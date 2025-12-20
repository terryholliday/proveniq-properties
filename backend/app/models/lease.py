"""Lease and TenantAccess models."""

import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Date, ForeignKey, Enum as SQLEnum, Text, BigInteger, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LeaseStatus, LeaseType

if TYPE_CHECKING:
    from app.models.property import Unit
    from app.models.user import User
    from app.models.inspection import Inspection


class Lease(Base):
    """A lease agreement for a unit."""

    __tablename__ = "leases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Lease type and status
    lease_type: Mapped[LeaseType] = mapped_column(
        SQLEnum(LeaseType),
        default=LeaseType.RESIDENTIAL_GROSS,
        nullable=False,
    )
    status: Mapped[LeaseStatus] = mapped_column(
        SQLEnum(LeaseStatus),
        default=LeaseStatus.DRAFT,
        nullable=False,
        index=True,
    )
    
    # Dates
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Money (ALL INTEGER CENTS - BIGINT)
    rent_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deposit_amount_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    
    # Commercial NNN fields (REQUIRED if lease_type='commercial_nnn')
    # pro_rata_share_bps: basis points (1-10000) representing tenant's share of CAM
    pro_rata_share_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cam_budget_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Tenant info (before tenant account exists)
    tenant_email: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tenant_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Magic link invite
    invite_token_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    invite_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invite_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    unit: Mapped["Unit"] = relationship("Unit", back_populates="leases")
    tenant_access: Mapped[list["TenantAccess"]] = relationship(
        "TenantAccess", back_populates="lease", cascade="all, delete-orphan"
    )
    inspections: Mapped[list["Inspection"]] = relationship(
        "Inspection", back_populates="lease", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "(pro_rata_share_bps IS NULL) OR (pro_rata_share_bps > 0 AND pro_rata_share_bps <= 10000)",
            name="ck_lease_pro_rata_share_bps_range",
        ),
    )


class TenantAccess(Base):
    """Links a user (tenant) to a lease they have access to."""

    __tablename__ = "tenant_access"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    is_primary: Mapped[bool] = mapped_column(default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    lease: Mapped["Lease"] = relationship("Lease", back_populates="tenant_access")
    user: Mapped["User"] = relationship("User", back_populates="tenant_access")
