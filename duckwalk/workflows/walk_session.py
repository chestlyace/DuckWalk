"""WalkSession: breadcrumb -> nudge -> wait for movement -> voice loop -> return brief.

Durable by design: Temporal retries failed activities (e.g. Ollama down), and a
worker restart resumes the session where it left off.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from duckwalk.activities import walk

TASK_QUEUE = "duckwalk"
MOVE_TIMEOUT = timedelta(minutes=10)

# LLM steps: 5 attempts, 30 s each (duckwalk-phases.md, Phase 3 task 3).
# Backoff 2s, 4s, 8s, 16s gives Ollama about 30 s to come back before the session fails.
LLM = dict(
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=2), backoff_coefficient=2.0),
)
QUICK = dict(start_to_close_timeout=timedelta(seconds=10), retry_policy=RetryPolicy(maximum_attempts=3))


@workflow.defn
class WalkSession:
    def __init__(self) -> None:
        self.moving = False
        self.stage = "starting"

    @workflow.signal
    def phone_moving(self) -> None:
        self.moving = True

    @workflow.query
    def status(self) -> str:
        return self.stage

    @workflow.run
    async def run(self, ctx: dict) -> dict:
        window_id = ctx.get("window_id")

        self.stage = "breadcrumb"
        crumb = await workflow.execute_activity(walk.capture_breadcrumb, ctx, **LLM)
        self.stage = "nudge"
        nudge = await workflow.execute_activity(walk.gemma_nudge, crumb, **LLM)
        await workflow.execute_activity(walk.push_to_phone, nudge, **QUICK)
        await workflow.execute_activity(walk.record_outcome, {"window_id": window_id, "nudged": True, "walked": None}, **QUICK)

        self.stage = "waiting_for_movement"
        try:
            timeout = timedelta(seconds=ctx["move_timeout_s"]) if ctx.get("move_timeout_s") else MOVE_TIMEOUT
            await workflow.wait_condition(lambda: self.moving, timeout=timeout)
        except asyncio.TimeoutError:
            self.stage = "done_no_walk"
            await workflow.execute_activity(walk.record_outcome, {"window_id": window_id, "nudged": True, "walked": False}, **QUICK)
            return {"walked": False, "nudge": nudge, "summary": crumb["summary"], "brief": None}

        self.stage = "voice_loop"
        transcript = await workflow.execute_activity(
            walk.voice_loop, ctx, start_to_close_timeout=timedelta(minutes=45), retry_policy=RetryPolicy(maximum_attempts=3)
        )
        self.stage = "brief"
        brief = await workflow.execute_activity(walk.gemma_brief, {"summary": crumb["summary"], "transcript": transcript}, **LLM)
        await workflow.execute_activity(walk.record_outcome, {"window_id": window_id, "nudged": True, "walked": True}, **QUICK)
        self.stage = "done"
        return {"walked": True, "nudge": nudge, "summary": crumb["summary"], "brief": brief}
