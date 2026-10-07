# DuckWalk
A local-first AI companion that notices when a developer is stuck, gets them away from the screen, and helps them think out loud while they walk. The screen is the shortest part of the experience.

## Setup

Linux x86_64. Requires [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com), git, cmake, a C++ compiler and curl.

```bash
bash scripts/setup.sh
```

This installs Python 3.12 and the dependencies, pulls `gemma4:e4b` (local default), and puts the Temporal CLI, whisper.cpp (`base.en`) and the Piper voice (`en_US-lessac-medium`) under `vendor/` (gitignored). It also creates `.env` from `.env.example`. Add your `SENTRY_DSN` there. To use Ollama's cloud instead of a local model, set `OLLAMA_MODEL=gemma4:31b-cloud` (requires `ollama signin` and `ollama pull gemma4:31b-cloud`).

Then check everything:

```bash
vendor/bin/temporal server start-dev     # separate terminal; UI at http://localhost:8233
uv run python scripts/doctor.py          # pass/fail table for every service
uv run python scripts/doctor.py --sentry-test   # also sends a test error to Sentry
```

The Flutter client lives in `phone/` (`cd phone && flutter run` with a phone connected).

## Signals and the stuck detector

```bash
bash scripts/install_daemon.sh        # dw on PATH, Cursor extension, systemd user service (--uninstall reverses it)
dw pytest -x                          # run builds/tests through dw so failures are counted and logged
uv run python -m duckwalk.daemon.label            # one-key labeling: s = stuck, f = flow, k = skip, q = quit
uv run python ml/train_detector.py                # held-out metrics + learning curve -> ml/data/
uv run python -m duckwalk.daemon.detector --synthetic stuck   # P(stuck) for a synthetic window
```

Set `DUCKWALK_REPOS` and `TABPFN_TOKEN` in `.env` first. Runtime data stays in `~/.duckwalk` (editor and run event logs, terminal log, `windows.db`), and the editor extension logs file paths only, never contents.

## Walk sessions (Temporal)

`scripts/install_daemon.sh` also runs the Temporal dev server (state kept in `~/.duckwalk/temporal.db`) and the WalkSession worker as systemd user services. With them running:

```bash
S="uv run python -m duckwalk.workflows.starter"
$S trigger --fixture failing_test     # start a session (or --repo PATH to capture a real repo)
$S status                             # stage of the latest session
$S signal                             # fake "phone is moving"
$S result                             # wait for and print the nudge, summary and brief
bash scripts/drill_ollama_kill.sh     # failure drill: stop Ollama mid-session (needs sudo)
```

Set `DUCKWALK_AUTO_NUDGE=1` in `.env` to let the daemon start sessions when P(stuck) crosses the threshold. The Temporal UI is at http://localhost:8233.

## Voice duck

A hands-free Socratic conversation: mic → Silero VAD → whisper.cpp → Gemma (streamed) → Piper → speaker. The duck asks questions and never gives the answer. Say "end walk" to finish (30 minute cap).

```bash
uv run python -m duckwalk.voice --mic-test                 # does the mic, VAD and whisper hear you?
uv run python -m duckwalk.voice --fixture failing_test     # talk to the duck from the laptop
uv run python -m duckwalk.voice --script eval/voice/scripts/rounding.json   # scripted user, no sound (regression + latency)
uv run python -m duckwalk.voice.report eval/voice/transcripts               # per-turn latency table
```

Transcripts and per-turn metrics are saved to `~/.duckwalk/transcripts/`. Piper is the offline default. Set `DUCKWALK_TTS=elevenlabs`, `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` in `.env` to opt in to ElevenLabs, which sends the duck's replies to ElevenLabs' servers. `starter trigger --voice-script FILE` runs a whole walk session with a scripted user.
