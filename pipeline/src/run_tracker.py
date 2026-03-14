"""Pipeline run tracker — logs execution history to pipeline_runs table."""

import json
import uuid
from datetime import datetime, timezone

import asyncpg


class RunTracker:
    """Track pipeline run lifecycle in Supabase."""

    async def start(self, pool: asyncpg.Pool, stage: str) -> str:
        """Record a new pipeline run. Returns the run ID."""
        run_id = str(uuid.uuid4())
        await pool.execute(
            "INSERT INTO pipeline_runs (id, stage, status) VALUES ($1, $2, 'running')",
            run_id, stage,
        )
        return run_id

    async def complete(self, pool: asyncpg.Pool, run_id: str, stats: dict) -> None:
        """Mark a run as completed with stats."""
        await pool.execute(
            "UPDATE pipeline_runs SET completed_at = NOW(), status = 'completed', "
            "stats = $1 WHERE id = $2",
            json.dumps(stats), run_id,
        )

    async def fail(self, pool: asyncpg.Pool, run_id: str, error: str) -> None:
        """Mark a run as failed with error message."""
        await pool.execute(
            "UPDATE pipeline_runs SET completed_at = NOW(), status = 'failed', "
            "error_message = $1 WHERE id = $2",
            error[:2000], run_id,
        )
