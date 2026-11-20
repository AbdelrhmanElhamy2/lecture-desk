import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import config
import pipeline
import transcription
from mock_generator import get_sample_bilingual_lecture_guide
from models import VerificationResult


class TestGeminiAudioTranscription(unittest.TestCase):
    def test_transcriber_uploads_transcribes_and_cleans_up_files_preserving_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.mp3"
            second = Path(tmp) / "second.mp3"
            first.write_bytes(b"first audio content")
            second.write_bytes(b"second audio content")

            mock_client = MagicMock()
            uploaded_file1 = SimpleNamespace(name="files/audio1", state="ACTIVE")
            uploaded_file2 = SimpleNamespace(name="files/audio2", state="ACTIVE")
            mock_client.files.upload.side_effect = [uploaded_file1, uploaded_file2]

            sample_json = json.dumps({
                "language": "ar",
                "language_probability": 0.91,
                "segments": [
                    {"start": 0.25, "end": 1.5, "text": "Power electronics"},
                    {"start": 1.5, "end": 2.0, "text": "lecture"}
                ],
                "full_text": "Power electronics lecture"
            })
            mock_client.models.generate_content.return_value = SimpleNamespace(text=sample_json)

            result = transcription.transcribe_audio_sources([first, second], client=mock_client)

            self.assertEqual([item.source_index for item in result], [1, 2])
            self.assertEqual([item.text for item in result], ["Power electronics lecture", "Power electronics lecture"])
            self.assertEqual(result[0].segments[0].start, 0.25)
            self.assertEqual(result[0].segments[1].end, 2.0)
            self.assertEqual(result[0].language, "ar")
            self.assertAlmostEqual(result[0].language_probability, 0.91)

            # Verify files were uploaded in order
            self.assertEqual(mock_client.files.upload.call_count, 2)
            # Verify files were cleaned up from Gemini File API in finally blocks
            self.assertEqual(mock_client.files.delete.call_count, 2)
            mock_client.files.delete.assert_has_calls([
                call(name="files/audio1"),
                call(name="files/audio2"),
            ])

    def test_temporary_uploaded_file_cleaned_up_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lecture.wav"
            path.write_bytes(b"lecture audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/failed_audio", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file
            mock_client.models.generate_content.side_effect = RuntimeError("503 Service Unavailable")

            with self.assertRaises(RuntimeError):
                transcription.transcribe_audio_sources([path], client=mock_client)

            # Verify file was cleaned up despite failure
            mock_client.files.delete.assert_called_once_with(name="files/failed_audio")

    def test_model_fallback_from_primary_to_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lecture.wav"
            path.write_bytes(b"lecture audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/fallback_audio", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            success_json = json.dumps({
                "language": "en",
                "language_probability": 0.99,
                "segments": [{"start": 0.0, "end": 2.5, "text": "Signal processing fundamentals"}],
                "full_text": "Signal processing fundamentals"
            })

            # Primary model fails twice (due to retry), fallback model succeeds
            mock_client.models.generate_content.side_effect = [
                RuntimeError("503 UNAVAILABLE"),
                RuntimeError("503 UNAVAILABLE"),
                SimpleNamespace(text=success_json),
            ]

            with patch("transcription.time.sleep"):
                result = transcription.transcribe_audio_sources(
                    [path],
                    client=mock_client,
                    model="gemini-3.8-flash"
                )

            self.assertEqual(result[0].text, "Signal processing fundamentals")
            called_models = [c.kwargs["model"] for c in mock_client.models.generate_content.call_args_list]
            self.assertIn("gemini-3.8-flash", called_models)
            self.assertIn("gemini-3.6-flash", called_models)
            mock_client.files.delete.assert_called_once_with(name="files/fallback_audio")

    def test_empty_audio_and_empty_transcript_are_readable_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.wav"
            empty.touch()
            with self.assertRaisesRegex(ValueError, "empty"):
                transcription.transcribe_audio_sources([empty], client=MagicMock())

            valid = Path(tmp) / "silent.wav"
            valid.write_bytes(b"audio content")
            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/silent", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file
            empty_json = json.dumps({
                "language": "en",
                "language_probability": 0.8,
                "segments": [],
                "full_text": ""
            })
            mock_client.models.generate_content.return_value = SimpleNamespace(text=empty_json)
            with self.assertRaisesRegex(ValueError, "empty transcript"):
                transcription.transcribe_audio_sources([valid], client=mock_client)
            mock_client.files.delete.assert_called_once_with(name="files/silent")

    def test_missing_api_key_raises_readable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")
            with patch("transcription.get_gemini_api_key", return_value=""):
                with self.assertRaisesRegex(ValueError, "Gemini API key is required"):
                    transcription.transcribe_audio_sources([path], api_key=None, client=None)

    def test_cancellation_check_aborts_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/cancel_audio", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            checks = 0

            def cancel():
                nonlocal checks
                checks += 1
                if checks >= 2:
                    raise InterruptedError("Cancelled")

            with self.assertRaises(InterruptedError):
                transcription.transcribe_audio_sources([path], client=mock_client, cancellation_check=cancel)

            mock_client.files.delete.assert_called_once_with(name="files/cancel_audio")

    def test_gemini_policy_allows_only_primary_and_configured_fallback(self):
        expected_chain = [
            "gemini-4-hydrogen",
            "gemini-3.8-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
        ]
        self.assertEqual(config.PRIMARY_GEMINI_MODEL, "gemini-4-hydrogen")
        self.assertEqual(config.FALLBACK_GEMINI_MODEL, "gemini-3.8-flash")
        self.assertEqual(list(config.FREE_TIER_GEMINI_MODELS), expected_chain)
        self.assertEqual(config.default_gemini_model(), "gemini-4-hydrogen")
        self.assertEqual(config.default_gemini_model("gemini-3.7-flash"), "gemini-4-hydrogen")
        self.assertEqual(config.gemini_model_candidates("gemini-4-hydrogen"), expected_chain)
        self.assertEqual(config.gemini_model_candidates("gemini-3.8-flash"), expected_chain[1:])
        self.assertEqual(config.gemini_model_candidates("gemini-3.1-flash-lite"), ["gemini-3.1-flash-lite"])
        for disallowed in (
            "gemini-3.5-flash",
            "gemini-3.7-flash",
            "gemini-2.5-flash",
            "gemini-4-argon",
            "gemini-4-neon",
            "gemini-4-carbon",
            "gemini-3.1-pro-preview",
            "gemini-flash-latest",
        ):
            with self.assertRaises(ValueError):
                config.resolve_gemini_model(disallowed)

    def test_runtime_model_ui_env_and_docs_are_consistent(self):
        root = Path(__file__).resolve().parents[1]
        ui = (root / "templates" / "index.html").read_text(encoding="utf-8")
        env_example = (root / ".env.example").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        for model_id in config.FREE_TIER_GEMINI_MODELS:
            self.assertIn(f'value="{model_id}"', ui)
            self.assertIn(model_id, readme)
        self.assertNotIn('value="gemini-3.5-flash"', ui)
        self.assertNotIn('value="gemini-3.7-flash"', ui)
        self.assertNotIn('value="gemini-4-argon"', ui)
        self.assertNotIn('value="gemini-2.5-flash"', ui)
        self.assertIn("GEMINI_MODEL=gemini-4-hydrogen", env_example)
        self.assertNotIn("LECTUREAI_WHISPER_MODEL", env_example)

    def test_generation_sends_transcript_not_audio_and_uses_bounded_fallback(self):
        import pedagogy_engine
        guide = get_sample_bilingual_lecture_guide()
        verification = VerificationResult(
            contradictions_detected=0,
            audit_summary="Transcript check complete.",
            corrected_guide=guide,
        )
        responses = [
            SimpleNamespace(text=guide.model_dump_json()),
            SimpleNamespace(text=verification.model_dump_json()),
        ]
        client = MagicMock()
        client.models.generate_content.side_effect = [
            RuntimeError("503 UNAVAILABLE"),
            RuntimeError("503 UNAVAILABLE"),
            *responses
        ]
        transcript = "[Recording 1; detected language: ar]\n[0.25-1.50] MOSFET switching frequency"
        with patch("pedagogy_engine.genai.Client", return_value=client), patch("pedagogy_engine.time.sleep"):
            result = pedagogy_engine.analyze_lecture_transcript(transcript, api_key="unit-test-key", model="gemini-3.8-flash")
        self.assertIsNotNone(result)
        requested_models = [call.kwargs["model"] for call in client.models.generate_content.call_args_list]
        self.assertEqual(requested_models, ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.6-flash"])
        self.assertFalse(any(model in {"gemini-3.5-flash", "gemini-3.7-flash"} for model in requested_models))
        payloads = [call.kwargs["contents"] for call in client.models.generate_content.call_args_list]
        self.assertTrue(all(any(transcript in item for item in payload if isinstance(item, str)) for payload in payloads))
        self.assertTrue(all(b"audio" not in payload for payload in payloads if isinstance(payload, bytes)))
        client.files.upload.assert_not_called()

    def test_demo_skips_transcription_and_gemini(self):
        class Builder:
            def __init__(self, guide, **kwargs):
                self.guide = guide

            def build(self):
                return Path(tempfile.gettempdir()) / "mock-demo.pdf"

        with patch("pipeline.transcribe_audio_sources", side_effect=AssertionError("Transcription called")), \
             patch("pipeline.analyze_lecture_transcript", side_effect=AssertionError("Gemini path called")), \
             patch("pipeline.PDFStudyGuideBuilder", Builder):
            result = pipeline.process_lecture(use_sample_demo=True)
        self.assertTrue(result["is_demo"])
        self.assertTrue(result["guide"]["verification_report"]["is_simulation"])
        self.assertIn("Simulated", result["verification_report"]["overall_fidelity_summary"])

    def test_pipeline_transcribes_with_gemini_before_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "lecture-recording.wav"
            audio.write_bytes(b"synthetic audio")
            transcription_result = [transcription.SourceTranscript(
                source_index=1,
                text="switching frequency is ten kilohertz",
                segments=[transcription.TranscriptSegment(0.0, 1.25, "switching frequency is ten kilohertz")],
                language="en",
                language_probability=0.98,
            )]
            generated = get_sample_bilingual_lecture_guide()
            with patch("pipeline.transcribe_audio_sources", return_value=transcription_result) as transcribe, \
                 patch("pipeline.analyze_lecture_transcript", return_value=generated) as analyze, \
                 patch("pipeline.PDFStudyGuideBuilder") as builder:
                builder.return_value.build.return_value = Path(tmp) / "guide.pdf"
                pipeline.process_lecture(audio_path=[audio], api_key="test-key", model="gemini-3.8-flash")

            transcribe.assert_called_once()
            self.assertEqual(transcribe.call_args.kwargs["api_key"], "test-key")
            self.assertEqual(transcribe.call_args.kwargs["model"], "gemini-3.8-flash")
            self.assertEqual(analyze.call_args.kwargs["transcript_text"].count("switching frequency"), 1)

            with patch("pipeline.transcribe_audio_sources", side_effect=ValueError("Gemini transcription failed")), \
                 patch("pipeline.analyze_lecture_transcript") as analyze:
                with self.assertRaisesRegex(ValueError, "Gemini transcription failed"):
                    pipeline.process_lecture(audio_path=[audio], api_key="test-key")
                analyze.assert_not_called()

    def test_gemini_key_is_preflighted_before_transcription(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "recording.wav"
            audio.write_bytes(b"audio")
            with patch("pipeline.get_gemini_api_key", return_value=""), \
                 patch("pipeline.transcribe_audio_sources") as transcribe:
                with self.assertRaisesRegex(ValueError, "Gemini API key is required"):
                    pipeline.process_lecture(audio_path=[audio], api_key=None)
                transcribe.assert_not_called()

    def test_job_error_redacts_key_paths_and_signed_links(self):
        from app import safe_public_error
        message = safe_public_error(
            r"Key secret-token failed at C:\private\lecture.mp3 https://example.test/file?token=secret-token",
            "secret-token"
        )
        self.assertNotIn("secret-token", message)
        self.assertNotIn("C:\\private", message)
        self.assertNotIn("https://", message)


    def test_file_processing_timeout_raises_runtime_error_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/timeout_audio", state="PROCESSING")
            mock_client.files.upload.return_value = uploaded_file
            mock_client.files.get.return_value = uploaded_file

            with patch("transcription.time.time", side_effect=[0.0, 0.0, 301.0, 302.0]):
                with self.assertRaisesRegex(RuntimeError, "processing timed out"):
                    transcription.transcribe_audio_sources([path], client=mock_client)

            mock_client.files.delete.assert_called_once_with(name="files/timeout_audio")

    def test_file_processing_failed_state_raises_value_error_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            error_status = SimpleNamespace(message="Unsupported audio codec")
            uploaded_file = SimpleNamespace(name="files/failed_audio", state="FAILED", error=error_status)
            mock_client.files.upload.return_value = uploaded_file

            with self.assertRaisesRegex(ValueError, "Unsupported audio codec"):
                transcription.transcribe_audio_sources([path], client=mock_client)

            mock_client.files.delete.assert_called_once_with(name="files/failed_audio")

    def test_markdown_code_fenced_json_is_successfully_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/markdown_audio", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            raw_payload = "```json\n" + json.dumps({
                "language": "en",
                "language_probability": 0.95,
                "segments": [{"start": 0.0, "end": 1.0, "text": "Fenced JSON response"}],
                "full_text": "Fenced JSON response"
            }) + "\n```"
            mock_client.models.generate_content.return_value = SimpleNamespace(text=raw_payload)

            result = transcription.transcribe_audio_sources([path], client=mock_client)
            self.assertEqual(result[0].text, "Fenced JSON response")
            mock_client.files.delete.assert_called_once_with(name="files/markdown_audio")

    def test_malformed_json_raises_clean_value_error_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/malformed_audio", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file
            mock_client.models.generate_content.return_value = SimpleNamespace(text="Not valid json: {foo: bar, baz}")

            with self.assertRaisesRegex(ValueError, "transcription could not be parsed: invalid JSON response"):
                transcription.transcribe_audio_sources([path], client=mock_client)

            mock_client.files.delete.assert_called_once_with(name="files/malformed_audio")

    def test_negative_and_inverted_timestamps_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/timestamps_audio", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            sample_json = json.dumps({
                "language": "en",
                "language_probability": 0.99,
                "segments": [
                    {"start": -2.5, "end": 1.0, "text": "Negative start"},
                    {"start": 5.0, "end": 2.0, "text": "Inverted interval"},
                ],
                "full_text": "Negative start Inverted interval"
            })
            mock_client.models.generate_content.return_value = SimpleNamespace(text=sample_json)

            result = transcription.transcribe_audio_sources([path], client=mock_client)
            self.assertEqual(result[0].segments[0].start, 0.0)
            self.assertEqual(result[0].segments[0].end, 1.0)
            self.assertEqual(result[0].segments[1].start, 5.0)
            self.assertEqual(result[0].segments[1].end, 5.0)
            mock_client.files.delete.assert_called_once_with(name="files/timestamps_audio")

    def test_upload_api_error_categorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            mock_client.files.upload.side_effect = RuntimeError("403 PERMISSION_DENIED: API key expired")

            with self.assertRaisesRegex(RuntimeError, "Gemini rejected the API key or request permissions"):
                transcription.transcribe_audio_sources([path], client=mock_client)

    def test_nonexistent_audio_file_raises_readable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist.wav"
            with self.assertRaisesRegex(ValueError, "could not be found"):
                transcription.transcribe_audio_sources([missing], client=MagicMock())

    def test_fenced_json_with_trailing_braces_is_parsed(self):
        """Model outputs fenced JSON followed by explanatory notes with braces."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/audio_fenced_trailing", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            sample_json = json.dumps({
                "language": "en",
                "language_probability": 0.95,
                "segments": [{"start": 0.0, "end": 1.5, "text": "Welcome to class."}],
                "full_text": "Welcome to class."
            })
            raw_response = f"```json\n{sample_json}\n```\nFormula reference: {{V_in = 12V}}"
            mock_client.models.generate_content.return_value = SimpleNamespace(text=raw_response)

            result = transcription.transcribe_audio_sources([path], client=mock_client)
            self.assertEqual(result[0].text, "Welcome to class.")
            mock_client.files.delete.assert_called_once_with(name="files/audio_fenced_trailing")

    def test_null_and_missing_timestamps_in_segments(self):
        """Model outputs segments with null or omitted start/end timestamps."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/audio_null_ts", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            sample_json = json.dumps({
                "language": "en",
                "segments": [
                    {"start": None, "end": 2.0, "text": "Segment one with null start"},
                    {"text": "Segment two with missing timestamps"}
                ],
                "full_text": "Segment one with null start Segment two with missing timestamps"
            })
            mock_client.models.generate_content.return_value = SimpleNamespace(text=sample_json)

            result = transcription.transcribe_audio_sources([path], client=mock_client)
            self.assertEqual(len(result[0].segments), 2)
            self.assertEqual(result[0].segments[0].start, 0.0)
            self.assertEqual(result[0].segments[0].end, 2.0)
            self.assertEqual(result[0].segments[1].start, 0.0)
            mock_client.files.delete.assert_called_once_with(name="files/audio_null_ts")

    def test_polling_transient_error_is_retried(self):
        """Transient 503 during client.files.get polling loop should retry, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/audio_poll_glitch", state="PROCESSING")
            active_file = SimpleNamespace(name="files/audio_poll_glitch", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            mock_client.files.get.side_effect = [
                RuntimeError("503 UNAVAILABLE"),
                active_file,
            ]

            success_json = json.dumps({
                "language": "en",
                "segments": [{"start": 0.0, "end": 1.0, "text": "Polled audio"}],
                "full_text": "Polled audio"
            })
            mock_client.models.generate_content.return_value = SimpleNamespace(text=success_json)

            with patch("transcription.time.sleep"):
                result = transcription.transcribe_audio_sources([path], client=mock_client)

            self.assertEqual(result[0].text, "Polled audio")
            mock_client.files.delete.assert_called_once_with(name="files/audio_poll_glitch")

    def test_multifile_preflight_fails_fast_without_upload(self):
        """If 2nd file is missing, 1st file should NOT be uploaded."""
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.mp3"
            first.write_bytes(b"first audio")
            missing = Path(tmp) / "second_missing.mp3"

            mock_client = MagicMock()

            with self.assertRaisesRegex(ValueError, "could not be found"):
                transcription.transcribe_audio_sources([first, missing], client=mock_client)

            mock_client.files.upload.assert_not_called()

    def test_nan_and_inf_timestamps_are_sanitized(self):
        """Model outputs NaN or Inf timestamps."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/audio_nan", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            sample_json = json.dumps({
                "language": "en",
                "segments": [
                    {"start": float("nan"), "end": float("inf"), "text": "NaN and Inf timestamps"}
                ],
                "full_text": "NaN and Inf timestamps"
            })
            mock_client.models.generate_content.return_value = SimpleNamespace(text=sample_json)

            result = transcription.transcribe_audio_sources([path], client=mock_client)
            self.assertEqual(result[0].segments[0].start, 0.0)
            self.assertEqual(result[0].segments[0].end, 0.0)
            mock_client.files.delete.assert_called_once_with(name="files/audio_nan")

    def test_percentage_language_probability_normalized(self):
        """Model outputs language_probability as a percentage e.g. 95 instead of 0.95."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/audio_prob", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            sample_json = json.dumps({
                "language": "en",
                "language_probability": 95.0,
                "segments": [{"start": 0.0, "end": 1.0, "text": "Normalized probability"}],
                "full_text": "Normalized probability"
            })
            mock_client.models.generate_content.return_value = SimpleNamespace(text=sample_json)

            result = transcription.transcribe_audio_sources([path], client=mock_client)
            self.assertAlmostEqual(result[0].language_probability, 0.95)

    def test_model_fallback_when_primary_returns_unparseable_json(self):
        """Primary model produces conversational refusal or non-JSON; fallback model rescues."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/audio_refusal", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            refusal_response = SimpleNamespace(text="I cannot process this audio file directly.")
            valid_json = json.dumps({
                "language": "en",
                "segments": [{"start": 0.0, "end": 2.0, "text": "Rescued by fallback model"}],
                "full_text": "Rescued by fallback model"
            })
            success_response = SimpleNamespace(text=valid_json)

            # Primary model returns unparseable text on both attempts, fallback model succeeds
            mock_client.models.generate_content.side_effect = [
                refusal_response,
                refusal_response,
                success_response,
            ]

            result = transcription.transcribe_audio_sources(
                [path],
                client=mock_client,
                model="gemini-3.8-flash"
            )

            self.assertEqual(result[0].text, "Rescued by fallback model")
            called_models = [c.kwargs["model"] for c in mock_client.models.generate_content.call_args_list]
            self.assertIn("gemini-3.8-flash", called_models)
            self.assertIn("gemini-3.6-flash", called_models)
            mock_client.files.delete.assert_called_once_with(name="files/audio_refusal")

    def test_model_fallback_when_primary_returns_empty_transcript(self):
        """Primary model returns empty transcript; fallback model succeeds with text."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/audio_empty_primary", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            empty_response = SimpleNamespace(text=json.dumps({"language": "en", "segments": [], "full_text": ""}))
            valid_json = json.dumps({
                "language": "en",
                "segments": [{"start": 0.0, "end": 1.5, "text": "Fallback captured audio"}],
                "full_text": "Fallback captured audio"
            })
            success_response = SimpleNamespace(text=valid_json)

            mock_client.models.generate_content.side_effect = [
                empty_response,
                empty_response,
                success_response,
            ]

            result = transcription.transcribe_audio_sources(
                [path],
                client=mock_client,
                model="gemini-3.8-flash"
            )

            self.assertEqual(result[0].text, "Fallback captured audio")
            called_models = [c.kwargs["model"] for c in mock_client.models.generate_content.call_args_list]
            self.assertIn("gemini-3.8-flash", called_models)
            self.assertIn("gemini-3.6-flash", called_models)
            mock_client.files.delete.assert_called_once_with(name="files/audio_empty_primary")

    def test_cancellation_exception_propagates_unmasked(self):
        """Cancellation exceptions must not be caught and re-wrapped as audio decode ValueError."""
        class MockJobCancelledException(Exception):
            pass

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recording.wav"
            path.write_bytes(b"audio")

            mock_client = MagicMock()
            uploaded_file = SimpleNamespace(name="files/cancel_audio_2", state="ACTIVE")
            mock_client.files.upload.return_value = uploaded_file

            call_count = [0]
            def cancel_checker():
                call_count[0] += 1
                # Trigger on 2nd check which occurs inside _transcribe_single_recording
                if call_count[0] >= 2:
                    raise MockJobCancelledException("User requested cancellation")

            with self.assertRaises(MockJobCancelledException):
                transcription.transcribe_audio_sources(
                    [path],
                    client=mock_client,
                    cancellation_check=cancel_checker
                )
            mock_client.files.delete.assert_called_once_with(name="files/cancel_audio_2")

    def test_format_transcript_falls_back_to_source_text_when_segments_empty(self):
        """When segments list is empty, format_transcript retains full lecture text."""
        source = transcription.SourceTranscript(
            source_index=1,
            text="Comprehensive power electronics lecture on inverter topologies.",
            segments=[],
            language="en",
            language_probability=0.99
        )
        formatted = transcription.format_transcript([source])
        self.assertIn("[Recording 1; detected language: en (0.99 confidence)]", formatted)
        self.assertIn("[0.00-0.00] Comprehensive power electronics lecture on inverter topologies.", formatted)

    def test_unfenced_json_with_trailing_braces_parsed_successfully(self):
        """Payload has introductory text and trailing notes with braces outside code fences."""
        payload = (
            "Here is the lecture transcript:\n"
            + json.dumps({
                "language": "en",
                "segments": [{"start": 0.0, "end": 2.0, "text": "Signal processing lecture"}],
                "full_text": "Signal processing lecture"
            })
            + "\nNotes from lecture: {V_out = 5V, R = 100 Ohms}"
        )
        parsed = transcription._parse_transcription_payload(payload)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.full_text, "Signal processing lecture")
        self.assertEqual(len(parsed.segments), 1)
        self.assertEqual(parsed.segments[0].text, "Signal processing lecture")


if __name__ == "__main__":
    unittest.main()
