"""Calls to the teacher/judge model (gemma4:31b-cloud through Ollama), with retries for flaky cloud connections."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from duckwalk.activities import llm  # noqa: E402

TEACHER_MODEL = "gemma4:31b-cloud"


def ask(messages: list[dict], *, temperature: float = 0.8, max_tokens: int = 400, json_mode: bool = False,
        tries: int = 6) -> str:
    """One teacher call. Retries with growing waits (3, 6, 12, 24, 48 s), long enough for the cloud's
    "too many concurrent requests" (429) limit to clear."""
    for attempt in range(tries):
        try:
            return llm.chat(messages, stage="teacher", model=TEACHER_MODEL, temperature=temperature,
                            max_tokens=max_tokens, json_mode=json_mode).text
        except llm.OllamaError:
            if attempt == tries - 1:
                raise
            time.sleep(3 * 2 ** attempt)


def judge(prompt: str) -> str:
    return ask([{"role": "user", "content": prompt}], temperature=0, max_tokens=120, json_mode=True)
