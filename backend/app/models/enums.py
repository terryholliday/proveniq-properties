"""Enumeration types for PROVENIQ Properties domain model."""

from enum import Enum


class PropertyType(str, Enum):
    """Type of property."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED = "mixed"


class OccupancyModel(str, Enum):
    """Occupancy model for a property."""
    LONG_TERM_RESIDENTIAL = "long_term_residential"
    COMMERCIAL_LEASE = "commercial_lease"
    SHORT_TERM_RENTAL = "short_term_rental"


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
    ORG_CLEANER = "ORG_CLEANER"  # STR turnover role - can only do turnovers


class TurnoverStatus(str, Enum):
    """Status of an STR turnover."""
    PENDING = "pending"        # Scheduled, not started
    IN_PROGRESS = "in_progress"  # Cleaner on-site
    COMPLETED = "completed"    # All photos submitted
    VERIFIED = "verified"      # Host reviewed and approved
    FLAGGED = "flagged"        # Issue found


class TurnoverPhotoType(str, Enum):
    """Mandatory photo types for STR turnover."""
    BED = "bed"              # Bed made, linens fresh
    KITCHEN = "kitchen"      # Kitchen clean, appliances ready
    BATHROOM = "bathroom"    # Bathroom sanitized
    TOWELS = "towels"        # Fresh towels placed
    KEYS = "keys"            # Keys/lockbox ready
    INVENTORY = "inventory"  # Optional: inventory count photo


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
    # Lease-scoped (LTR/Commercial)
    MOVE_IN = "move_in"
    MOVE_OUT = "move_out"
    PERIODIC = "periodic"
    # Booking-scoped (STR)
    PRE_STAY = "pre_stay"
    POST_STAY = "post_stay"


class InspectionScope(str, Enum):
    """Scope of an inspection."""
    LEASE = "lease"      # Long-term rental / commercial lease
    BOOKING = "booking"  # Short-term rental booking


class InspectionSignedBy(str, Enum):
    """Who signed the inspection."""
    TENANT = "TENANT"
    LANDLORD_ORG_MEMBER = "LANDLORD_ORG_MEMBER"
    HOST_SYSTEM = "HOST_SYSTEM"  # STR host attestation


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
    INSPECTION_ATTESTED = "inspection_attested"  # STR host attestation
    VENDOR_ASSIGNED = "vendor_assigned"
    MAINTENANCE_TRIAGED = "maintenance_triaged"
    LEASE_CREATED = "lease_created"
    LEASE_ACTIVATED = "lease_activated"
    EVIDENCE_CONFIRMED = "evidence_confirmed"
    BOOKING_CREATED = "booking_created"
    CLAIM_PACKET_GENERATED = "claim_packet_generated"


class BookingStatus(str, Enum):
    """Status of an STR booking."""
    UPCOMING = "upcoming"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


# === Golden Master v2.3.1 Enums ===

class TenantRole(str, Enum):
    """Role of tenant on a lease."""
    PRIMARY = "PRIMARY"
    OCCUPANT = "OCCUPANT"


class InviteStatus(str, Enum):
    """Status of tenant invite."""
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"


class InspectionCondition(str, Enum):
    """Condition of an inspection item."""
    GOOD = "good"
    FAIR = "fair"
    DAMAGED = "damaged"
    NOT_PRESENT = "not_present"


class EvidenceSource(str, Enum):
    """Source of evidence upload."""
    TENANT = "tenant"
    LANDLORD = "landlord"
    VENDOR = "vendor"
    SYSTEM = "system"


class SignatureType(str, Enum):
    """Cryptographic signature type."""
    NONE = "none"
    ED25519 = "ed25519"
    P256 = "p256"


class ContextVerdict(str, Enum):
    """Verdict for context verification."""
    UNKNOWN = "unknown"
    MATCH = "match"
    MISMATCH = "mismatch"
    INCONCLUSIVE = "inconclusive"


class StorageInstanceKind(str, Enum):
    """Storage provider instance identifier type."""
    GCS_GENERATION = "gcs_generation"
    S3_ETAG = "s3_etag"


class JobStatus(str, Enum):
    """Status of async job in outbox."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
