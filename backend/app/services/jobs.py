"""Jobs outbox service for async side effects.

Golden Master v2.3.1: All async side effects MUST use jobs_outbox.
No fire-and-forget tasks.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.jobs import JobsOutbox
from app.models.enums import JobStatus


class JobsService:
    """Service for managing async jobs via outbox pattern."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        unique_scope: str,
        run_after: Optional[datetime] = None,
    ) -> Optional[uuid.UUID]:
        """Enqueue a job with unique_scope de-duplication.
        
        If a job with the same unique_scope already exists, returns None.
        Otherwise returns the new job ID.
        
        Args:
            job_type: Type of job (e.g., "verify_hash", "generate_certificate")
            payload: Job payload as JSON-serializable dict
            unique_scope: Unique identifier for de-duplication
            run_after: Optional delay before job should run
            
        Returns:
            Job ID if created, None if duplicate scope exists
        """
        job_id = uuid.uuid4()
        
        # Use INSERT ... ON CONFLICT DO NOTHING for idempotency
        stmt = insert(JobsOutbox).values(
            id=job_id,
            type=job_type,
            payload=payload,
            status=JobStatus.PENDING,
            unique_scope=unique_scope,
            run_after=run_after or datetime.utcnow(),
        ).on_conflict_do_nothing(index_elements=['unique_scope'])
        
        result = await self.db.execute(stmt)
        
        # rowcount will be 0 if conflict occurred
        if result.rowcount == 0:
            return None
        
        return job_id

    async def enqueue_verify_hash(
        self,
        evidence_id: uuid.UUID,
        object_path: str,
        claimed_hash: str,
    ) -> Optional[uuid.UUID]:
        """Enqueue SHA-256 verification job for evidence."""
        return await self.enqueue(
            job_type="verify_hash",
            payload={
                "evidence_id": str(evidence_id),
                "object_path": object_path,
                "claimed_hash": claimed_hash,
            },
            unique_scope=f"verify_hash:evidence:{evidence_id}",
        )

    async def enqueue_generate_certificate(
        self,
        inspection_id: uuid.UUID,
        content_hash: str,
    ) -> Optional[uuid.UUID]:
        """Enqueue certificate PDF generation job."""
        return await self.enqueue(
            job_type="generate_certificate",
            payload={
                "inspection_id": str(inspection_id),
                "content_hash": content_hash,
            },
            unique_scope=f"generate_certificate:inspection:{inspection_id}",
        )

    async def claim_pending_jobs(
        self,
        job_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[JobsOutbox]:
        """Claim pending jobs for processing.
        
        Atomically updates status to PROCESSING and returns jobs.
        """
        query = (
            select(JobsOutbox)
            .where(
                JobsOutbox.status == JobStatus.PENDING,
                JobsOutbox.run_after <= datetime.utcnow(),
            )
        )
        
        if job_type:
            query = query.where(JobsOutbox.type == job_type)
        
        query = query.order_by(JobsOutbox.run_after).limit(limit)
        
        result = await self.db.execute(query)
        jobs = result.scalars().all()
        
        if not jobs:
            return []
        
        # Update status to PROCESSING
        job_ids = [j.id for j in jobs]
        await self.db.execute(
            update(JobsOutbox)
            .where(JobsOutbox.id.in_(job_ids))
            .values(
                status=JobStatus.PROCESSING,
                started_at=datetime.utcnow(),
                attempts=JobsOutbox.attempts + 1,
            )
        )
        
        return jobs

    async def complete_job(self, job_id: uuid.UUID) -> None:
        """Mark job as completed."""
        await self.db.execute(
            update(JobsOutbox)
            .where(JobsOutbox.id == job_id)
            .values(
                status=JobStatus.COMPLETED,
                completed_at=datetime.utcnow(),
            )
        )

    async def fail_job(
        self,
        job_id: uuid.UUID,
        error: str,
        dead_letter: bool = False,
    ) -> None:
        """Mark job as failed.
        
        If dead_letter=True or max attempts reached, moves to DEAD_LETTER.
        Otherwise, resets to PENDING for retry.
        """
        # Get current job state
        result = await self.db.execute(
            select(JobsOutbox).where(JobsOutbox.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            return
        
        if dead_letter or job.attempts >= job.max_attempts:
            new_status = JobStatus.DEAD_LETTER
        else:
            new_status = JobStatus.PENDING
        
        await self.db.execute(
            update(JobsOutbox)
            .where(JobsOutbox.id == job_id)
            .values(
                status=new_status,
                last_error=error,
            )
        )
