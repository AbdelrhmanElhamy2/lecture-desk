"""Multimodal audio transcription service powered by Google Gemini API."""

from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import (
    DEFAULT_MODEL,
    gemini_model_candidates,
    get_gemini_api_key,
)

logger = logging.getLogger(__name__)


def _sanitize_float(val: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """Safely convert any value to a finite float or return default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isfinite(f):
            return f
        return default
    except (TypeError, ValueError):
        return default


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class SourceTranscript:
    source_index: int
    text: str
    segments: list[TranscriptSegment]
    language: Optional[str] = None
    language_probability: Optional[float] = None


class GeminiTranscriptSegment(BaseModel):
    start: Optional[float] = Field(
        default=0.0,
        description="Start timestamp of the segment in seconds"
    )
    end: Optional[float] = Field(
        default=0.0,
        description="End timestamp of the segment in seconds"
    )
    text: Optional[str] = Field(
        default="",
        description="Transcribed spoken text in this segment"
    )


class GeminiAudioTranscription(BaseModel):
    language: Optional[str] = Field(
        default=None,
        description="ISO 639-1 language code of primary spoken language, e.g. 'en', 'ar'"
    )
    language_probability: Optional[float] = Field(
        default=None,
        description="Confidence score of language detection between 0.0 and 1.0"
    )
    segments: list[GeminiTranscriptSegment] = Field(
        default_factory=list,
        description="Ordered timestamped transcript segments"
    )
    full_text: Optional[str] = Field(
        default=None,
        description="Complete verbatim transcript combining all segments"
    )


TRANSCRIPTION_SYSTEM_INSTRUCTION = (
    "You are an expert academic audio transcription service. "
    "Transcribe the provided audio recording with high fidelity, ordered timestamped segments, and language detection. "
    "Keep spoken text in its original spoken language (e.g. if the lecturer speaks Arabic or switches between Arabic and English, "
    "transcribe both accurately as spoken). "
    "Preserve all mathematical formulas, engineering units, technical terms, and proper nouns verbatim. "
    "For each segment, output the start and end timestamps in seconds (float) and the spoken text. "
    "Detect the primary language and report your confidence score (0.0 to 1.0)."
)


def _file_state(file_obj: Any) -> str:
    """Return the Gemini File API state name, tolerating a missing/None state."""
    state = getattr(file_obj, "state", None)
    return getattr(state, "name", str(state or "")) if state is not None else ""


def _is_retryable_gemini_error(exc: Exception) -> bool:
    message = str(exc).upper()
    return any(code in message for code in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "TOO MANY REQUESTS"))


def _gemini_error_category(exc: Exception) -> str:
    message = str(exc).upper()
    if "404" in message or "NOT_FOUND" in message or ("MODEL" in message and "NOT AVAILABLE" in message):
        return "The configured Gemini model is unavailable."
    if "401" in message or "403" in message or "API_KEY" in message or "PERMISSION" in message:
        return "Gemini rejected the API key or request permissions."
    if _is_retryable_gemini_error(exc):
        return "Gemini is temporarily overloaded or rate limited."
    sanitized = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", str(exc))
    return sanitized


def _delete_remote_files(client: Optional[genai.Client], files: list[Any]) -> None:
    """Best-effort cleanup of uploaded audio files from Gemini File API in finally block."""
    if not client or not hasattr(client, "files"):
        return
    seen: set[str] = set()
    for f in files:
        file_name = getattr(f, "name", None) if not isinstance(f, str) else f
        if file_name and file_name not in seen:
            seen.add(file_name)
            try:
                client.files.delete(name=file_name)
            except Exception:
                pass


def _parse_transcription_payload(raw_json: str) -> Optional[GeminiAudioTranscription]:
    """Parse model JSON output with multi-candidate extraction and resilient dict fallback."""
    raw_clean = raw_json.strip()
    candidates: list[str] = [raw_clean]

    # Candidate 2: Markdown code fence extraction
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_clean, re.IGNORECASE)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    # Candidate 3: Clean leading and trailing markdown fence backticks
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_clean, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    if cleaned != raw_clean:
        candidates.append(cleaned.strip())

    # Candidate 4: Outermost curly braces object
    brace_match = re.search(r"\{.*\}", raw_clean, re.DOTALL)
    if brace_match:
        candidates.append(brace_match.group(0).strip())

    # Candidate 5: Balanced JSON object scanning from '{' markers
    decoder = json.JSONDecoder()
    pos = 0
    while True:
        idx = raw_clean.find("{", pos)
        if idx == -1:
            break
        try:
            obj, _ = decoder.raw_decode(raw_clean[idx:])
            if isinstance(obj, dict) and any(k in obj for k in ("segments", "full_text", "text", "transcript", "transcription")):
                candidates.append(json.dumps(obj))
                break
        except Exception:
            pass
        pos = idx + 1

    for cand in candidates:
        if not cand:
            continue
        try:
            data = json.loads(cand)
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        # Try strict Pydantic model validation first
        try:
            return GeminiAudioTranscription.model_validate(data)
        except Exception:
            pass

        # Resilient dictionary fallback if Pydantic validation failed on edge cases
        try:
            segments: list[GeminiTranscriptSegment] = []
            raw_segments = data.get("segments")
            if isinstance(raw_segments, list):
                for item in raw_segments:
                    if isinstance(item, dict):
                        text = str(item.get("text") or "").strip()
                        if text:
                            start = max(0.0, _sanitize_float(item.get("start"), 0.0) or 0.0)
                            end = max(start, _sanitize_float(item.get("end"), start) or start)
                            segments.append(GeminiTranscriptSegment(start=start, end=end, text=text))

            full_text = str(
                data.get("full_text")
                or data.get("text")
                or data.get("transcript")
                or data.get("transcription")
                or ""
            ).strip()

            raw_lang_prob = _sanitize_float(data.get("language_probability"), None)
            if raw_lang_prob is not None:
                if 1.0 < raw_lang_prob <= 100.0:
                    raw_lang_prob = raw_lang_prob / 100.0
                raw_lang_prob = max(0.0, min(1.0, raw_lang_prob))

            lang = str(data.get("language") or "").strip() or None

            return GeminiAudioTranscription(
                language=lang,
                language_probability=raw_lang_prob,
                segments=segments,
                full_text=full_text or None,
            )
        except Exception:
            continue

    return None


def _transcribe_single_recording(
    client: genai.Client,
    path: Path,
    index: int,
    candidate_models: list[str],
    cancellation_check: Optional[Callable[[], None]] = None,
) -> SourceTranscript:
    """Upload audio to Gemini Files API, transcribe using candidate models, and ensure file deletion in finally block."""
    uploaded_files: list[Any] = []
    try:
        try:
            uploaded_file = client.files.upload(file=str(path))
            uploaded_files.append(uploaded_file)
        except Exception as exc:
            err_msg = _gemini_error_category(exc)
            if any(k in str(exc).upper() for k in ("401", "403", "API_KEY", "PERMISSION", "503", "UNAVAILABLE", "429")):
                raise RuntimeError(f"Gemini audio upload failed for recording {index}: {err_msg}") from exc
            raise ValueError(f"Recording {index} could not be uploaded or decoded: {err_msg}") from exc

        # Poll if file is still processing with 5-minute timeout guard and transient error retry
        poll_start = time.time()
        while _file_state(uploaded_file).upper() == "PROCESSING":
            if cancellation_check:
                cancellation_check()
            if time.time() - poll_start > 300.0:
                raise RuntimeError(f"Recording {index} audio processing timed out on Gemini File API.")
            time.sleep(1)
            file_name = getattr(uploaded_file, "name", None)
            if not file_name:
                raise RuntimeError(f"Recording {index} has no file handle to check processing status.")
            try:
                uploaded_file = client.files.get(name=file_name)
            except Exception as exc:
                if _is_retryable_gemini_error(exc) and (time.time() - poll_start <= 300.0):
                    logger.warning("Transient error checking Gemini file %s: %s; retrying...", file_name, exc)
                    time.sleep(2)
                    continue
                raise

        if _file_state(uploaded_file).upper() == "FAILED":
            err_obj = getattr(uploaded_file, "error", None)
            err_msg = getattr(err_obj, "message", str(err_obj)) if err_obj else "Unknown error"
            raise ValueError(f"Recording {index} processing failed on Gemini: {err_msg}")

        if cancellation_check:
            cancellation_check()

        prompt = (
            "Transcribe this university lecture recording completely into ordered timestamped segments. "
            "Identify the spoken language and provide start and end timestamps in seconds for every segment."
        )

        parsed: Optional[GeminiAudioTranscription] = None
        last_error: Optional[Exception] = None
        last_response_text: Optional[str] = None

        for model_name in candidate_models:
            for attempt in range(2):
                if cancellation_check:
                    cancellation_check()
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[uploaded_file, prompt],
                        config=types.GenerateContentConfig(
                            system_instruction=TRANSCRIPTION_SYSTEM_INSTRUCTION,
                            response_mime_type="application/json",
                            response_schema=GeminiAudioTranscription,
                            temperature=0.0,
                        ),
                    )
                    if response is not None and response.text:
                        last_response_text = response.text
                        parsed_cand = _parse_transcription_payload(response.text)
                        if parsed_cand is not None:
                            full_txt = (parsed_cand.full_text or "").strip()
                            if not full_txt:
                                full_txt = " ".join((s.text or "").strip() for s in parsed_cand.segments if s.text).strip()
                            if full_txt:
                                parsed = parsed_cand
                                last_error = None
                                break
                            else:
                                logger.warning(
                                    "Model %s produced an empty transcript for recording %s; trying next candidate...",
                                    model_name, index,
                                )
                        else:
                            logger.warning(
                                "Model %s produced unparseable JSON for recording %s; trying next candidate...",
                                model_name, index,
                            )
                except Exception as exc:
                    last_error = exc
                    if _is_retryable_gemini_error(exc):
                        time.sleep(2)
                        continue
                    else:
                        break
            if parsed is not None:
                break

        if parsed is None:
            if last_error:
                error_msg = _gemini_error_category(last_error)
                raise RuntimeError(f"Gemini audio transcription failed for recording {index}: {error_msg}") from last_error
            if last_response_text:
                test_parse = _parse_transcription_payload(last_response_text)
                if test_parse is None:
                    raise ValueError(f"Recording {index} transcription could not be parsed: invalid JSON response.")
                raise ValueError(f"Recording {index} produced an empty transcript. Try another recording or audio source.")
            raise RuntimeError(f"Gemini returned an empty transcription for recording {index}.")

        segments: list[TranscriptSegment] = []
        for s in parsed.segments:
            s_text = (s.text or "").strip()
            if s_text:
                start_val = max(0.0, _sanitize_float(s.start, 0.0) or 0.0)
                end_val = max(start_val, _sanitize_float(s.end, start_val) or start_val)
                segments.append(TranscriptSegment(start=start_val, end=end_val, text=s_text))

        full_text = (parsed.full_text or "").strip()
        if not full_text:
            full_text = " ".join(seg.text for seg in segments if seg.text).strip()

        if not full_text:
            raise ValueError(f"Recording {index} produced an empty transcript. Try another recording or audio source.")

        if not segments and full_text:
            segments.append(TranscriptSegment(start=0.0, end=0.0, text=full_text))

        lang_prob = _sanitize_float(parsed.language_probability, None)
        if lang_prob is not None:
            if 1.0 < lang_prob <= 100.0:
                lang_prob = lang_prob / 100.0
            lang_prob = max(0.0, min(1.0, lang_prob))

        return SourceTranscript(
            source_index=index,
            text=full_text,
            segments=segments,
            language=parsed.language,
            language_probability=lang_prob,
        )
    finally:
        _delete_remote_files(client, uploaded_files)


def transcribe_audio_sources(
    audio_paths: Sequence[Path | str],
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    client: Optional[genai.Client] = None,
    progress_callback: Optional[Callable[[str, int], None]] = None,
    cancellation_check: Optional[Callable[[], None]] = None,
    **kwargs: Any,
) -> list[SourceTranscript]:
    """Transcribe audio files using Google Gemini API and structured output."""
    if not audio_paths:
        raise ValueError("At least one lecture recording is required.")

    # Preflight check all recordings upfront to fail fast before expensive uploads/transcriptions
    normalized_paths: list[Path] = []
    for index, raw_path in enumerate(audio_paths, 1):
        p = Path(raw_path)
        if not p.exists() or not p.is_file():
            raise ValueError(f"Recording {index} could not be found.")
        if p.stat().st_size == 0:
            raise ValueError(f"Recording {index} is empty.")
        normalized_paths.append(p)

    resolved_key = api_key or get_gemini_api_key()
    if client is None:
        if not resolved_key:
            raise ValueError(
                "Gemini API key is required for audio transcription. "
                "Please provide it in the Web UI or configure GEMINI_API_KEY."
            )
        client = genai.Client(api_key=resolved_key)

    chosen_model = model or kwargs.get("model_name") or DEFAULT_MODEL
    candidate_models = gemini_model_candidates(chosen_model)

    results: list[SourceTranscript] = []
    count = len(normalized_paths)

    for index, path in enumerate(normalized_paths, 1):
        if progress_callback:
            progress_callback(
                f"Transcribing recording {index}/{count} with Gemini API...",
                20 + int(25 * (index - 1) / count),
            )

        if cancellation_check:
            cancellation_check()

        try:
            transcript = _transcribe_single_recording(
                client=client,
                path=path,
                index=index,
                candidate_models=candidate_models,
                cancellation_check=cancellation_check,
            )
            results.append(transcript)
        except (ValueError, RuntimeError, InterruptedError):
            raise
        except Exception as exc:
            if cancellation_check:
                cancellation_check()
            if "CANCEL" in type(exc).__name__.upper() or "INTERRUPT" in type(exc).__name__.upper():
                raise
            logger.warning("Transcription failed for recording %s (%s).", index, type(exc).__name__)
            raise ValueError(f"Recording {index} could not be decoded or transcribed. Check that it is a supported, readable audio file.") from exc

    return results


def format_transcript(transcripts: Sequence[SourceTranscript]) -> str:
    """Build an ordered, timestamped transcript without exposing local paths."""
    blocks = []
    for source in transcripts:
        language = f"; detected language: {source.language}" if source.language else ""
        if source.language_probability is not None:
            prob = _sanitize_float(source.language_probability, None)
            if prob is not None:
                language += f" ({prob:.2f} confidence)"
        lines = [f"[Recording {source.source_index}{language}]"]
        segment_lines = []
        for segment in source.segments:
            s_text = (getattr(segment, "text", "") or "").strip()
            if s_text:
                st = max(0.0, _sanitize_float(getattr(segment, "start", 0.0), 0.0) or 0.0)
                en = max(st, _sanitize_float(getattr(segment, "end", st), st) or st)
                segment_lines.append(f"[{st:.2f}-{en:.2f}] {s_text}")
        if segment_lines:
            lines.extend(segment_lines)
        elif source.text and source.text.strip():
            lines.append(f"[0.00-0.00] {source.text.strip()}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def transcript_metadata(transcripts: Sequence[SourceTranscript]) -> list[dict[str, Any]]:
    return [asdict(item) for item in transcripts]
