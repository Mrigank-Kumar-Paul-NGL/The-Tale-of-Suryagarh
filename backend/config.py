"""Local configuration. Override with environment variables if needed."""
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Minimal .env reader (KEY=VALUE lines). Real environment variables take precedence. Never prints values."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv(ROOT / ".env")
WEB_DIR = ROOT / "web"
SAVE_FILE = Path(os.environ.get("GAME_SAVE", ROOT / "saves" / "save.json"))

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))

# Qwen is served by the local Ollama app (http://127.0.0.1:11434).
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen3:8b-q4_K_M")
_raw = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if "://" not in _raw:
    _raw = "http://" + _raw
OLLAMA_URL = _raw.rstrip("/")

# The game must never talk to a remote model. Refuse anything not on this machine.
_host = (urlparse(OLLAMA_URL).hostname or "").lower()
if _host in ("0.0.0.0", ""):
    OLLAMA_URL = OLLAMA_URL.replace("0.0.0.0", "127.0.0.1")
elif _host not in ("127.0.0.1", "localhost", "::1"):
    raise SystemExit(f"OLLAMA_HOST must point at this machine, got {OLLAMA_URL!r}")

QWEN_TIMEOUT_S = 180       # first request may need to load the model into memory
QWEN_MAX_TOKENS = 700
QWEN_TEMPERATURE = 0.8

# ---------- Remote play (hosted frontend + HTTPS tunnel to this laptop) ----------
# Requests that arrive through a tunnel must carry this key in the X-Game-Key header.
# Set it only in your shell (never in code or the frontend), e.g.  export GAME_ACCESS_KEY="$(openssl rand -hex 16)"
ACCESS_KEY = os.environ.get("GAME_ACCESS_KEY", "").strip()
ACCESS_KEY_MIN_LEN = 16
# Browser origins allowed to call the API cross-origin, comma-separated; "*" wildcards allowed,
# e.g. GAME_ALLOWED_ORIGINS="https://suryagarh-*-w1ther.vercel.app"
ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in os.environ.get("GAME_ALLOWED_ORIGINS", "").split(",") if o.strip()]
LOCAL_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

# ---------- Gemini fallback (only used when local Qwen is unavailable; needs internet) ----------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()   # never log or return this
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_BASE_URL = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
if not (GEMINI_BASE_URL.startswith("https://generativelanguage.googleapis.com/")
        or urlparse(GEMINI_BASE_URL).hostname in ("127.0.0.1", "localhost")):  # local mock for testing only
    raise SystemExit("GEMINI_BASE_URL must be the official Gemini API endpoint.")
GEMINI_TIMEOUT_S = 60

# Which model narrates: "gemini" (default, online) or "qwen" (local, with Gemini as fallback).
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
if LLM_PROVIDER not in ("gemini", "qwen"):
    raise SystemExit("LLM_PROVIDER must be 'gemini' or 'qwen'.")

# ---------- Cloud deployment (Supabase saves + public web play) ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "").strip()   # server-only; never log or return
if SUPABASE_URL and not SUPABASE_URL.startswith("https://"):
    raise SystemExit("SUPABASE_URL must be an https:// URL.")
CLOUD = bool(SUPABASE_URL and SUPABASE_SECRET_KEY)
# Public play: anyone with the link can play (each browser gets its own save). On for the cloud build.
PUBLIC_PLAY = CLOUD or os.environ.get("PUBLIC_PLAY", "") == "1"
# Abuse limits (window seconds, max hits) — model calls cost money.
RATE_LIMITS = {
    "narrate_player": (3600, 240),
    "narrate_ip": (3600, 600),
    "new_ip": (3600, 30),
}

# ---------- Hosted Qwen fallback (OpenRouter) ----------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()   # never log or return this
QWEN_CLOUD_MODEL = os.environ.get("QWEN_CLOUD_MODEL", "qwen/qwen3-30b-a3b-instruct-2507").strip()
