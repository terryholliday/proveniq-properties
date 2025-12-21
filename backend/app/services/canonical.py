"""Canonical JSON serializer with whitelist-based hashing.

Golden Master v2.3.1: Deterministic serialization for cross-language compatibility.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.models.inspection import Inspection, InspectionItem, InspectionEvidence


# Whitelist of fields included in canonical hash (Golden Master v2.3.1)
HEADER_FIELDS = [
    "inspection_id",
    "lease_id",
    "type",
    "status",
    "locked_at",
    "device_signed_at",
    "captured_offline",
]

ITEM_FIELDS = [
    "room_key",
    "item_key",
    "ordinal",
    "condition",
    "notes",
]

EVIDENCE_FIELDS = [
    "object_path",
    "mime_type",
    "confirmed_at",
    "storage_instance_kind",
    "storage_instance_id",
    "evidence_source",
    "file_sha256_verified",
]


class CanonicalJSONEncoder(json.JSONEncoder):
    """JSON encoder for canonical serialization."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            # ISO8601 UTC with Z suffix, second precision
            return obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(obj, UUID):
            return str(obj)
        if hasattr(obj, "value"):  # Enum
            return obj.value
        return super().default(obj)


def normalize_value(value: Any) -> Any:
    """Normalize a value for canonical JSON.
    
    Rules:
    - Null values are stripped (returned as None to be filtered)
    - Empty strings forbidden except notes; notes '' → null
    - Booleans and integers must be explicit
    - No floats or decimals allowed
    """
    if value is None:
        return None
    if isinstance(value, str):
        if value == "":
            return None  # Empty strings become null (stripped)
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise ValueError("Floats are not allowed in canonical JSON")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "value"):  # Enum
        return value.value
    return value


def extract_whitelist(data: dict, whitelist: list[str]) -> dict:
    """Extract only whitelisted fields from data."""
    result = {}
    for field in whitelist:
        if field in data:
            normalized = normalize_value(data[field])
            if normalized is not None:  # Strip nulls
                result[field] = normalized
    return result


def build_canonical_header(inspection: Inspection) -> dict:
    """Build canonical header from inspection."""
    data = {
        "inspection_id": inspection.id,
        "lease_id": inspection.lease_id,
        "type": inspection.inspection_type,
        "status": inspection.status,
        "locked_at": inspection.locked_at,
        "device_signed_at": inspection.device_signed_at,
        "captured_offline": inspection.captured_offline,
    }
    return extract_whitelist(data, HEADER_FIELDS)


def build_canonical_item(item: InspectionItem) -> dict:
    """Build canonical item from inspection item."""
    data = {
        "room_key": item.room_key,
        "item_key": item.item_key,
        "ordinal": item.ordinal,
        "condition": item.condition,
        "notes": item.notes,
    }
    return extract_whitelist(data, ITEM_FIELDS)


def build_canonical_evidence(evidence: InspectionEvidence) -> dict:
    """Build canonical evidence from inspection evidence."""
    data = {
        "object_path": evidence.object_path,
        "mime_type": evidence.mime_type,
        "confirmed_at": evidence.confirmed_at,
        "storage_instance_kind": evidence.storage_instance_kind,
        "storage_instance_id": evidence.storage_instance_id,
        "evidence_source": evidence.evidence_source,
        "file_sha256_verified": evidence.file_sha256_verified,
    }
    return extract_whitelist(data, EVIDENCE_FIELDS)


def build_canonical_payload(inspection: Inspection) -> dict:
    """Build full canonical payload for an inspection.
    
    Structure:
    {
        "header": { ... },
        "items": [
            {
                "item": { ... },
                "evidence": [ ... ]
            }
        ]
    }
    
    Sorting:
    - Items sorted by (room_key, ordinal, item_key)
    - Evidence sorted by (confirmed_at, object_path)
    """
    header = build_canonical_header(inspection)
    
    # Sort items by (room_key, ordinal, item_key)
    sorted_items = sorted(
        inspection.items,
        key=lambda x: (x.room_key, x.ordinal, x.item_key)
    )
    
    items_list = []
    for item in sorted_items:
        item_data = build_canonical_item(item)
        
        # Sort evidence by (confirmed_at, object_path)
        sorted_evidence = sorted(
            item.evidence,
            key=lambda x: (x.confirmed_at, x.object_path)
        )
        
        evidence_list = [build_canonical_evidence(ev) for ev in sorted_evidence]
        
        items_list.append({
            "item": item_data,
            "evidence": evidence_list,
        })
    
    return {
        "header": header,
        "items": items_list,
    }


def serialize_canonical(payload: dict) -> str:
    """Serialize payload to canonical JSON string.
    
    - Dictionary keys sorted alphabetically
    - No extra whitespace
    - UTF-8 encoding
    """
    return json.dumps(
        payload,
        cls=CanonicalJSONEncoder,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_canonical_hash(inspection: Inspection) -> tuple[dict, str, str]:
    """Compute canonical hash for an inspection.
    
    Returns:
        tuple: (canonical_payload, canonical_json, sha256_hash)
    """
    payload = build_canonical_payload(inspection)
    canonical_json = serialize_canonical(payload)
    sha256_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    
    return payload, canonical_json, sha256_hash


def verify_canonical_hash(canonical_json: str, expected_hash: str) -> bool:
    """Verify that canonical JSON matches expected hash."""
    computed_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return computed_hash == expected_hash
