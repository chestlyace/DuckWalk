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
