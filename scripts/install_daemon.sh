#!/usr/bin/env bash
# Install the DuckWalk background pipeline for the current user:
#   1. `dw` on PATH (symlink in ~/.local/bin)
#   2. the DuckWalk Signals extension in Cursor (or VS Code: EDITOR_CLI=code)
#   3. systemd user services: the Temporal dev server (state in ~/.duckwalk/temporal.db),
#      the WalkSession worker and the signal daemon
# Undo: scripts/install_daemon.sh --uninstall
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNITS="$HOME/.config/systemd/user"
SERVICES="duckwalk-temporal duckwalk-worker duckwalk-daemon"
EDITOR_CLI="${EDITOR_CLI:-cursor}"

if [ "${1:-}" = "--uninstall" ]; then
  for s in $SERVICES; do
    systemctl --user disable --now "$s.service" 2>/dev/null || true
    rm -f "$UNITS/$s.service"
  done
  rm -f "$HOME/.local/bin/dw"
  systemctl --user daemon-reload
  "$EDITOR_CLI" --uninstall-extension duckwalk.duckwalk-signals 2>/dev/null || true
  echo "Uninstalled. Data in ~/.duckwalk was kept."
  exit 0
fi

echo "==> dw -> ~/.local/bin/dw"
mkdir -p "$HOME/.local/bin"
ln -sf "$ROOT/.venv/bin/dw" "$HOME/.local/bin/dw"

echo "==> Editor extension ($EDITOR_CLI)"
(cd "$ROOT/editor/vscode" && npx --yes @vscode/vsce package --skip-license --out "$ROOT/vendor/duckwalk-signals.vsix")
"$EDITOR_CLI" --install-extension "$ROOT/vendor/duckwalk-signals.vsix" --force

# unit NAME DESCRIPTION EXEC_START [AFTER]
unit() {
  {
    echo "[Unit]"
    echo "Description=$2"
    if [ -n "${4:-}" ]; then echo "After=$4"; echo "Wants=$4"; fi
    echo
    echo "[Service]"
    echo "WorkingDirectory=$ROOT"
    echo "ExecStart=$3"
    echo "Environment=PYTHONUNBUFFERED=1"
    echo "Restart=on-failure"
    echo "RestartSec=5"
    echo
    echo "[Install]"
    echo "WantedBy=default.target"
  } > "$UNITS/$1.service"
}

echo "==> systemd user services"
mkdir -p "$UNITS" "$HOME/.duckwalk"
unit duckwalk-temporal "DuckWalk Temporal dev server (persistent)" \
  "$ROOT/vendor/bin/temporal server start-dev --db-filename $HOME/.duckwalk/temporal.db --log-level warn"
unit duckwalk-worker "DuckWalk WalkSession worker" \
  "$ROOT/.venv/bin/python -m duckwalk.workflows.worker" duckwalk-temporal.service
unit duckwalk-daemon "DuckWalk signal daemon (records 5-minute work windows)" \
  "$ROOT/.venv/bin/python -m duckwalk.daemon"
systemctl --user daemon-reload
for s in $SERVICES; do
  systemctl --user enable "$s.service"
  systemctl --user restart "$s.service"
done

echo
echo "Done. Reload Cursor so the extension activates."
echo "UI:     http://localhost:8233"
echo "Logs:   journalctl --user -u duckwalk-daemon -u duckwalk-worker -f"
echo "Label:  uv run python -m duckwalk.daemon.label"
