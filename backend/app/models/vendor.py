"""Vendor model — enhanced with Service module capabilities."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Boolean, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import VendorSpecialty, VendorStatus, VendorType

if TYPE_CHECKING:
    from app.models.org import Organization
    from app.models.maintenance import MaintenanceTicket
    from app.models.vendor_license import VendorLicense
    from app.models.vendor_review import VendorReview


class Vendor(Base):
    """A vendor/contractor for maintenance work (org-scoped).
    
    Enhanced with proveniq-service capabilities:
    - License verification
    - Rating/review system
    - Service area/capabilities
    - Pricing
    """

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
    
    # Business info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[VendorType] = mapped_column(
        SQLEnum(VendorType),
        default=VendorType.INDIVIDUAL,
        nullable=False,
    )
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
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    service_area: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # GeoJSON or zip codes
    
    # Status (enhanced from is_active)
    status: Mapped[VendorStatus] = mapped_column(
        SQLEnum(VendorStatus),
        default=VendorStatus.PENDING,
        nullable=False,
    )
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Verification (from Service)
    insurance_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    background_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Ratings (computed from reviews)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    
    # Pricing (INTEGER CENTS)
    hourly_rate_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minimum_fee_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Capabilities
    service_types: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)  # MAINTENANCE, REPAIR, etc.
    
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
    licenses: Mapped[list["VendorLicense"]] = relationship(
        "VendorLicense", back_populates="vendor", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["VendorReview"]] = relationship(
        "VendorReview", back_populates="vendor", cascade="all, delete-orphan"
    )
