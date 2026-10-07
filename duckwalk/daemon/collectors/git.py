"""Commits landed across the repos in DUCKWALK_REPOS."""

import subprocess
from pathlib import Path

from duckwalk import config


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10)
    return out.stdout.strip() if out.returncode == 0 else ""


def collect(start: float, end: float) -> dict:
    """Your own commits (by committer email) with a commit time in [start, end), on any branch."""
    commits = 0
    for repo in config.REPOS:
        email = _git(repo, "config", "user.email")
        times = _git(repo, "log", "--all", f"--committer={email}", "--format=%ct",
                     f"--since=@{int(start)}", f"--until=@{int(end)}")
        commits += sum(start <= int(t) < end for t in times.split())
    return {"commits": commits}


def repo_for(path: str | None) -> str | None:
    """The watched repo that contains `path`, if any."""
    if not path:
        return None
    for repo in config.REPOS:
        if Path(path).resolve().is_relative_to(repo.resolve()):
            return str(repo)
    return None
