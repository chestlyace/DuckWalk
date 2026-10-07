"""Speech-to-text with whisper.cpp (runs offline)."""

import re
import subprocess
import tempfile
import wave

import numpy as np

from duckwalk import config
from duckwalk.voice.audio import SAMPLE_RATE

# whisper tags non-speech like [BLANK_AUDIO], (wind blowing), *footsteps*
_NON_SPEECH = re.compile(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*")


class WhisperError(Exception):
    pass


def transcribe(audio: np.ndarray) -> str:
    """Transcribe int16 16 kHz mono audio. Returns "" if nothing intelligible was said."""
    for path in (config.WHISPER_BIN, config.WHISPER_MODEL):
        if not path.exists():
            raise WhisperError(f"missing {path.relative_to(config.ROOT)} (run scripts/setup.sh)")
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        with wave.open(f.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(audio.tobytes())
        out = subprocess.run(
            [str(config.WHISPER_BIN), "-m", str(config.WHISPER_MODEL), "-f", f.name, "-nt", "-np", "-l", "en", "-t", "4"],
            capture_output=True, text=True, timeout=120,
        )
    if out.returncode != 0:
        raise WhisperError(f"whisper-cli failed: {out.stderr.strip()[-200:]}")
    return " ".join(_NON_SPEECH.sub(" ", out.stdout).split())
