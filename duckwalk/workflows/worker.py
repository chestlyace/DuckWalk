"""Temporal worker for WalkSession.

    uv run python -m duckwalk.workflows.worker   # the systemd service runs this
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from duckwalk import config
from duckwalk.activities import walk
from duckwalk.telemetry import init_sentry
from duckwalk.workflows.walk_session import TASK_QUEUE, WalkSession


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_sentry()
    client = await Client.connect(config.TEMPORAL_ADDRESS)
    with ThreadPoolExecutor(max_workers=8) as pool:
        worker = Worker(client, task_queue=TASK_QUEUE, workflows=[WalkSession], activities=walk.ALL, activity_executor=pool)
        logging.info("worker listening on task queue %r at %s", TASK_QUEUE, config.TEMPORAL_ADDRESS)
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
