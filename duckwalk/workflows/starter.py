"""Start WalkSessions and send fake phone signals.

    uv run python -m duckwalk.workflows.starter trigger [--fixture failing_test] [--repo PATH]
    uv run python -m duckwalk.workflows.starter signal [WORKFLOW_ID]     # fake "phone is moving"
    uv run python -m duckwalk.workflows.starter status [WORKFLOW_ID]
    uv run python -m duckwalk.workflows.starter result [WORKFLOW_ID]     # wait for and print the result

WORKFLOW_ID defaults to the most recent WalkSession.
"""

import argparse
import asyncio
import json
import sys
import time

from temporalio.client import Client
from temporalio.service import RPCError

from duckwalk import config
from duckwalk.workflows.walk_session import TASK_QUEUE, WalkSession


async def _client() -> Client:
    return await Client.connect(config.TEMPORAL_ADDRESS)


async def running_session(client: Client) -> str | None:
    async for wf in client.list_workflows("WorkflowType = 'WalkSession' AND ExecutionStatus = 'Running'"):
        return wf.id
    return None


async def latest_session(client: Client) -> str | None:
    async for wf in client.list_workflows("WorkflowType = 'WalkSession'"):
        return wf.id  # newest first
    return None


async def start_walk_session(ctx: dict) -> str | None:
    """Start a session unless one is already running. Returns the workflow id, or None if skipped."""
    client = await _client()
    if await running_session(client):
        return None
    wf_id = f"walk-{ctx.get('window_id') or 'manual'}-{int(time.time())}"
    await client.start_workflow(WalkSession.run, ctx, id=wf_id, task_queue=TASK_QUEUE)
    return wf_id


async def _main(args) -> int:
    client = await _client()
    if args.cmd == "trigger":
        ctx = {"window_id": args.window_id, "repo": args.repo, "fixture": args.fixture}
        if args.voice_script:
            ctx["voice_script"] = json.loads(open(args.voice_script).read())
        if args.move_timeout:
            ctx["move_timeout_s"] = args.move_timeout
        wf_id = await start_walk_session(ctx)
        if wf_id is None:
            print(f"skipped: session {await running_session(client)} is already running", file=sys.stderr)
            return 1
        print(wf_id)
        return 0

    wf_id = args.workflow_id or await latest_session(client)
    if not wf_id:
        print("no WalkSession found", file=sys.stderr)
        return 1
    handle = client.get_workflow_handle(wf_id)
    if args.cmd == "signal":
        await handle.signal(WalkSession.phone_moving)
        print(f"{wf_id}: phone_moving sent")
    elif args.cmd == "status":
        desc = await handle.describe()
        stage = "-"
        if desc.status.name == "RUNNING":
            try:
                stage = await asyncio.wait_for(handle.query(WalkSession.status), timeout=5)
            except (asyncio.TimeoutError, RPCError):
                stage = "unknown (no worker running to answer the query)"
        print(f"{wf_id}: {desc.status.name}, stage {stage}")
    elif args.cmd == "result":
        print(json.dumps(await handle.result(), indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trigger", help="start a WalkSession now")
    t.add_argument("--fixture", help="use an eval/fixtures state instead of capturing the repo")
    t.add_argument("--repo", help="repo to capture (default: this repo)")
    t.add_argument("--window-id", type=int, help="windows.db row to record the outcome on")
    t.add_argument("--voice-script", help="JSON list of things the user says; replaces the mic and speaker (testing)")
    t.add_argument("--move-timeout", type=int, help="seconds to wait for movement (testing; default 600)")
    for name in ("signal", "status", "result"):
        sub.add_parser(name).add_argument("workflow_id", nargs="?")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
