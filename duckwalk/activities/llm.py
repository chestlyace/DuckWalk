"""Ollama client wrapper. Every call is a Sentry `gen_ai.chat` span.

Spans carry metadata only (model, stage, token counts, timings), never the
prompt or the response text.
"""

import json
import time
from dataclasses import dataclass

import httpx
import sentry_sdk

from duckwalk import config


class OllamaError(Exception):
    """Ollama was unreachable, timed out, or returned an error."""


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_s: float


def generate(prompt: str, *, stage: str, model: str | None = None, timeout_s: float = 60.0) -> LLMResult:
    """Send one non-streaming prompt to Ollama. `stage` names the pipeline step (e.g. "summary")."""
    model = model or config.OLLAMA_MODEL
    with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {model}") as span:
        span.set_tag("duckwalk.stage", stage)
        span.set_data("gen_ai.system", "ollama")
        span.set_data("gen_ai.operation.name", "chat")
        span.set_data("gen_ai.request.model", model)
        try:
            res = httpx.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "think": False},
                timeout=timeout_s,
            )
        except httpx.TimeoutException:
            span.set_status("deadline_exceeded")
            raise OllamaError(f"{stage}: Ollama timed out after {timeout_s:.0f}s") from None
        except httpx.HTTPError as e:
            span.set_status("unavailable")
            raise OllamaError(f"{stage}: Ollama not reachable at {config.OLLAMA_URL} ({e.__class__.__name__})") from None
        if res.is_error:
            span.set_status("internal_error")
            raise OllamaError(f"{stage}: Ollama returned {res.status_code}: {res.json().get('error', res.text)[:200]}")

        body = res.json()
        result = LLMResult(
            text=body["response"].strip(),
            model=body.get("model", model),
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
            duration_s=body.get("total_duration", 0) / 1e9,
        )
        span.set_data("gen_ai.response.model", result.model)
        span.set_data("gen_ai.usage.input_tokens", result.input_tokens)
        span.set_data("gen_ai.usage.output_tokens", result.output_tokens)
        span.set_data("gen_ai.usage.total_tokens", result.input_tokens + result.output_tokens)
        span.set_status("ok")
        return result


class ChatStream:
    """Streaming /api/chat call. Iterate for text chunks; stats are filled in as it runs.

    One `gen_ai.chat` span covers the whole stream, tagged like `generate`.
    """

    def __init__(self, messages: list[dict], *, stage: str, model: str | None = None,
                 timeout_s: float = 60.0, max_tokens: int = 150):
        self.messages, self.stage, self.timeout_s, self.max_tokens = messages, stage, timeout_s, max_tokens
        self.model = model or config.OLLAMA_MODEL
        self.input_tokens = self.output_tokens = 0
        self.first_token_s: float | None = None  # seconds from request start to the first text chunk

    def __iter__(self):
        with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {self.model}") as span:
            span.set_tag("duckwalk.stage", self.stage)
            span.set_data("gen_ai.system", "ollama")
            span.set_data("gen_ai.operation.name", "chat")
            span.set_data("gen_ai.request.model", self.model)
            start = time.monotonic()
            try:
                with httpx.stream(
                    "POST", f"{config.OLLAMA_URL}/api/chat", timeout=self.timeout_s,
                    json={"model": self.model, "messages": self.messages, "stream": True, "think": False,
                          "options": {"num_predict": self.max_tokens}},
                ) as res:
                    if res.is_error:
                        span.set_status("internal_error")
                        raise OllamaError(f"{self.stage}: Ollama returned {res.status_code}: {res.read().decode()[:200]}")
                    for line in res.iter_lines():
                        if not line:
                            continue
                        body = json.loads(line)
                        text = body.get("message", {}).get("content", "")
                        if text:
                            if self.first_token_s is None:
                                self.first_token_s = time.monotonic() - start
                                span.set_data("duckwalk.first_token_s", round(self.first_token_s, 3))
                            yield text
                        if body.get("done"):
                            self.input_tokens = body.get("prompt_eval_count", 0)
                            self.output_tokens = body.get("eval_count", 0)
            except httpx.TimeoutException:
                span.set_status("deadline_exceeded")
                raise OllamaError(f"{self.stage}: Ollama timed out after {self.timeout_s:.0f}s") from None
            except httpx.HTTPError as e:
                span.set_status("unavailable")
                raise OllamaError(f"{self.stage}: Ollama not reachable at {config.OLLAMA_URL} ({e.__class__.__name__})") from None
            span.set_data("gen_ai.usage.input_tokens", self.input_tokens)
            span.set_data("gen_ai.usage.output_tokens", self.output_tokens)
            span.set_data("gen_ai.usage.total_tokens", self.input_tokens + self.output_tokens)
            span.set_status("ok")
