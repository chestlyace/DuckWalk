#!/usr/bin/env bash
# One-command local setup for DuckWalk (Linux x86_64).
# Needs: uv, ollama, git, cmake, a C++ compiler, curl. Flutter is set up separately.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor"
mkdir -p "$VENDOR/bin" "$VENDOR/piper-voices"
cd "$ROOT"

echo "==> Python 3.12 environment and dependencies"
uv python install 3.12
uv sync

echo "==> Gemma via Ollama"
ollama pull "${OLLAMA_MODEL:-gemma4:e4b}"

echo "==> Temporal CLI"
if [ ! -x "$VENDOR/bin/temporal" ]; then
  curl -fsSL "https://temporal.download/cli/archive/latest?platform=linux&arch=amd64" -o "$VENDOR/temporal.tgz"
  tar -xzf "$VENDOR/temporal.tgz" -C "$VENDOR/bin" temporal
  rm "$VENDOR/temporal.tgz"
fi

echo "==> whisper.cpp + base.en model"
if [ ! -d "$VENDOR/whisper.cpp" ]; then
  git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$VENDOR/whisper.cpp"
fi
cmake -S "$VENDOR/whisper.cpp" -B "$VENDOR/whisper.cpp/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$VENDOR/whisper.cpp/build" -j"$(nproc)" --config Release
if [ ! -f "$VENDOR/whisper.cpp/models/ggml-base.en.bin" ]; then
  bash "$VENDOR/whisper.cpp/models/download-ggml-model.sh" base.en
fi

echo "==> Piper voice"
uv run python -m piper.download_voices --data-dir "$VENDOR/piper-voices" en_US-lessac-medium

[ -f .env ] || cp .env.example .env

echo
echo "Done. Start Temporal in another terminal:  vendor/bin/temporal server start-dev"
echo "Then run:                                  uv run python scripts/doctor.py"
