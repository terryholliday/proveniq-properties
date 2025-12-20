"""User model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.org import OrgMembership
    from app.models.lease import TenantAccess
    from app.models.inspection import Inspection


class User(Base):
    """User account linked to Firebase Auth."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    firebase_uid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    org_memberships: Mapped[list["OrgMembership"]] = relationship(
        "OrgMembership", back_populates="user", cascade="all, delete-orphan"
    )
    tenant_access: Mapped[list["TenantAccess"]] = relationship(
        "TenantAccess", back_populates="user", cascade="all, delete-orphan"
    )
    inspections_created: Mapped[list["Inspection"]] = relationship(
        "Inspection", back_populates="created_by", foreign_keys="Inspection.created_by_id"
    )
