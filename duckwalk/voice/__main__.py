"""Talk to the duck from the laptop (test harness for the voice loop).

    uv run python -m duckwalk.voice                          # live mic and speaker
    uv run python -m duckwalk.voice --fixture failing_test   # start from a fixture's breadcrumb summary
    uv run python -m duckwalk.voice --script eval/voice/scripts/rounding.json   # scripted user, no sound
    uv run python -m duckwalk.voice --mic-test               # check that the mic, VAD and whisper hear you

Say "end walk" to finish. Transcripts go to ~/.duckwalk/transcripts/.
"""

import argparse
import json
import sys
import time
from datetime import datetime

import sentry_sdk

from duckwalk import config
from duckwalk.activities import llm
from duckwalk.telemetry import init_sentry
from duckwalk.voice import stt
from duckwalk.voice.audio import LiveMic, ScriptedMic
from duckwalk.voice.duck import Duck
from duckwalk.voice.tts import Speaker, make_tts
from duckwalk.voice.vad import Listener

DEFAULT_SUMMARY = ("Doing: Fixing an invoice rounding bug.\n"
                   "Failing: test_total_with_discount expects 50.97 but gets 50.98.\n"
                   "Next: Investigate where the cent is added.")


def mic_test() -> int:
    mic = LiveMic()
    mic.start()
    print("Say something short (waiting up to 15 s)...")
    utt = Listener(mic).hear(silence_timeout_s=15)
    mic.stop()
    if utt is None:
        print("No speech detected. Check the input device (DUCKWALK_AUDIO_IN) and your mic volume.")
        return 1
    t0 = time.monotonic()
    text = stt.transcribe(utt.audio)
    print(f"Heard {utt.speech_s:.1f}s of speech; whisper took {time.monotonic() - t0:.1f}s and heard: {text!r}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixture", help="seed the duck with the summary of an eval/fixtures state")
    parser.add_argument("--summary", help="seed the duck with this text")
    parser.add_argument("--script", help="JSON list of things the user says; replaces the mic")
    parser.add_argument("--play", action="store_true", help="with --script, also play the duck's voice")
    parser.add_argument("--max-minutes", type=float, help=f"conversation limit (default {config.VOICE_MAX_MINUTES})")
    parser.add_argument("--name", help="transcript name (default: timestamp)")
    parser.add_argument("--mic-test", action="store_true")
    args = parser.parse_args()
    init_sentry()
    if args.mic_test:
        return mic_test()

    summary = args.summary or DEFAULT_SUMMARY
    if args.fixture:
        from duckwalk.activities import breadcrumb
        fixtures = json.loads((config.ROOT / "eval" / "fixtures" / "states.json").read_text())
        state = next(f["state"] for f in fixtures if f["id"] == args.fixture)
        summary = llm.generate(breadcrumb.render_prompt("summary", state), stage="summary").text

    scripted = bool(args.script)
    mic = ScriptedMic(json.loads(open(args.script).read())) if scripted else LiveMic()
    speaker = Speaker(make_tts(), play=args.play or not scripted)
    name = args.name or datetime.now().strftime("%Y%m%d-%H%M%S")
    duck = Duck(summary, mic, speaker, transcript_path=config.TRANSCRIPTS_DIR / f"{name}.json",
                max_seconds=args.max_minutes * 60 if args.max_minutes else None)
    print(f"Starting. Say \"{config.STOP_PHRASE}\" to finish.\n" if not scripted else "Running scripted conversation...\n")
    with sentry_sdk.start_transaction(op="duckwalk.cli", name="voice"):
        result = duck.run()
    sentry_sdk.flush(timeout=10)
    print(result["transcript"])
    print(f"\nEnded: {result['ended']} after {result['turns']} turns. Saved {config.TRANSCRIPTS_DIR / (name + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
