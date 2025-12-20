"""Organization and membership models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import OrgRole

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.property import Property
    from app.models.vendor import Vendor


class Organization(Base):
    """Organization (landlord entity - individual or company)."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Contact info
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Settings
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    memberships: Mapped[list["OrgMembership"]] = relationship(
        "OrgMembership", back_populates="org", cascade="all, delete-orphan"
    )
    properties: Mapped[list["Property"]] = relationship(
        "Property", back_populates="org", cascade="all, delete-orphan"
    )
    vendors: Mapped[list["Vendor"]] = relationship(
        "Vendor", back_populates="org", cascade="all, delete-orphan"
    )


class OrgMembership(Base):
    """User membership in an organization with role."""

    __tablename__ = "org_memberships"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[OrgRole] = mapped_column(
        SQLEnum(OrgRole),
        default=OrgRole.ORG_AGENT,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    org: Mapped["Organization"] = relationship("Organization", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="org_memberships")
