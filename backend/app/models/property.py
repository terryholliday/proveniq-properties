"""Property and Unit models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PropertyType, UnitStatus, OccupancyModel

if TYPE_CHECKING:
    from app.models.org import Organization
    from app.models.lease import Lease
    from app.models.maintenance import MaintenanceTicket
    from app.models.booking import Booking


class Property(Base):
    """A property (building/complex) owned/managed by an organization."""

    __tablename__ = "properties"

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
    property_type: Mapped[PropertyType] = mapped_column(
        SQLEnum(PropertyType),
        default=PropertyType.RESIDENTIAL,
        nullable=False,
    )
    
    # STR support: determines inspection cadence and signing semantics
    occupancy_model: Mapped[OccupancyModel] = mapped_column(
        SQLEnum(OccupancyModel),
        default=OccupancyModel.LONG_TERM_RESIDENTIAL,
        nullable=False,
    )
    
    # Address
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(50), default="USA")
    
    # Commercial fields (REQUIRED if property_type in ('commercial', 'mixed'))
    total_leasable_sq_ft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Metadata
    year_built: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    org: Mapped["Organization"] = relationship("Organization", back_populates="properties")
    units: Mapped[list["Unit"]] = relationship(
        "Unit", back_populates="property", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "(property_type = 'residential') OR (total_leasable_sq_ft IS NOT NULL)",
            name="ck_property_commercial_sq_ft",
        ),
    )


class Unit(Base):
    """A rentable unit within a property."""

    __tablename__ = "units"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    unit_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[UnitStatus] = mapped_column(
        SQLEnum(UnitStatus),
        default=UnitStatus.VACANT,
        nullable=False,
    )
    
    # Unit details
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)  # stored as int (e.g., 15 = 1.5)
    
    # Commercial fields (REQUIRED if parent property_type in ('commercial', 'mixed'))
    # Service-layer enforced
    sq_ft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    property: Mapped["Property"] = relationship("Property", back_populates="units")
    leases: Mapped[list["Lease"]] = relationship(
        "Lease", back_populates="unit", cascade="all, delete-orphan"
    )
    maintenance_tickets: Mapped[list["MaintenanceTicket"]] = relationship(
        "MaintenanceTicket", back_populates="unit", cascade="all, delete-orphan"
    )
    # STR bookings
    bookings: Mapped[list["Booking"]] = relationship(
        "Booking", back_populates="unit", cascade="all, delete-orphan"
    )
