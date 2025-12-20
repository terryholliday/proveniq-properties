"""MaintenanceTicket model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import MaintenanceStatus, VendorSpecialty

if TYPE_CHECKING:
    from app.models.property import Unit
    from app.models.vendor import Vendor
    from app.models.user import User


class MaintenanceTicket(Base):
    """A maintenance request/ticket."""

    __tablename__ = "maintenance_tickets"

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
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Assignment (vendor OR org member, not both)
    assigned_vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_org_member_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Ticket details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[MaintenanceStatus] = mapped_column(
        SQLEnum(MaintenanceStatus),
        default=MaintenanceStatus.OPEN,
        nullable=False,
        index=True,
    )
    
    # Categorization
    category: Mapped[Optional[VendorSpecialty]] = mapped_column(
        SQLEnum(VendorSpecialty),
        nullable=True,
    )
    
    # Priority (1-5, 1=highest)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    
    # Cost estimate (INTEGER CENTS - advisory only)
    maintenance_cost_estimate_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Mason AI triage results
    mason_triage_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    mason_triaged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Scheduling
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Tenant visibility
    is_tenant_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    unit: Mapped["Unit"] = relationship("Unit", back_populates="maintenance_tickets")
    assigned_vendor: Mapped[Optional["Vendor"]] = relationship(
        "Vendor", back_populates="maintenance_tickets"
    )
