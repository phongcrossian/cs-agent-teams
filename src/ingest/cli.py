"""
Re-ingest CLI entrypoint (D-16).

Usage:
    python -m src.ingest.cli re-ingest [--run-id RUN_ID]

This is the manual re-export → idempotent re-ingest command described in D-16.
Run whenever Phase-1 snapshots are updated to rebuild the knowledge store.
The ingest is idempotent: unchanged content is a no-op, changed prose re-embeds.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def _run_ingest(run_id: str) -> None:
    """Open asyncpg pool, run IngestPipeline.ingest_all, print summary."""
    import asyncpg
    from pgvector.asyncpg import register_vector
    from src.ingest.pipeline import IngestPipeline

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://csbot:csbot@localhost:5432/csbot"
    )
    # asyncpg expects postgresql:// (not postgresql+asyncpg://)
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    async def _init_conn(conn):
        try:
            await register_vector(conn)
        except Exception:
            pass  # pgvector not installed — graceful skip

    logger.info("Connecting to database …")
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5, init=_init_conn)
    try:
        logger.info("Starting ingest run_id=%s", run_id)
        pipeline = IngestPipeline(pool)
        counts = await pipeline.ingest_all(run_id=run_id)
        print("\n=== Ingest complete ===")
        print(f"  run_id:           {run_id}")
        print(f"  kb_chunk rows:    {counts['kb_chunk']}")
        print(f"  policy_threshold: {counts['policy_threshold']}")
        print(f"  code_map:         {counts['code_map']}")
        print(f"  template_library: {counts['template_library']}")
    finally:
        await pool.close()


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args and dispatch sub-command."""
    parser = argparse.ArgumentParser(
        prog="python -m src.ingest.cli",
        description="Knowledge ingest pipeline — build / re-sync the centralized RAG store.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Sub-command: re-ingest
    reingest_parser = subparsers.add_parser(
        "re-ingest",
        help="Re-ingest all Phase-1 snapshots into knowledge.* tables (idempotent).",
    )
    reingest_parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Identifier for this ingest run (default: current UTC timestamp). "
            "Used as snapshot_version on all inserted/updated rows."
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "re-ingest":
        run_id = args.run_id or datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        asyncio.run(_run_ingest(run_id))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
