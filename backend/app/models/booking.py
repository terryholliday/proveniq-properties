"""Booking model for STR (Short-Term Rental) support."""

import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Date, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BookingStatus

if TYPE_CHECKING:
    from app.models.property import Unit
    from app.models.user import User


class Booking(Base):
    """An STR booking (minimal v0.1 - manual entry or future channel integration).
    
    On create, auto-generates PRE_STAY inspection draft.
    POST_STAY inspection created on checkout.
    """

    __tablename__ = "bookings"

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
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # External reference (Airbnb confirmation code, etc.)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual, airbnb, vrbo, etc.
    
    # Guest info (minimal - no PII storage beyond name)
    guest_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    guest_count: Mapped[int] = mapped_column(default=1)
    
    # Dates
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Actual times (set on check-in/check-out)
    actual_check_in: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_check_out: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus),
        default=BookingStatus.UPCOMING,
        nullable=False,
        index=True,
    )
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    unit: Mapped["Unit"] = relationship("Unit", back_populates="bookings")
    created_by: Mapped[Optional["User"]] = relationship("User")
