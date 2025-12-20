"""Turnover model for STR cleaning/turnover workflow."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TurnoverStatus, TurnoverPhotoType

if TYPE_CHECKING:
    from app.models.property import Unit
    from app.models.booking import Booking
    from app.models.user import User


class Turnover(Base):
    """An STR turnover (cleaning between guests).
    
    Turnovers are linked to a booking's checkout and the next booking's checkin.
    Cleaners complete a 5-photo checklist to verify the unit is ready.
    """

    __tablename__ = "turnovers"

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
    
    # Link to outgoing and incoming bookings (optional - turnover can exist without bookings)
    checkout_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
    )
    checkin_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Assignment
    assigned_cleaner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Scheduling
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    due_by: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Must be done by this time
    
    # Status tracking
    status: Mapped[TurnoverStatus] = mapped_column(
        SQLEnum(TurnoverStatus),
        default=TurnoverStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Notes
    cleaner_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    host_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Flags
    has_damage: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_restock: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    unit: Mapped["Unit"] = relationship("Unit")
    checkout_booking: Mapped[Optional["Booking"]] = relationship(
        "Booking", foreign_keys=[checkout_booking_id]
    )
    checkin_booking: Mapped[Optional["Booking"]] = relationship(
        "Booking", foreign_keys=[checkin_booking_id]
    )
    assigned_cleaner: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_cleaner_id]
    )
    verified_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[verified_by_id]
    )
    photos: Mapped[List["TurnoverPhoto"]] = relationship(
        "TurnoverPhoto", back_populates="turnover", cascade="all, delete-orphan"
    )
    inventory_checks: Mapped[List["TurnoverInventory"]] = relationship(
        "TurnoverInventory", back_populates="turnover", cascade="all, delete-orphan"
    )


class TurnoverPhoto(Base):
    """A photo in the turnover checklist.
    
    5 mandatory photos: bed, kitchen, bathroom, towels, keys
    """

    __tablename__ = "turnover_photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    turnover_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("turnovers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    photo_type: Mapped[TurnoverPhotoType] = mapped_column(
        SQLEnum(TurnoverPhotoType),
        nullable=False,
    )
    
    # Storage
    object_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    mime_type: Mapped[str] = mapped_column(String(100), default="image/jpeg")
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)  # Host flagged an issue
    
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    turnover: Mapped["Turnover"] = relationship("Turnover", back_populates="photos")
    uploaded_by: Mapped[Optional["User"]] = relationship("User")


class TurnoverInventory(Base):
    """Inventory count for STR turnover.
    
    Tracks counts of items like wine glasses, towels, etc.
    #1 dispute in STR is missing inventory items.
    """

    __tablename__ = "turnover_inventory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    turnover_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("turnovers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Item details
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="")  # e.g., "Kitchen", "Master Bath"
    
    # Counts
    expected_quantity: Mapped[int] = mapped_column(Integer, default=0)
    actual_quantity: Mapped[int] = mapped_column(Integer, default=0)
    
    # Flags
    is_missing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_damaged: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    turnover: Mapped["Turnover"] = relationship("Turnover", back_populates="inventory_checks")
