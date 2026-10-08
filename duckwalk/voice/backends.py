"""Where the duck's LLM runs. Only the duck's replies use this; the nudge, summary and brief stay on Ollama.

    DUCK_BACKEND=ollama    (default) Ollama, model DUCK_MODEL or OLLAMA_MODEL
    DUCK_BACKEND=llamacpp  the fine-tuned model served locally by llama-server (offline), at LLAMACPP_URL
    DUCK_BACKEND=tinker    the fine-tuned model sampled from Tinker's servers (cloud), checkpoint path in DUCK_MODEL

Every backend returns an iterable of text chunks with `first_token_s`, `input_tokens` and `output_tokens`.
"""

import json
import time

import httpx
import sentry_sdk

from duckwalk import config
from duckwalk.activities import llm

TEMPERATURE = 0.7
MAX_TOKENS = 150
_tinker_samplers: dict = {}


class OpenAIStream:
    """Streaming /v1/chat/completions against a local llama-server (thinking turned off)."""

    def __init__(self, messages: list[dict], timeout_s: float = 120.0) -> None:
        self.messages, self.timeout_s = messages, timeout_s
        self.input_tokens = self.output_tokens = 0
        self.first_token_s: float | None = None

    def __iter__(self):
        model = f"{config.DUCK_MODEL or 'duck'} (llama.cpp)"
        with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {model}") as span:
            span.set_tag("duckwalk.stage", "duck")
            span.set_data("gen_ai.system", "llama.cpp")
            span.set_data("gen_ai.request.model", model)
            start = time.monotonic()
            body = {"messages": self.messages, "stream": True, "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
                    "chat_template_kwargs": {"enable_thinking": False}, "stream_options": {"include_usage": True}}
            try:
                with httpx.stream("POST", f"{config.LLAMACPP_URL}/v1/chat/completions", json=body, timeout=self.timeout_s) as res:
                    if res.is_error:
                        raise llm.OllamaError(f"duck: llama-server returned {res.status_code}: {res.read().decode()[:200]}")
                    for line in res.iter_lines():
                        if not line.startswith("data: ") or line == "data: [DONE]":
                            continue
                        chunk = json.loads(line[6:])
                        if chunk.get("usage"):
                            self.input_tokens = chunk["usage"].get("prompt_tokens", 0)
                            self.output_tokens = chunk["usage"].get("completion_tokens", 0)
                        for choice in chunk.get("choices", []):
                            text = choice.get("delta", {}).get("content") or ""
                            if text:
                                if self.first_token_s is None:
                                    self.first_token_s = time.monotonic() - start
                                yield text
            except httpx.HTTPError as e:
                span.set_status("unavailable")
                raise llm.OllamaError(f"duck: llama-server not reachable at {config.LLAMACPP_URL} ({e.__class__.__name__})") from None
            span.set_data("gen_ai.usage.input_tokens", self.input_tokens)
            span.set_data("gen_ai.usage.output_tokens", self.output_tokens)
            span.set_status("ok")


class TinkerStream:
    """One-shot sampling from Tinker, presented as a stream of one chunk. Cloud: the text leaves this machine."""

    def __init__(self, messages: list[dict]) -> None:
        self.messages = messages
        self.input_tokens = self.output_tokens = 0
        self.first_token_s: float | None = None

    def __iter__(self):
        sampler = _sampler(config.DUCK_MODEL)
        with sentry_sdk.start_span(op="gen_ai.chat", name="chat duck (tinker)") as span:
            span.set_tag("duckwalk.stage", "duck")
            span.set_data("gen_ai.system", "tinker")
            out = sampler(self.messages)
            self.first_token_s = out["total_s"]
            self.input_tokens, self.output_tokens = out["input_tokens"], out["output_tokens"]
            span.set_data("gen_ai.usage.input_tokens", self.input_tokens)
            span.set_data("gen_ai.usage.output_tokens", self.output_tokens)
            span.set_status("ok")
        yield out["text"]


def _sampler(path: str):
    if path not in _tinker_samplers:
        import sys

        sys.path.insert(0, str(config.ROOT / "ml" / "tinker"))
        from tinker_sampler import TinkerSampler

        _tinker_samplers[path] = TinkerSampler(path, base_only=False)
    return _tinker_samplers[path]


def duck_stream(messages: list[dict]):
    if config.DUCK_BACKEND == "llamacpp":
        return OpenAIStream(messages)
    if config.DUCK_BACKEND == "tinker":
        return TinkerStream(messages)
    if config.DUCK_BACKEND != "ollama":
        raise llm.OllamaError(f"unknown DUCK_BACKEND={config.DUCK_BACKEND!r} (use ollama, llamacpp or tinker)")
    return llm.ChatStream(messages, stage="duck", model=config.DUCK_MODEL or None)
