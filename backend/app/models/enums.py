"""Enumeration types for PROVENIQ Properties domain model."""

from enum import Enum


class PropertyType(str, Enum):
    """Type of property."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED = "mixed"


class UnitStatus(str, Enum):
    """Status of a unit."""
    OCCUPIED = "occupied"
    VACANT = "vacant"
    MAINTENANCE = "maintenance"


class OrgRole(str, Enum):
    """Role within an organization."""
    ORG_OWNER = "ORG_OWNER"
    ORG_ADMIN = "ORG_ADMIN"
    ORG_AGENT = "ORG_AGENT"


class LeaseStatus(str, Enum):
    """Status of a lease."""
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    TERMINATING = "terminating"
    ENDED = "ended"
    DISPUTED = "disputed"


class LeaseType(str, Enum):
    """Type of lease agreement."""
    RESIDENTIAL_GROSS = "residential_gross"
    COMMERCIAL_GROSS = "commercial_gross"
    COMMERCIAL_NNN = "commercial_nnn"


class InspectionType(str, Enum):
    """Type of inspection."""
    MOVE_IN = "move_in"
    MOVE_OUT = "move_out"
    PERIODIC = "periodic"


class InspectionStatus(str, Enum):
    """Status of an inspection."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    SIGNED = "signed"
    ARCHIVED = "archived"


class MaintenanceStatus(str, Enum):
    """Status of a maintenance ticket."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class VendorSpecialty(str, Enum):
    """Vendor specialty type."""
    GENERAL = "GENERAL"
    PLUMBING = "PLUMBING"
    HVAC = "HVAC"
    ELECTRICAL = "ELECTRICAL"
    ROOFING = "ROOFING"


class EvidenceType(str, Enum):
    """Type of evidence file."""
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class StorageProvider(str, Enum):
    """Cloud storage provider."""
    GCS = "gcs"
    S3 = "s3"


class AuditAction(str, Enum):
    """Actions tracked in audit log."""
    INVITE_SENT = "invite_sent"
    INVITE_ACCEPTED = "invite_accepted"
    INSPECTION_SUBMITTED = "inspection_submitted"
    INSPECTION_SIGNED = "inspection_signed"
    VENDOR_ASSIGNED = "vendor_assigned"
    MAINTENANCE_TRIAGED = "maintenance_triaged"
    LEASE_CREATED = "lease_created"
    LEASE_ACTIVATED = "lease_activated"
    EVIDENCE_CONFIRMED = "evidence_confirmed"
