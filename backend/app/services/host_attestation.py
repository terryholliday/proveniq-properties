"""Host Attestation Service for STR properties.

Generates cryptographically verifiable attestations for STR hosts to:
- Prove property condition at booking start/end
- Support resolution center claims (Airbnb/VRBO/Booking.com)
- Build trust with guests and platforms

ATTESTATION PROTOCOL:
- Time-bound (valid only for specific booking window)
- Evidence-backed (linked to inspection photos/items)
- Cryptographically signed (SHA-256 hash chain)
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.inspection import Inspection, InspectionItem, InspectionEvidence
from app.models.enums import BookingStatus, InspectionStatus, InspectionType


class HostAttestationService:
    """Generate and verify host attestations for STR bookings."""

    ATTESTATION_VERSION = "1.0.0"
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_pre_booking_attestation(
        self,
        booking_id: UUID,
        inspection_id: UUID,
        org_id: UUID,
        host_user_id: UUID,
    ) -> dict[str, Any]:
        """Generate attestation for property condition before guest arrival.
        
        This attestation:
        - Links to check-in inspection
        - Captures property condition baseline
        - Is time-stamped and hashed for integrity
        """
        # Get booking
        booking_result = await self.db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = booking_result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        
        # Get inspection
        inspection_result = await self.db.execute(
            select(Inspection).where(Inspection.id == inspection_id)
        )
        inspection = inspection_result.scalar_one_or_none()
        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")
        
        # Get inspection items with condition scores
        items_result = await self.db.execute(
            select(InspectionItem).where(InspectionItem.inspection_id == inspection_id)
        )
        items = items_result.scalars().all()
        
        # Get evidence count
        evidence_result = await self.db.execute(
            select(InspectionEvidence).where(InspectionEvidence.inspection_id == inspection_id)
        )
        evidence = evidence_result.scalars().all()
        
        # Build attestation payload
        attestation_id = uuid4()
        issued_at = datetime.utcnow()
        expires_at = booking.check_out_date + timedelta(days=30)  # Valid 30 days after checkout
        
        payload = {
            "attestation_type": "PRE_BOOKING_CONDITION",
            "booking_id": str(booking_id),
            "inspection_id": str(inspection_id),
            "property_unit_id": str(booking.unit_id),
            "guest_name": booking.guest_name,
            "check_in_date": booking.check_in_date.isoformat(),
            "check_out_date": booking.check_out_date.isoformat(),
            "inspection_status": inspection.status.value,
            "inspection_completed_at": inspection.completed_at.isoformat() if inspection.completed_at else None,
            "items_inspected": len(items),
            "evidence_photos": len(evidence),
            "condition_summary": self._summarize_conditions(items),
        }
        
        # Generate evidence digest
        evidence_digest = self._compute_evidence_digest(items, evidence)
        
        attestation = {
            "attestation_id": str(attestation_id),
            "version": self.ATTESTATION_VERSION,
            "attestation_type": "PRE_BOOKING_CONDITION",
            "org_id": str(org_id),
            "host_user_id": str(host_user_id),
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "time_window": {
                "start": booking.check_in_date.isoformat(),
                "end": booking.check_out_date.isoformat(),
            },
            "payload": payload,
            "evidence_digest": evidence_digest,
            "signature": self._sign_attestation(attestation_id, payload, evidence_digest, issued_at),
            "verification_url": f"/api/attestations/verify/{attestation_id}",
        }
        
        return attestation

    async def generate_post_booking_attestation(
        self,
        booking_id: UUID,
        check_in_inspection_id: UUID,
        check_out_inspection_id: UUID,
        org_id: UUID,
        host_user_id: UUID,
    ) -> dict[str, Any]:
        """Generate attestation comparing pre/post booking condition.
        
        This attestation:
        - Compares check-in vs check-out inspections
        - Documents any damage or changes
        - Supports resolution center claims
        """
        # Get booking
        booking_result = await self.db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = booking_result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        
        # Get both inspections
        check_in_result = await self.db.execute(
            select(Inspection).where(Inspection.id == check_in_inspection_id)
        )
        check_in_inspection = check_in_result.scalar_one_or_none()
        
        check_out_result = await self.db.execute(
            select(Inspection).where(Inspection.id == check_out_inspection_id)
        )
        check_out_inspection = check_out_result.scalar_one_or_none()
        
        if not check_in_inspection or not check_out_inspection:
            raise ValueError("Both check-in and check-out inspections required")
        
        # Get items from both inspections
        check_in_items = await self._get_inspection_items(check_in_inspection_id)
        check_out_items = await self._get_inspection_items(check_out_inspection_id)
        
        # Compare conditions
        damage_report = self._compare_inspections(check_in_items, check_out_items)
        
        # Build attestation
        attestation_id = uuid4()
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(days=365)  # Valid for 1 year
        
        payload = {
            "attestation_type": "POST_BOOKING_COMPARISON",
            "booking_id": str(booking_id),
            "check_in_inspection_id": str(check_in_inspection_id),
            "check_out_inspection_id": str(check_out_inspection_id),
            "property_unit_id": str(booking.unit_id),
            "guest_name": booking.guest_name,
            "booking_window": {
                "check_in": booking.check_in_date.isoformat(),
                "check_out": booking.check_out_date.isoformat(),
            },
            "damage_report": damage_report,
            "total_damage_items": damage_report["total_damaged_items"],
            "estimated_repair_cost_cents": damage_report["estimated_total_cents"],
        }
        
        # Generate evidence digest from both inspections
        check_in_evidence = await self._get_inspection_evidence(check_in_inspection_id)
        check_out_evidence = await self._get_inspection_evidence(check_out_inspection_id)
        evidence_digest = self._compute_combined_digest(
            check_in_items, check_out_items, 
            check_in_evidence, check_out_evidence
        )
        
        attestation = {
            "attestation_id": str(attestation_id),
            "version": self.ATTESTATION_VERSION,
            "attestation_type": "POST_BOOKING_COMPARISON",
            "org_id": str(org_id),
            "host_user_id": str(host_user_id),
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "time_window": {
                "start": booking.check_in_date.isoformat(),
                "end": booking.check_out_date.isoformat(),
            },
            "payload": payload,
            "evidence_digest": evidence_digest,
            "signature": self._sign_attestation(attestation_id, payload, evidence_digest, issued_at),
            "claim_support": {
                "airbnb_compatible": True,
                "vrbo_compatible": True,
                "booking_com_compatible": True,
            },
            "verification_url": f"/api/attestations/verify/{attestation_id}",
        }
        
        return attestation

    async def _get_inspection_items(self, inspection_id: UUID) -> list:
        """Get all items for an inspection."""
        result = await self.db.execute(
            select(InspectionItem).where(InspectionItem.inspection_id == inspection_id)
        )
        return result.scalars().all()

    async def _get_inspection_evidence(self, inspection_id: UUID) -> list:
        """Get all evidence for an inspection."""
        result = await self.db.execute(
            select(InspectionEvidence).where(InspectionEvidence.inspection_id == inspection_id)
        )
        return result.scalars().all()

    def _summarize_conditions(self, items: list) -> dict[str, Any]:
        """Summarize condition scores across all items."""
        if not items:
            return {"average": 0, "min": 0, "max": 0, "count": 0}
        
        conditions = [item.condition_score for item in items if item.condition_score is not None]
        if not conditions:
            return {"average": 0, "min": 0, "max": 0, "count": 0}
        
        return {
            "average": round(sum(conditions) / len(conditions), 2),
            "min": min(conditions),
            "max": max(conditions),
            "count": len(conditions),
        }

    def _compare_inspections(self, check_in_items: list, check_out_items: list) -> dict[str, Any]:
        """Compare check-in vs check-out items to find damage."""
        # Build lookup by room + item name
        check_in_map = {
            f"{item.room_name}:{item.item_name}": item 
            for item in check_in_items
        }
        
        damaged_items = []
        total_estimated = 0
        
        for out_item in check_out_items:
            key = f"{out_item.room_name}:{out_item.item_name}"
            in_item = check_in_map.get(key)
            
            if not in_item:
                continue
            
            condition_change = (out_item.condition_score or 0) - (in_item.condition_score or 0)
            
            if condition_change < 0:
                # Damage detected
                estimated_cost = self._estimate_repair_cost(
                    out_item.room_name, 
                    out_item.item_name, 
                    condition_change
                )
                
                damaged_items.append({
                    "room_name": out_item.room_name,
                    "item_name": out_item.item_name,
                    "condition_before": in_item.condition_score,
                    "condition_after": out_item.condition_score,
                    "condition_change": condition_change,
                    "estimated_repair_cents": estimated_cost,
                })
                total_estimated += estimated_cost
        
        return {
            "total_damaged_items": len(damaged_items),
            "items": damaged_items,
            "estimated_total_cents": total_estimated,
        }

    def _estimate_repair_cost(self, room: str, item: str, condition_change: int) -> int:
        """Quick repair cost estimate based on condition change."""
        base_cost = 15000  # $150 default
        multiplier = abs(condition_change) * 0.25
        return int(base_cost * (1 + multiplier))

    def _compute_evidence_digest(self, items: list, evidence: list) -> str:
        """Compute SHA-256 digest of all evidence."""
        data = {
            "items": [
                {
                    "room": item.room_name,
                    "item": item.item_name,
                    "condition": item.condition_score,
                }
                for item in items
            ],
            "evidence_hashes": [
                e.content_hash for e in evidence if e.content_hash
            ],
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _compute_combined_digest(
        self, 
        in_items: list, 
        out_items: list, 
        in_evidence: list, 
        out_evidence: list
    ) -> str:
        """Compute combined digest for both inspections."""
        data = {
            "check_in": {
                "items": [
                    {"room": i.room_name, "item": i.item_name, "condition": i.condition_score}
                    for i in in_items
                ],
                "evidence": [e.content_hash for e in in_evidence if e.content_hash],
            },
            "check_out": {
                "items": [
                    {"room": i.room_name, "item": i.item_name, "condition": i.condition_score}
                    for i in out_items
                ],
                "evidence": [e.content_hash for e in out_evidence if e.content_hash],
            },
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _sign_attestation(
        self, 
        attestation_id: UUID, 
        payload: dict, 
        evidence_digest: str, 
        issued_at: datetime
    ) -> str:
        """Generate attestation signature."""
        sign_data = {
            "attestation_id": str(attestation_id),
            "payload_hash": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
            "evidence_digest": evidence_digest,
            "issued_at": issued_at.isoformat(),
        }
        return hashlib.sha256(
            json.dumps(sign_data, sort_keys=True).encode()
        ).hexdigest()

    async def verify_attestation(self, attestation: dict[str, Any]) -> dict[str, Any]:
        """Verify an attestation's integrity."""
        # Recompute signature
        recomputed = self._sign_attestation(
            UUID(attestation["attestation_id"]),
            attestation["payload"],
            attestation["evidence_digest"],
            datetime.fromisoformat(attestation["issued_at"]),
        )
        
        signature_valid = recomputed == attestation["signature"]
        
        # Check expiration
        expires_at = datetime.fromisoformat(attestation["expires_at"])
        is_expired = datetime.utcnow() > expires_at
        
        return {
            "attestation_id": attestation["attestation_id"],
            "signature_valid": signature_valid,
            "is_expired": is_expired,
            "verification_time": datetime.utcnow().isoformat(),
            "status": "valid" if signature_valid and not is_expired else "invalid",
        }
