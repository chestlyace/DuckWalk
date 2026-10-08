"""Sample the duck from a Tinker-hosted model (the untuned base, or a fine-tuned checkpoint).

Used by run_eval.py. Needs TINKER_API_KEY (set in .env). This runs on Tinker's servers, not locally.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from duckwalk import config  # noqa: E402,F401  (loads .env so TINKER_API_KEY is in the environment)

import tinker  # noqa: E402
from tinker_cookbook.model_info import get_recommended_renderer_names  # noqa: E402
from tinker_cookbook.renderers import get_renderer, get_text_content  # noqa: E402

TEMPERATURE = 0.7
MAX_TOKENS = 150  # same cap as the deployed voice loop


def renderer_name(base_model: str) -> str:
    """The recommended renderer with thinking disabled, matching how the voice loop calls its model."""
    names = get_recommended_renderer_names(base_model)
    return next((n for n in names if n.endswith("disable_thinking")), names[0])


class TinkerSampler:
    def __init__(self, model: str, base_only: bool = False) -> None:
        service = tinker.ServiceClient()
        if base_only:
            self.client = service.create_sampling_client(base_model=model)
            base = model
        else:
            self.client = service.create_sampling_client(model_path=model)
            base = self.client.get_base_model()
        self.renderer = get_renderer(renderer_name(base), self.client.get_tokenizer())

    def __call__(self, messages: list[dict]) -> dict:
        prompt = self.renderer.build_generation_prompt(messages)
        params = tinker.SamplingParams(max_tokens=MAX_TOKENS, temperature=TEMPERATURE, stop=self.renderer.get_stop_sequences())
        t0 = time.monotonic()
        response = self.client.sample(prompt=prompt, num_samples=1, sampling_params=params).result()
        total = time.monotonic() - t0
        tokens = response.sequences[0].tokens
        message, _ = self.renderer.parse_response(tokens)
        return {"text": get_text_content(message).strip(), "first_token_s": None, "total_s": total,
                "input_tokens": prompt.length, "output_tokens": len(tokens)}
