import os
os.environ["LECTUREAI_TESTING"] = "1"

import pytest
import pypdf
from pathlib import Path
from fastapi.testclient import TestClient

from models import LectureStudyGuide, LectureSection, DoctorAlert, KeyFormula, TableDefinition, DiagramDefinition, ExamQuestion
from pedagogy_engine import slice_pdf_pages, _analyze_lecture_audio_impl
from pdf_builder import PDFStudyGuideBuilder
from pipeline import process_lecture
from mock_generator import get_sample_bilingual_lecture_guide
from app import app


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def sample_multi_page_pdf(tmp_path):
    """Creates a synthetic 40-page PDF to test dynamic slide counts without any 25-page cap."""
    pdf_path = tmp_path / "test_deck_40_pages.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(40):
        writer.add_blank_page(width=720, height=540)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


def test_models_verbatim_and_slide_fields():
    """Verify that LectureSection and LectureStudyGuide support verbatim, simple explanation, practical example, and slide fields."""
    section = LectureSection(
        section_number=1,
        topic_title="Signal Sampling & Nyquist Theorem",
        source_reference="00:05:00–00:15:00",
        detailed_explanation="The sampling theorem states that fs must be at least twice the maximum frequency.",
        key_bullet_points=["fs >= 2 * fmax to prevent aliasing."],
        doctor_exact_wording="Doctor said: 'If you do not sample at twice the maximum signal frequency, you will get aliasing!'",
        simple_explanation="Think of a movie showing a car's wheels spinning backwards when recorded too slowly.",
        practical_example="Recording high-definition audio at 44.1 kHz to capture sounds up to 20 kHz without distortion."
    )
    assert section.doctor_exact_wording is not None
    assert "Doctor said" in section.doctor_exact_wording
    assert "movie showing a car" in section.simple_explanation
    assert "44.1 kHz" in section.practical_example

    guide = LectureStudyGuide(
        course_name="Digital Signal Processing",
        lecture_title="Sampling & Reconstruction",
        executive_summary="Overview of sampling and discrete time reconstruction.",
        sections=[section],
        exam_readiness_section=[],
        full_transcript_english="Doctor discussed sampling rates and Nyquist criterion.",
        slides_covered_start=1,
        slides_covered_end=18,
        notes_reference="Slides 1–18 of 40 (Covered in lecture)"
    )
    assert guide.slides_covered_start == 1
    assert guide.slides_covered_end == 18
    assert "Slides 1–18" in guide.notes_reference


def test_slice_pdf_pages_no_25_cap(sample_multi_page_pdf, tmp_path):
    """Verify that slice_pdf_pages on a 40-page deck does not default or cap at 25."""
    # When neither start nor end is given, full 40 slides should be reported
    sliced_p, label = slice_pdf_pages(sample_multi_page_pdf, start_page=None, end_page=None, output_dir=tmp_path)
    assert "40 slides" in label
    assert "25" not in label

    # When start is 1 and end is omitted, it should span to 40, not 25
    sliced_p, label = slice_pdf_pages(sample_multi_page_pdf, start_page=1, end_page=None, output_dir=tmp_path)
    assert "40 slides" in label
    assert "25" not in label

    # When explicit user boundaries are given (e.g. 1 to 12), respect exactly 1 to 12
    sliced_p, label = slice_pdf_pages(sample_multi_page_pdf, start_page=1, end_page=12, output_dir=tmp_path)
    assert "Slides 1–12 of 40" in label
    reader = pypdf.PdfReader(str(sliced_p))
    assert len(reader.pages) == 12


def test_pipeline_demo_with_verbatim_explained(tmp_path):
    """Verify that the end-to-end pipeline processes in verbatim_explained mode and produces a valid PDF."""
    result = process_lecture(
        audio_path=None,
        notes_path=None,
        use_sample_demo=True,
        study_mode="verbatim_explained",
        custom_output_filename=str(tmp_path / "test_verbatim_output.pdf")
    )
    assert result["success"] is True
    assert Path(result["pdf_path"]).exists()
    assert Path(result["pdf_path"]).stat().st_size > 5000

    # Ensure mock guide has verbatim and simple explanation fields populated
    sec = result["guide"]["sections"][0]
    assert sec.get("doctor_exact_wording") is not None
    assert sec.get("simple_explanation") is not None
    assert sec.get("practical_example") is not None


def test_pipeline_demo_with_custom_deck_no_25_cap(sample_multi_page_pdf, tmp_path):
    """Verify that when a 40-page slide deck is provided to pipeline without end_slide, it doesn't claim 25."""
    result = process_lecture(
        audio_path=None,
        notes_path=sample_multi_page_pdf,
        start_slide=1,
        end_slide=None,
        use_sample_demo=True,
        study_mode="detailed",
        custom_output_filename=str(tmp_path / "test_deck_output.pdf")
    )
    assert result["success"] is True
    notes_ref = result.get("notes_reference") or ""
    # Must report 40 slides, NOT 25
    assert "of 40" in notes_ref
    assert "of 25" not in notes_ref


def test_pdf_builder_verbatim_cards(tmp_path):
    """Verify PDFStudyGuideBuilder correctly renders doctor exact words, simple explanation, and practical example cards."""
    guide = get_sample_bilingual_lecture_guide()
    out_pdf = tmp_path / "builder_verbatim_test.pdf"
    builder = PDFStudyGuideBuilder(guide, output_filename=str(out_pdf))
    built_path = builder.build()
    assert built_path.exists()
    assert built_path.stat().st_size > 5000


def test_api_endpoint_accepts_verbatim_explained(test_client):
    """Verify that POST /api/process_audio accepts study_mode='verbatim_explained' and launches demo."""
    resp = test_client.post(
        "/api/process_audio",
        data={
            "demo_mode": "true",
            "study_mode": "verbatim_explained",
            "include_diagrams": "true",
            "include_exam_questions": "true",
            "include_transcript": "true",
        },
        headers={"origin": "http://127.0.0.1:8000"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "job_id" in data


def test_api_endpoint_rejects_invalid_study_mode(test_client):
    """Verify that POST /api/process_audio rejects unknown study modes."""
    resp = test_client.post(
        "/api/process_audio",
        data={
            "demo_mode": "true",
            "study_mode": "invalid_mode_xyz",
        },
        headers={"origin": "http://127.0.0.1:8000"}
    )
    assert resp.status_code == 400
    assert "Study mode must be detailed, revision, exam, or verbatim_explained." in resp.text
