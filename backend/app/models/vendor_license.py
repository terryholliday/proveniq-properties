"""VendorLicense model — migrated from proveniq-service."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LicenseType

if TYPE_CHECKING:
    from app.models.vendor import Vendor


class VendorLicense(Base):
    """A verified license/credential for a vendor."""

    __tablename__ = "vendor_licenses"

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

    license_type: Mapped[LicenseType] = mapped_column(
        SQLEnum(LicenseType),
        nullable=False,
    )
    license_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="licenses")
