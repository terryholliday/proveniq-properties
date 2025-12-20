"""Inspection, InspectionItem, and InspectionEvidence models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Integer, Boolean, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    InspectionType, InspectionStatus, EvidenceType, InspectionScope, InspectionSignedBy,
    InspectionCondition, EvidenceSource, StorageInstanceKind, SignatureType,
)
from sqlalchemy import BigInteger, UniqueConstraint

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
    
    # STR support: scope determines if lease-scoped or booking-scoped
    scope: Mapped[InspectionScope] = mapped_column(
        SQLEnum(InspectionScope),
        default=InspectionScope.LEASE,
        nullable=False,
    )
    # Required if scope='booking' (STR)
    booking_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    
    # Inspection date
    inspection_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Golden Master v2.3.1: Immutability + Canonical JSON
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    device_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    captured_offline: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Content hash (SHA-256 of canonical JSON)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Frozen canonical JSON blob for audit trail
    canonical_json_blob: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    canonical_json_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Certificate PDF
    certificate_pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    certificate_pdf_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Signatures (lease-scoped: tenant + landlord)
    tenant_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    landlord_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # STR host attestation (booking-scoped)
    signed_by: Mapped[Optional[InspectionSignedBy]] = mapped_column(
        SQLEnum(InspectionSignedBy),
        nullable=True,
    )
    signed_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
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

    __table_args__ = (
        # STR constraint: booking-scoped inspections require booking_id
        CheckConstraint(
            "(scope = 'booking' AND booking_id IS NOT NULL) OR (scope = 'lease')",
            name="ck_inspection_booking_scope",
        ),
        # STR constraint: booking-scoped must be PRE_STAY/POST_STAY, lease-scoped must be MOVE_IN/MOVE_OUT/PERIODIC
        CheckConstraint(
            "(scope = 'booking' AND inspection_type IN ('pre_stay', 'post_stay')) OR "
            "(scope = 'lease' AND inspection_type IN ('move_in', 'move_out', 'periodic'))",
            name="ck_inspection_scope_type",
        ),
    )


class InspectionItem(Base):
    """An item within an inspection.
    
    Golden Master v2.3.1: Uses room_key/item_key/ordinal/condition pattern.
    """

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
    
    # Golden Master v2.3.1: room_key/item_key/ordinal pattern
    room_key: Mapped[str] = mapped_column(String(100), nullable=False)
    item_key: Mapped[str] = mapped_column(String(100), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Condition (enum-based)
    condition: Mapped[InspectionCondition] = mapped_column(
        SQLEnum(InspectionCondition),
        default=InspectionCondition.GOOD,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
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
        order_by="InspectionEvidence.confirmed_at"
    )

    __table_args__ = (
        UniqueConstraint('inspection_id', 'room_key', 'ordinal', 'item_key', name='uq_inspection_item_order'),
    )


class InspectionEvidence(Base):
    """Evidence (photo/video/document) attached to an inspection item.
    
    Golden Master v2.3.1: Idempotent confirm with storage instance tracking.
    Evidence custody: Presign → Client Upload → Server Confirm (idempotent)
    """

    __tablename__ = "inspection_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    inspection_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Storage info
    object_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    # SHA-256 hashes: claimed by client, verified by server async
    file_sha256_claimed: Mapped[str] = mapped_column(String(64), nullable=False)
    file_sha256_verified: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Confirm timestamp (server-side HEAD check passed)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Evidence source
    evidence_source: Mapped[EvidenceSource] = mapped_column(
        SQLEnum(EvidenceSource),
        default=EvidenceSource.TENANT,
        nullable=False,
    )
    
    # Storage provider instance tracking (for immutability verification)
    storage_instance_kind: Mapped[StorageInstanceKind] = mapped_column(
        SQLEnum(StorageInstanceKind),
        nullable=False,
    )
    storage_instance_id: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Idempotency key for confirm endpoint
    confirm_idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    item: Mapped["InspectionItem"] = relationship("InspectionItem", back_populates="evidence")

    __table_args__ = (
        UniqueConstraint('inspection_item_id', 'confirm_idempotency_key', name='uq_evidence_confirm'),
    )
