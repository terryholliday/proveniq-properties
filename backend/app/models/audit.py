"""AuditLog and MasonLog models."""

import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import AuditAction


class AuditLog(Base):
    """Immutable audit log for compliance tracking."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    action: Mapped[AuditAction] = mapped_column(
        SQLEnum(AuditAction),
        nullable=False,
        index=True,
    )
    
    # Resource being acted upon
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    # Details
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MasonLog(Base):
    """Log of Mason AI advisory decisions (for auditing AI recommendations)."""

    __tablename__ = "mason_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # What Mason was asked to do
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Resource context
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    # Input to Mason
    input_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    # Mason's output
    output_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    # Disclaimer (always present per guardrails)
    disclaimer: Mapped[str] = mapped_column(
        Text,
        default="This is a non-binding advisory estimate. Actual costs may vary.",
        nullable=False,
    )
    
    # Processing time (ms)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
