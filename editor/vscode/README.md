# DuckWalk Signals

Logs local editing signals for the DuckWalk stuck detector to `~/.duckwalk/editor.jsonl`: edit, undo, redo, save and focus events, each with a timestamp and file path. File contents are never logged, and nothing leaves your machine.

Installed by `scripts/install_daemon.sh`.
