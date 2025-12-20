"""Jobs outbox model for async side effects with unique_scope de-duplication."""

import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, DateTime, Text, Integer, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import JobStatus


class JobsOutbox(Base):
    """Async job queue with idempotency via unique_scope.
    
    All async side effects MUST use this table. No fire-and-forget tasks.
    unique_scope ensures de-duplication (e.g., "verify_hash:evidence:{id}").
    """

    __tablename__ = "jobs_outbox"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Job type (e.g., "verify_hash", "generate_certificate", "send_notification")
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Job payload (JSON)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    # Status
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    
    # Unique scope for idempotency (e.g., "verify_hash:evidence:abc123")
    # UNIQUE constraint prevents duplicate jobs for same scope
    unique_scope: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    
    # Retry tracking
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Scheduling
    run_after: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_jobs_outbox_pending', 'status', 'run_after', 
              postgresql_where=(status == JobStatus.PENDING)),
    )
