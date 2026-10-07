"""Shared settings, read from the environment and an optional `.env` file."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal KEY=VALUE loader. Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")  # local default; e.g. gemma4:31b-cloud for Ollama cloud
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

TEMPORAL_BIN = VENDOR / "bin" / "temporal"
WHISPER_BIN = VENDOR / "whisper.cpp" / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = VENDOR / "whisper.cpp" / "models" / "ggml-base.en.bin"
PIPER_VOICE_DIR = VENDOR / "piper-voices"
PIPER_VOICE = "en_US-lessac-medium"
