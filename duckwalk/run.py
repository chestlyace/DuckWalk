"""`dw`: run a build/test command, tee its output to the terminal log and record the exit code.

    dw pytest -x
    dw npm test

Exit code and output are passed through unchanged.
"""

import json
import os
import subprocess
import sys
import time

from duckwalk import config


def main() -> int:
    cmd = sys.argv[1:]
    if not cmd:
        print("usage: dw <command> [args...]", file=sys.stderr)
        return 2
    config.HOME.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with open(config.TERMINAL_LOG, "a", errors="replace") as log:
        log.write(f"\n$ {' '.join(cmd)}\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        except FileNotFoundError:
            print(f"dw: command not found: {cmd[0]}", file=sys.stderr)
            return 127
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        code = proc.wait()
        log.write(f"[exit {code}]\n")
    event = {"ts": start, "end": time.time(), "exit": code, "cmd": cmd[0], "cwd": os.getcwd()}
    with open(config.RUN_EVENTS, "a") as f:
        f.write(json.dumps(event) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
