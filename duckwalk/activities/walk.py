"""Temporal activities for the WalkSession workflow.

Each activity runs in its own Sentry transaction, so its LLM spans are grouped
under it. LLM failures raise OllamaError, which Temporal retries.
"""

import functools
import json
import sqlite3
from pathlib import Path

import sentry_sdk
from temporalio import activity

from duckwalk import config
from duckwalk.activities import breadcrumb, llm

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
FIXTURES = config.ROOT / "eval" / "fixtures" / "states.json"
LLM_HTTP_TIMEOUT_S = 25  # below the 30s start-to-close timeout, so a hung call fails as a clean OllamaError

# Phase 3 stand-in for the Phase 4 voice loop: a plausible walk monologue about the failing_test fixture.
CANNED_TRANSCRIPT = (
    "Okay so the invoice total is off by one cent, 50.98 instead of 50.97. "
    "Three items at 19.99 is 59.97, minus fifteen percent. I think the discount is rounded per item "
    "and then summed, so each item rounds up a little and it adds up to an extra cent. "
    "Or maybe it's float, the discount is 0.15 as a float, not a Decimal, so the multiplication isn't exact. "
    "Actually the test passes a float discount, so both could be true. "
    "The quickest check is to print each line total before summing and see where the cent appears."
)


def traced(fn):
    """Run an activity inside a Sentry transaction named after it."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with sentry_sdk.start_transaction(op="duckwalk.activity", name=fn.__name__) as tx:
            tx.set_tag("temporal.attempt", activity.info().attempt)
            return fn(*args, **kwargs)
    return wrapper


@activity.defn
@traced
def capture_breadcrumb(ctx: dict) -> dict:
    """Snapshot the working state (or load a fixture) and compress it into the 60-word summary."""
    if ctx.get("fixture"):
        state = next(f["state"] for f in json.loads(FIXTURES.read_text()) if f["id"] == ctx["fixture"])
    else:
        state = breadcrumb.capture_breadcrumb(ctx.get("repo") or str(config.ROOT))
    summary = llm.generate(breadcrumb.render_prompt("summary", state), stage="summary", timeout_s=LLM_HTTP_TIMEOUT_S)
    return {"state": state, "summary": summary.text}


@activity.defn
@traced
def gemma_nudge(crumb: dict) -> str:
    result = llm.generate(breadcrumb.render_prompt("nudge", crumb["state"]), stage="nudge", timeout_s=LLM_HTTP_TIMEOUT_S)
    return result.text.strip().strip('"').strip()


@activity.defn
@traced
def push_to_phone(nudge: str) -> None:
    """Phase 3 stand-in: print to the worker console. Phase 6 replaces this with a real push."""
    activity.logger.info("PUSH TO PHONE: %s", nudge)
    print(f"\n📱  {nudge}\n", flush=True)


@activity.defn
@traced
def voice_loop(ctx: dict) -> str:
    """Phase 3 stand-in: return a canned transcript. Phase 4 replaces this with the real voice loop."""
    return CANNED_TRANSCRIPT


@activity.defn
@traced
def gemma_brief(inputs: dict) -> str:
    prompt = (PROMPTS / "brief.txt").read_text()
    prompt = prompt.replace("{breadcrumb}", inputs["summary"]).replace("{transcript}", inputs["transcript"])
    return llm.generate(prompt, stage="brief", timeout_s=LLM_HTTP_TIMEOUT_S).text


@activity.defn
@traced
def record_outcome(outcome: dict) -> None:
    """Write nudged/walked for the window that triggered the session. Manual triggers have no window."""
    if outcome.get("window_id") is None:
        return
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute(
            "UPDATE windows SET nudged = ?, walked = ? WHERE id = ?",
            (outcome["nudged"], outcome["walked"], outcome["window_id"]),
        )


ALL = [capture_breadcrumb, gemma_nudge, push_to_phone, voice_loop, gemma_brief, record_outcome]
