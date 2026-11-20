"""Regression tests for slide-scope detection, verbatim-field handling, and long-text PDF rendering."""
import os
os.environ["LECTUREAI_TESTING"] = "1"

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pypdf
import pytest

import pedagogy_engine
from mock_generator import get_sample_bilingual_lecture_guide
from pdf_builder import PDFStudyGuideBuilder
from pipeline import process_lecture


@pytest.fixture
def deck_40(tmp_path):
    path = tmp_path / "deck40.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(40):
        writer.add_blank_page(width=720, height=540)
    with open(path, "wb") as f:
        writer.write(f)
    return path


class FakeClient:
    """Minimal stand-in for genai.Client that returns a canned guide and records prompts."""

    def __init__(self, covered_start=None, covered_end=None):
        guide = get_sample_bilingual_lecture_guide()
        guide.slides_covered_start = covered_start
        guide.slides_covered_end = covered_end
        guide.notes_reference = "whatever the model said"
        self._payload = guide.model_dump_json()
        self.prompts = []
        self.files = SimpleNamespace(
            upload=lambda file: SimpleNamespace(name=f"files/{Path(file).name}", state=None),
            get=lambda name: SimpleNamespace(name=name, state=None),
            delete=lambda name: None,
        )
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, model, contents, config):
        self.prompts.append(contents[-1])
        return SimpleNamespace(text=self._payload)


def _run(client, audit=None, **kwargs):
    audit = audit or (lambda **kw: (kw["guide"].model_copy(deep=True), None))
    with patch.object(pedagogy_engine, "verify_and_reconcile_study_guide", side_effect=audit):
        return pedagogy_engine._analyze_lecture_audio_impl(
            client=client, uploaded_files=[], transcript_text="[00:00] lecture text", **kwargs
        )


def test_open_end_detects_range_in_original_slide_numbers(deck_40):
    client = FakeClient(covered_start=10, covered_end=17)
    guide = _run(client, notes_path=deck_40, start_slide=10, end_slide=None)
    assert "page 1 of the attached slide file is original slide 10" in client.prompts[0]
    assert "original slides 10–40 of 40" in client.prompts[0]
    assert (guide.slides_covered_start, guide.slides_covered_end) == (10, 17)
    assert guide.notes_reference == "deck40.pdf (Slides 10–17 of 40, detected from lecture recording)"


def test_user_range_via_slide_ranges_is_never_overridden(deck_40):
    """Multi-source uploads pass the range in slide_ranges with end_slide=None; the user's end must win."""
    client = FakeClient(covered_start=1, covered_end=30)
    guide = _run(client, notes_path=[deck_40], slide_ranges=[(1, 12)])
    assert "slide range is fixed by the user" in client.prompts[0]
    assert (guide.slides_covered_start, guide.slides_covered_end) == (1, 12)
    assert "Slides 1–12 of 40" in guide.notes_reference
    assert "detected" not in guide.notes_reference


def test_explicit_end_slide_is_never_overridden(deck_40):
    client = FakeClient(covered_start=1, covered_end=35)
    guide = _run(client, notes_path=deck_40, start_slide=1, end_slide=20)
    assert (guide.slides_covered_start, guide.slides_covered_end) == (1, 20)
    assert "Slides 1–20 of 40" in guide.notes_reference


@pytest.mark.parametrize("bad_start,bad_end", [(1, 99), (5, 3), (None, 0), (50, 60)])
def test_out_of_range_detection_is_discarded(deck_40, bad_start, bad_end):
    client = FakeClient(covered_start=bad_start, covered_end=bad_end)
    guide = _run(client, notes_path=deck_40)
    if bad_end == 3:  # end valid, start after end -> start clamped to deck start
        assert (guide.slides_covered_start, guide.slides_covered_end) == (1, 3)
    else:
        assert guide.slides_covered_end is None
        assert "Full slide deck (40 slides)" in guide.notes_reference
    assert "25" not in (guide.notes_reference or "")


def test_multiple_decks_skip_detection(deck_40, tmp_path):
    second = tmp_path / "deck_b.pdf"
    second.write_bytes(deck_40.read_bytes())
    client = FakeClient(covered_start=1, covered_end=8)
    guide = _run(client, notes_path=[deck_40, second])
    assert "SLIDE NUMBERING" not in client.prompts[0]
    assert guide.slides_covered_end is None
    assert "deck40.pdf" in guide.notes_reference and "deck_b.pdf" in guide.notes_reference


def test_audit_pass_cannot_drop_scope_or_verbatim_fields(deck_40):
    def lossy_audit(**kw):
        g = kw["guide"].model_copy(deep=True)
        g.notes_reference = None
        g.slides_covered_start = g.slides_covered_end = None
        for s in g.sections:
            s.doctor_exact_wording = s.simple_explanation = s.practical_example = None
        return g, None

    client = FakeClient(covered_start=1, covered_end=9)
    guide = _run(client, audit=lossy_audit, notes_path=deck_40)
    assert guide.slides_covered_end == 9
    assert "Slides 1–9 of 40" in guide.notes_reference
    assert guide.sections[0].doctor_exact_wording
    assert guide.sections[0].simple_explanation
    assert guide.sections[0].practical_example


@pytest.mark.parametrize("mode,expect_fields", [
    ("detailed", False), ("revision", False), ("exam", False), ("verbatim_explained", True),
])
def test_verbatim_blocks_only_in_verbatim_mode(tmp_path, mode, expect_fields):
    result = process_lecture(
        use_sample_demo=True, study_mode=mode,
        custom_output_filename=str(tmp_path / f"{mode}.pdf"),
    )
    sec = result["guide"]["sections"][0]
    assert bool(sec["doctor_exact_wording"]) is expect_fields
    text = " ".join(p.extract_text() for p in pypdf.PdfReader(result["pdf_path"]).pages)
    assert ("SPOKEN WORDS" in text) is expect_fields


def test_demo_multi_deck_labels_use_each_decks_page_count(tmp_path, deck_40):
    small = tmp_path / "deck12.pdf"
    w = pypdf.PdfWriter()
    for _ in range(12):
        w.add_blank_page(width=720, height=540)
    with open(small, "wb") as f:
        w.write(f)
    result = process_lecture(
        use_sample_demo=True, notes_path=[deck_40, small], slide_ranges=[(3, None), (2, None)],
        custom_output_filename=str(tmp_path / "multi.pdf"),
    )
    assert "Slides 3–40 of 40" in result["notes_reference"]
    assert "Slides 2–12 of 12" in result["notes_reference"]


def test_very_long_verbatim_text_renders_across_pages(tmp_path):
    guide = get_sample_bilingual_lecture_guide()
    para = "The doctor explained the semaphore wait and signal operations in detail. " * 15
    guide.sections[0].doctor_exact_wording = "\n\n".join([para] * 10)
    guide.sections[0].simple_explanation = para * 8  # one giant paragraph
    guide.sections[0].practical_example = "Edge chars: <b>not bold</b> & 5 < 7 > 3"
    out = PDFStudyGuideBuilder(guide, output_filename=str(tmp_path / "long.pdf")).build()
    text = " ".join(p.extract_text() for p in pypdf.PdfReader(str(out)).pages)
    assert "SPOKEN WORDS" in text and "IN SIMPLE TERMS" in text
    assert "5 < 7" in text
