"""VendorReview model — migrated from proveniq-service."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.vendor import Vendor


class VendorReview(Base):
    """A review of a vendor's work."""

    __tablename__ = "vendor_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    maintenance_ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_tickets.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewer_type: Mapped[str] = mapped_column(String(50), nullable=False)  # tenant, landlord, owner

    # Overall rating (1-5)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Breakdown ratings (1-5)
    quality_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timeliness_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    communication_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    value_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="reviews")
