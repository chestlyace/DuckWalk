#!/usr/bin/env bash
# Install the DuckWalk signal pipeline for the current user:
#   1. `dw` on PATH (symlink in ~/.local/bin)
#   2. the DuckWalk Signals extension in Cursor (or VS Code: EDITOR_CLI=code)
#   3. a systemd user service that runs the daemon
# Undo: scripts/install_daemon.sh --uninstall
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT="$HOME/.config/systemd/user/duckwalk-daemon.service"
EDITOR_CLI="${EDITOR_CLI:-cursor}"

if [ "${1:-}" = "--uninstall" ]; then
  systemctl --user disable --now duckwalk-daemon.service 2>/dev/null || true
  rm -f "$UNIT" "$HOME/.local/bin/dw"
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

echo "==> systemd user service"
mkdir -p "$(dirname "$UNIT")"
cat > "$UNIT" <<EOF
[Unit]
Description=DuckWalk signal daemon (records 5-minute work windows)

[Service]
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/python -m duckwalk.daemon
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now duckwalk-daemon.service

echo
echo "Done. Reload Cursor so the extension activates."
echo "Logs:   journalctl --user -u duckwalk-daemon -f"
echo "Label:  uv run python -m duckwalk.daemon.label"
