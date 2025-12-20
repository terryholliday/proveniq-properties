"""Inspection, InspectionItem, and InspectionEvidence models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import InspectionType, InspectionStatus, EvidenceType

if TYPE_CHECKING:
    from app.models.lease import Lease
    from app.models.user import User


class Inspection(Base):
    """An inspection record (move-in, move-out, periodic)."""

    __tablename__ = "inspections"

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
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Supplemental inspection (corrections to signed inspection)
    supplemental_to_inspection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    inspection_type: Mapped[InspectionType] = mapped_column(
        SQLEnum(InspectionType),
        nullable=False,
    )
    status: Mapped[InspectionStatus] = mapped_column(
        SQLEnum(InspectionStatus),
        default=InspectionStatus.DRAFT,
        nullable=False,
        index=True,
    )
    
    # Inspection date
    inspection_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Immutability: content_hash is computed on SUBMIT and locked on SIGN
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Signatures
    tenant_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    landlord_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    lease: Mapped["Lease"] = relationship("Lease", back_populates="inspections")
    created_by: Mapped[Optional["User"]] = relationship(
        "User", back_populates="inspections_created", foreign_keys=[created_by_id]
    )
    items: Mapped[list["InspectionItem"]] = relationship(
        "InspectionItem", back_populates="inspection", cascade="all, delete-orphan",
        order_by="InspectionItem.room_name, InspectionItem.item_name"
    )
    supplemental_inspections: Mapped[list["Inspection"]] = relationship(
        "Inspection", back_populates="original_inspection",
        foreign_keys=[supplemental_to_inspection_id]
    )
    original_inspection: Mapped[Optional["Inspection"]] = relationship(
        "Inspection", back_populates="supplemental_inspections",
        remote_side=[id], foreign_keys=[supplemental_to_inspection_id]
    )


class InspectionItem(Base):
    """An item within an inspection (e.g., 'Kitchen - Sink')."""

    __tablename__ = "inspection_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Condition rating (1-5 scale)
    condition_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    condition_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # For diff calculations
    is_damaged: Mapped[bool] = mapped_column(Boolean, default=False)
    damage_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Mason AI cost estimate (advisory only - INTEGER CENTS)
    mason_estimated_repair_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    inspection: Mapped["Inspection"] = relationship("Inspection", back_populates="items")
    evidence: Mapped[list["InspectionEvidence"]] = relationship(
        "InspectionEvidence", back_populates="item", cascade="all, delete-orphan",
        order_by="InspectionEvidence.created_at"
    )


class InspectionEvidence(Base):
    """Evidence (photo/video/document) attached to an inspection item."""

    __tablename__ = "inspection_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    evidence_type: Mapped[EvidenceType] = mapped_column(
        SQLEnum(EvidenceType),
        default=EvidenceType.PHOTO,
        nullable=False,
    )
    
    # Storage info
    object_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Integrity: SHA-256 hash of file content
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Presign/confirm flow
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Metadata (EXIF, etc.)
    metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    item: Mapped["InspectionItem"] = relationship("InspectionItem", back_populates="evidence")
