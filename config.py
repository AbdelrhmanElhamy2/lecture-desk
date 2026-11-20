import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()

# Directories
UPLOAD_DIR = BASE_DIR / "uploads"
ASSETS_DIR = BASE_DIR / "generated_assets"
OUTPUT_DIR = BASE_DIR / "output_pdfs"

for folder in [UPLOAD_DIR, ASSETS_DIR, OUTPUT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# API Configuration (Current Free Tier Gemini models only)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
FREE_TIER_GEMINI_MODELS = (
    "gemini-4-hydrogen",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
)
PRIMARY_GEMINI_MODEL = FREE_TIER_GEMINI_MODELS[0]
FALLBACK_GEMINI_MODEL = FREE_TIER_GEMINI_MODELS[1]
ALLOWED_GEMINI_MODELS = frozenset(FREE_TIER_GEMINI_MODELS)

def default_gemini_model(configured_model: str | None = None) -> str:
    """Resolve the deployment default, allowing only an approved Free Tier override."""
    selected = (configured_model or PRIMARY_GEMINI_MODEL).strip()
    return selected if selected in ALLOWED_GEMINI_MODELS else PRIMARY_GEMINI_MODEL

_configured_model = os.environ.get("GEMINI_MODEL", "").strip()
# Keep old .env files usable, while never allowing obsolete, removed, or paid-only IDs at runtime.
DEFAULT_MODEL = default_gemini_model(_configured_model)

def set_gemini_model(model_name: str) -> None:
    """Set active model, restricted to supported Free Tier Gemini models."""
    global DEFAULT_MODEL
    if model_name not in ALLOWED_GEMINI_MODELS:
        raise ValueError(
            f"Unsupported Gemini model. Choose a supported Free Tier model: {', '.join(FREE_TIER_GEMINI_MODELS)}."
        )
    DEFAULT_MODEL = model_name
    os.environ["GEMINI_MODEL"] = model_name

def resolve_gemini_model(model_name: str | None = None) -> str:
    """Return an approved configured Free Tier model or reject unsupported/paid-only input."""
    selected = (model_name or DEFAULT_MODEL).strip()
    if selected not in ALLOWED_GEMINI_MODELS:
        raise ValueError(
            f"Unsupported Gemini model. Choose a supported Free Tier model: {', '.join(FREE_TIER_GEMINI_MODELS)}."
        )
    return selected

def gemini_model_candidates(model_name: str | None = None) -> list[str]:
    """Return the selected Free Tier model followed by lower-priority Free Tier fallbacks."""
    selected = resolve_gemini_model(model_name)
    idx = FREE_TIER_GEMINI_MODELS.index(selected)
    return list(FREE_TIER_GEMINI_MODELS[idx:])

# Supported Audio Formats
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm", ".wma"}

# Supported Notes & Slides Formats
SUPPORTED_NOTES_EXTS = {".pdf", ".txt", ".md"}

def set_gemini_api_key(key: str) -> None:
    """Save API key to .env and environment."""
    global GEMINI_API_KEY
    GEMINI_API_KEY = key
    os.environ["GEMINI_API_KEY"] = key
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(f"GEMINI_API_KEY={key}\nGEMINI_MODEL={DEFAULT_MODEL}\n")

def get_gemini_api_key() -> str:
    """Return active Gemini API key or empty string."""
    return os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
