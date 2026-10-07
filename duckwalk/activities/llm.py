"""Ollama client wrapper. Every call is a Sentry `gen_ai.chat` span.

Spans carry metadata only (model, stage, token counts, timings), never the
prompt or the response text.
"""

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
