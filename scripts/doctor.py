"""Check every DuckWalk service and print a pass/fail table.

Usage:
    uv run python scripts/doctor.py                 # check everything
    uv run python scripts/doctor.py --sentry-test   # also send a test error to Sentry
"""

import argparse
import asyncio
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from duckwalk import config  # noqa: E402

GEMMA_PROMPT = "A developer has been stuck on the same failing test for 90 minutes. Write a one-line walk nudge."


def check_ollama() -> tuple[bool, str]:
    try:
        tags = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).json()
    except httpx.HTTPError as e:
        return False, f"not reachable at {config.OLLAMA_URL} ({e.__class__.__name__})"
    names = {m["name"] for m in tags.get("models", [])}
    if config.OLLAMA_MODEL not in names:
        return False, f"{config.OLLAMA_MODEL} not pulled (run: ollama pull {config.OLLAMA_MODEL})"
    return True, f"{config.OLLAMA_MODEL} available"


def check_gemma() -> tuple[bool, str]:
    try:
        res = httpx.post(
            f"{config.OLLAMA_URL}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": GEMMA_PROMPT, "stream": False},
            timeout=180,
        )
    except httpx.HTTPError as e:
        return False, f"generate failed ({e.__class__.__name__})"
    if res.is_error:
        return False, f"generate failed: {res.json().get('error', res.text)[:120]}"
    reply = res.json()["response"].strip().replace("\n", " ")
    return bool(reply), f'"{reply[:90]}"'


def check_temporal() -> tuple[bool, str]:
    from temporalio.client import Client

    async def connect() -> None:
        await asyncio.wait_for(Client.connect(config.TEMPORAL_ADDRESS), timeout=5)

    try:
        asyncio.run(connect())
    except Exception as e:
        return False, f"no server at {config.TEMPORAL_ADDRESS} (start: vendor/bin/temporal server start-dev) [{e.__class__.__name__}]"
    try:
        httpx.get("http://localhost:8233", timeout=5).raise_for_status()
    except httpx.HTTPError:
        return False, f"server up at {config.TEMPORAL_ADDRESS}, but UI not loading on :8233"
    return True, f"server at {config.TEMPORAL_ADDRESS}, UI at http://localhost:8233"


def check_whisper() -> tuple[bool, str]:
    sample = config.VENDOR / "whisper.cpp" / "samples" / "jfk.wav"
    for path in (config.WHISPER_BIN, config.WHISPER_MODEL, sample):
        if not path.exists():
            return False, f"missing {path.relative_to(config.ROOT)} (run scripts/setup.sh)"
    out = subprocess.run(
        [str(config.WHISPER_BIN), "-m", str(config.WHISPER_MODEL), "-f", str(sample), "-nt"],
        capture_output=True, text=True, timeout=120,
    )
    text = out.stdout.strip()
    if out.returncode != 0 or "country" not in text.lower():
        return False, "transcription of samples/jfk.wav failed"
    return True, f'base.en: "{text[:60]}..."'


def check_piper() -> tuple[bool, str]:
    voice = config.PIPER_VOICE_DIR / f"{config.PIPER_VOICE}.onnx"
    if not voice.exists():
        return False, f"missing voice {voice.relative_to(config.ROOT)} (run scripts/setup.sh)"
    from piper import PiperVoice

    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        with wave.open(f.name, "wb") as wav:
            PiperVoice.load(str(voice)).synthesize_wav("Time for a walk.", wav)
        with wave.open(f.name, "rb") as wav:
            seconds = wav.getnframes() / wav.getframerate()
    if seconds <= 0:
        return False, "synthesis produced no audio"
    return True, f"{config.PIPER_VOICE}: synthesized {seconds:.1f}s of audio"


def check_sentry(send_test: bool) -> tuple[bool, str]:
    from duckwalk.telemetry import init_sentry

    if not init_sentry():
        return False, "SENTRY_DSN not set in .env"
    if not send_test:
        return True, "initialised (use --sentry-test to send a test error)"
    import sentry_sdk

    try:
        raise RuntimeError("DuckWalk doctor: Sentry test error")
    except RuntimeError as e:
        event_id = sentry_sdk.capture_exception(e)
    sentry_sdk.flush(timeout=10)
    return True, f"test error sent, event id {event_id}. Check the Sentry dashboard"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sentry-test", action="store_true", help="send a test error to Sentry")
    args = parser.parse_args()

    checks = [
        ("Ollama", check_ollama),
        ("Gemma reply", check_gemma),
        ("Temporal", check_temporal),
        ("whisper.cpp", check_whisper),
        ("Piper", check_piper),
        ("Sentry", lambda: check_sentry(args.sentry_test)),
    ]
    all_ok = True
    for name, check in checks:
        try:
            ok, detail = check()
        except Exception as e:  # a crashing check is a failing check, not a crashing doctor
            ok, detail = False, f"{e.__class__.__name__}: {e}"
        all_ok &= ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:<12} {detail}", flush=True)
    print("\nAll services healthy." if all_ok else "\nSome checks failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
