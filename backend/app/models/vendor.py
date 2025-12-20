"""Vendor model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import VendorSpecialty

if TYPE_CHECKING:
    from app.models.org import Organization
    from app.models.maintenance import MaintenanceTicket


class Vendor(Base):
    """A vendor/contractor for maintenance work (org-scoped)."""

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[VendorSpecialty] = mapped_column(
        SQLEnum(VendorSpecialty),
        default=VendorSpecialty.GENERAL,
        nullable=False,
    )
    
    # Contact info
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Address
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    org: Mapped["Organization"] = relationship("Organization", back_populates="vendors")
    maintenance_tickets: Mapped[list["MaintenanceTicket"]] = relationship(
        "MaintenanceTicket", back_populates="assigned_vendor"
    )
