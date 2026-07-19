from __future__ import annotations

import asyncio
import logging
import signal

from sqlalchemy import select

from mnemos.core.config import settings
from mnemos.core.db import SessionLocal, close_database
from mnemos.models import Query
from mnemos.services.query_execution import execute_query_background

logger = logging.getLogger(__name__)


async def claim_next_query() -> str | None:
    async with SessionLocal() as db:
        query = await db.scalar(
            select(Query)
            .where(Query.status == "queued")
            .order_by(Query.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if query is None:
            return None
        query.status = "running"
        await db.commit()
        return query.id


async def run_worker() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    logger.info("Mnemos query worker started")
    try:
        while not stop.is_set():
            query_id = await claim_next_query()
            if query_id is None:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_seconds)
                except TimeoutError:
                    continue
            else:
                await execute_query_background(query_id)
    finally:
        await close_database()
        logger.info("Mnemos query worker stopped")


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
