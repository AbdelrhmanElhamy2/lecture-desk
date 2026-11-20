"""Regression tests for the Lecture Desk usability, bug-fix, and anti-AI-slop overhaul."""
import os
os.environ["LECTUREAI_TESTING"] = "1"

import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from config import OUTPUT_DIR
from mock_generator import get_sample_bilingual_lecture_guide
from pdf_builder import PDFStudyGuideBuilder


def test_lecturer_hint_form_field_is_passed_to_pipeline(tmp_path):
    """Verify lecturer_hint is bound as a Form field (not silently ignored as a query param)."""
    import app as app_module
    client = TestClient(app)
    with patch.object(app_module, "HISTORY_FILE", tmp_path / "isolated_history.json"), \
         patch("app.process_lecture") as mock_pipeline:
        mock_pipeline.return_value = {
            "success": True,
            "is_demo": True,
            "pdf_path": str(OUTPUT_DIR / "mock_lecturer.pdf"),
            "pdf_filename": "mock_lecturer.pdf",
            "course_name": "Signals & Systems",
            "lecture_title": "Fourier Analysis",
            "lecturer_name": "Dr. Nadia Mansour",
            "executive_summary": "Summary",
            "sections_count": 1,
            "exam_questions_count": 1,
            "alerts_count": 0,
            "diagrams_count": 0,
            "guide": {},
        }
        resp = client.post(
            "/api/process_audio",
            data={
                "demo_mode": "true",
                "study_mode": "detailed",
                "course_hint": "Signals & Systems",
                "lecturer_hint": "Dr. Nadia Mansour",
            },
            headers={"origin": "http://127.0.0.1:8000"},
        )
        assert resp.status_code == 200
        assert mock_pipeline.called
        assert mock_pipeline.call_args.kwargs["lecturer_hint"] == "Dr. Nadia Mansour"
        assert mock_pipeline.call_args.kwargs["course_hint"] == "Signals & Systems"


def test_inline_view_pdf_endpoint_and_path_traversal_guard():
    """Verify /api/view/{filename} serves PDFs inline and blocks traversal/missing files."""
    client = TestClient(app)
    fname = f"test_inline_view_{uuid.uuid4().hex[:8]}.pdf"
    fpath = OUTPUT_DIR / fname
    fpath.write_bytes(b"%PDF-1.4 inline preview test")
    try:
        resp = client.get(f"/api/view/{fname}")
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("application/pdf")
        assert "inline" in resp.headers.get("content-disposition", "").lower()

        resp_missing = client.get("/api/view/does_not_exist_12345.pdf")
        assert resp_missing.status_code == 404

        resp_traversal = client.get("/api/view/..%2F..%2Fapp.py")
        assert resp_traversal.status_code == 404
    finally:
        fpath.unlink(missing_ok=True)


def test_ui_assets_are_free_of_ai_slop_tokens_and_keep_required_contracts():
    """Verify templates/index.html, static/styles.css, and static/app.js remove AI-slop clichés."""
    html = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    js = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")
    combined = html + "\n" + css + "\n" + js

    # Zero emojis, sparkles, glassmorphism, neon glow shadows, or Tailwind CDN
    forbidden = [
        "cdn.tailwindcss.com",
        "glass-card",
        "backdrop-blur",
        "shadow-[0_0_",
        "✦", "⚡", "🎓", "🎙", "📑", "➕", "✅", "⚠️", "❌", "⏳", "☀️", "🌙",
    ]
    for token in forbidden:
        assert token not in combined, f"Found forbidden AI-slop token in UI assets: {token!r}"

    # Required DOM contracts & verbatim web rendering
    assert 'id="modelSelect"' in html
    assert 'value="gemini-4-hydrogen"' in html
    assert 'value="gemini-3.8-flash"' in html
    assert 'value="gemini-3.6-flash"' in html
    assert 'value="gemini-3.5-flash-lite"' in html
    assert 'value="gemini-3-flash-preview"' in html
    assert 'value="gemini-3.1-flash-lite"' in html
    assert "/static/app_icon.png?v=5" in html
    assert "Engineering Study Suite" in html
    assert "Professor Exam Highlights" in html
    assert "Professor's Exam Alerts" in html
    assert "doctor_exact_wording" in js
    assert "simple_explanation" in js
    assert "practical_example" in js
    assert ".flac" in js and ".wma" in js


def test_pdf_footer_and_visualizer_palette_updated(tmp_path):
    """Verify PDF uses clean non-AI footer and visualizer palette excludes neon purple/pink."""
    import pypdf
    import visualizer

    assert "#7C3AED" not in visualizer.BOX_PALETTE
    assert "#DB2777" not in visualizer.BOX_PALETTE

    guide = get_sample_bilingual_lecture_guide()
    out_pdf = tmp_path / "footer_check.pdf"
    PDFStudyGuideBuilder(guide, output_filename=str(out_pdf)).build()
    reader = pypdf.PdfReader(str(out_pdf))
    page2_text = reader.pages[1].extract_text() or ""
    assert "Generated by LectureAI" not in page2_text
    assert "Engineering Study Suite" in page2_text


def test_undo_script_list_succeeds():
    """Verify the local rollback CLI utility lists change groups when local backups are present."""
    import pytest

    undo_script = PROJECT_ROOT / "undo_changes.py"
    manifest = PROJECT_ROOT / ".undo_backups" / "2026-11-20_pre_overhaul" / "manifest.json"
    if not undo_script.exists() or not manifest.exists():
        pytest.skip("Local pre-overhaul rollback snapshot not present on fresh clone.")

    proc = subprocess.run(
        [sys.executable, str(undo_script), "--list"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "CHG-02" in proc.stdout
    assert "CHG-03" in proc.stdout
    assert "CHG-05" in proc.stdout
    assert "CHG-06" in proc.stdout


def test_one_click_installers_and_lecture_desk_readme_present():
    """Verify non-technical 1-click launchers and updated Lecture Desk README exist."""
    for filename in ("Start_Lecture_Desk.bat", "Start_Lecture_Desk.command", "start_lecture_desk.sh"):
        path = PROJECT_ROOT / filename
        assert path.is_file(), f"Missing 1-click launcher: {filename}"

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Lecture Desk" in readme
    assert "Start_Lecture_Desk.bat" in readme
    assert "Start_Lecture_Desk.command" in readme
    assert "aistudio.google.com/apikey" in readme
