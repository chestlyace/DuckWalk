"""Breadcrumb: snapshot where the developer is, then compress it with the LLM."""

import subprocess
from pathlib import Path

from duckwalk import config
from duckwalk.activities import llm

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
LOG_TAIL_LINES = 40


def _git(repo: str, *args: str) -> str:
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=10)
    return out.stdout.strip("\n") if out.returncode == 0 else ""


def _tail(path: str, lines: int) -> str:
    if not path:
        return ""
    p = Path(path).expanduser()
    if not p.is_file():
        return ""
    return "\n".join(p.read_text(errors="replace").splitlines()[-lines:])


def editor_open_files() -> list[str]:
    """Stub until the editor collector exists (Phase 2)."""
    return []


def capture_breadcrumb(repo: str, terminal_log: str | None = None) -> dict:
    """`terminal_log` overrides DUCKWALK_TERMINAL_LOG from .env."""
    return {
        "branch": _git(repo, "branch", "--show-current"),
        "diff": _git(repo, "diff", "--stat"),
        "last_error": _tail(terminal_log or config.TERMINAL_LOG, LOG_TAIL_LINES),
        "open_files": editor_open_files(),
    }


def format_state(state: dict) -> str:
    """Render a breadcrumb as prompt text. Empty fields are stated as unknown, not dropped."""
    files = ", ".join(state.get("open_files") or []) or "unknown"
    return (
        f"Branch: {state.get('branch') or 'unknown'}\n"
        f"Uncommitted changes (git diff --stat):\n{state.get('diff') or 'none'}\n"
        f"Last terminal output:\n{state.get('last_error') or 'no error captured'}\n"
        f"Open files: {files}"
    )


def render_prompt(name: str, state: dict) -> str:
    return (PROMPTS / f"{name}.txt").read_text().replace("{state}", format_state(state))


def summarize(state: dict) -> llm.LLMResult:
    return llm.generate(render_prompt("summary", state), stage="summary")


def nudge(state: dict) -> llm.LLMResult:
    result = llm.generate(render_prompt("nudge", state), stage="nudge")
    result.text = result.text.strip().strip('"').strip()
    return result
