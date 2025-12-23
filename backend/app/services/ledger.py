"""
PROVENIQ Properties - Ledger Service

CANONICAL SCHEMA v1.0.0
- Uses DOMAIN_NOUN_VERB_PAST event naming
- Publishes to /api/v1/events/canonical endpoint
- Includes idempotency_key for duplicate prevention
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
import httpx

logger = logging.getLogger(__name__)

LEDGER_API_URL = "http://localhost:8006"
SCHEMA_VERSION = "1.0.0"
PRODUCER = "properties"
PRODUCER_VERSION = "1.0.0"


class LedgerService:
    """
    Bridge to PROVENIQ Ledger for property audit trail.
    
    Properties writes events for:
    - Inspections (created, signed, disputed)
    - Evidence uploads
    - Maintenance tickets
    - Lease events
    - Deposit disputes
    """
    
    def __init__(self, base_url: str = LEDGER_API_URL):
        self.base_url = base_url
    
    def _hash_payload(self, payload: dict) -> str:
        """Calculate SHA256 hash of payload."""
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    async def write_event(
        self,
        event_type: str,
        asset_id: Optional[str],
        actor_id: str,
        payload: dict,
        correlation_id: Optional[str] = None,
        subject_extra: Optional[dict] = None,
    ) -> Optional[dict]:
        """Write a canonical event to the Ledger."""
        corr_id = correlation_id or str(uuid4())
        idempotency_key = f"properties_{uuid4()}"
        occurred_at = datetime.utcnow().isoformat() + "Z"
        canonical_hash = self._hash_payload(payload)

        subject = {"asset_id": asset_id or "SYSTEM"}
        if subject_extra:
            subject.update(subject_extra)

        canonical_event = {
            "schema_version": SCHEMA_VERSION,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "committed_at": occurred_at,
            "correlation_id": corr_id,
            "idempotency_key": idempotency_key,
            "producer": PRODUCER,
            "producer_version": PRODUCER_VERSION,
            "subject": subject,
            "payload": {
                **payload,
                "actor_id": actor_id,
            },
            "canonical_hash_hex": canonical_hash,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/events/canonical",
                    json=canonical_event,
                    timeout=10.0,
                )
                
                if response.status_code not in (200, 201):
                    logger.warning(f"[LEDGER] Write failed: {response.status_code} {response.text}")
                    return None
                
                data = response.json()
                return {
                    "event_id": data.get("event_id"),
                    "sequence_number": data.get("sequence_number"),
                    "entry_hash": data.get("entry_hash"),
                    "committed_at": data.get("committed_at"),
                }
        except Exception as e:
            logger.error(f"[LEDGER] Write error: {e}")
            return None
    
    async def write_inspection_created(
        self,
        inspection_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        inspection_type: str,
        created_by: UUID,
    ) -> Optional[dict]:
        """Record inspection creation."""
        return await self.write_event(
            event_type="PROPERTIES_INSPECTION_CREATED",
            asset_id=str(property_id),
            actor_id=str(created_by),
            payload={
                "inspection_id": str(inspection_id),
                "unit_id": str(unit_id) if unit_id else None,
                "inspection_type": inspection_type,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_inspection_signed(
        self,
        inspection_id: UUID,
        property_id: UUID,
        signed_by: UUID,
        signature_role: str,
        evidence_hash: str,
    ) -> Optional[dict]:
        """Record inspection signature (immutable after this)."""
        return await self.write_event(
            event_type="PROPERTIES_INSPECTION_SIGNED",
            asset_id=str(property_id),
            actor_id=str(signed_by),
            payload={
                "inspection_id": str(inspection_id),
                "signature_role": signature_role,
                "evidence_hash": evidence_hash,
                "signed_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_evidence_uploaded(
        self,
        inspection_id: UUID,
        item_id: UUID,
        evidence_hash: str,
        evidence_type: str,
        uploaded_by: UUID,
    ) -> Optional[dict]:
        """Record evidence upload."""
        return await self.write_event(
            event_type="PROPERTIES_EVIDENCE_UPLOADED",
            asset_id=str(item_id),
            actor_id=str(uploaded_by),
            payload={
                "inspection_id": str(inspection_id),
                "evidence_hash": evidence_hash,
                "evidence_type": evidence_type,
                "uploaded_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_maintenance_created(
        self,
        ticket_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        issue_type: str,
        urgency: str,
        reported_by: UUID,
    ) -> Optional[dict]:
        """Record maintenance ticket creation."""
        return await self.write_event(
            event_type="PROPERTIES_MAINTENANCE_CREATED",
            asset_id=str(property_id),
            actor_id=str(reported_by),
            payload={
                "ticket_id": str(ticket_id),
                "unit_id": str(unit_id) if unit_id else None,
                "issue_type": issue_type,
                "urgency": urgency,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_maintenance_dispatched(
        self,
        ticket_id: UUID,
        property_id: UUID,
        vendor_id: UUID,
        dispatched_by: UUID,
    ) -> Optional[dict]:
        """Record maintenance dispatch to Service."""
        return await self.write_event(
            event_type="PROPERTIES_MAINTENANCE_DISPATCHED",
            asset_id=str(property_id),
            actor_id=str(dispatched_by),
            payload={
                "ticket_id": str(ticket_id),
                "vendor_id": str(vendor_id),
                "dispatched_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_deposit_dispute_filed(
        self,
        lease_id: UUID,
        property_id: UUID,
        tenant_id: UUID,
        disputed_amount_cents: int,
        reason: str,
    ) -> Optional[dict]:
        """Record deposit dispute filing."""
        return await self.write_event(
            event_type="PROPERTIES_DEPOSIT_DISPUTE_FILED",
            asset_id=str(property_id),
            actor_id=str(tenant_id),
            payload={
                "lease_id": str(lease_id),
                "disputed_amount_cents": disputed_amount_cents,
                "reason": reason,
                "filed_at": datetime.utcnow().isoformat(),
            },
        )


# Singleton
_ledger_instance: Optional[LedgerService] = None


def get_ledger_service() -> LedgerService:
    """Get the Ledger service instance."""
    global _ledger_instance
    if _ledger_instance is None:
        _ledger_instance = LedgerService()
    return _ledger_instance
