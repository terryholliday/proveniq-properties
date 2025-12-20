"""
PROVENIQ Properties - ClaimsIQ Integration Client

Pushes deposit dispute claims to ClaimsIQ for processing.
This completes the Evidence → Recovery → Payout pipeline.

ClaimsIQ Flow:
1. Properties generates claim packet (evidence + hashes + estimates)
2. Properties pushes claim to ClaimsIQ via this client
3. ClaimsIQ processes: Intake → Ledger → Intelligence → Audit
4. ClaimsIQ issues decision (PAY/DENY)
5. Capital receives PAY decisions and processes payout
"""

import httpx
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel
from enum import Enum

from app.core.config import get_settings


class ClaimType(str, Enum):
    """Type of claim being submitted."""
    DEPOSIT_DISPUTE = "DEPOSIT_DISPUTE"
    PROPERTY_DAMAGE = "PROPERTY_DAMAGE"
    STR_GUEST_DAMAGE = "STR_GUEST_DAMAGE"
    MAINTENANCE_CLAIM = "MAINTENANCE_CLAIM"


class IncidentVector(BaseModel):
    """Incident details for ClaimsIQ."""
    type: str  # THEFT, DAMAGE, VANDALISM, etc.
    location: Dict[str, Any]  # GeoJSON Point
    severity: int  # 1-10
    description_hash: str  # SHA-256 of description


class ClaimSubmission(BaseModel):
    """Claim submission to ClaimsIQ."""
    id: str
    intake_timestamp: str
    policy_snapshot_id: str
    claimant_did: str  # Landlord/Host DID
    asset_id: str  # Property/Unit ID
    incident_vector: IncidentVector
    status: str = "INTAKE"
    
    # PROVENIQ Properties specific
    source_app: str = "proveniq-properties"
    claim_type: ClaimType
    lease_id: Optional[str] = None
    booking_id: Optional[str] = None
    
    # Evidence package
    evidence: Dict[str, Any] = {}


class ClaimSubmissionResult(BaseModel):
    """Result from ClaimsIQ submission."""
    success: bool
    claim_id: Optional[str] = None
    decision: Optional[str] = None
    seal: Optional[str] = None
    error: Optional[str] = None


class ClaimsIQClient:
    """
    Client for submitting claims to PROVENIQ ClaimsIQ.
    
    This client bridges Properties → ClaimsIQ in the ecosystem:
    - Deposit disputes from move-out inspections
    - STR guest damage from turnover inspections
    - Property damage from maintenance tickets
    """
    
    def __init__(self):
        settings = get_settings()
        self.base_url = getattr(settings, 'claimsiq_base_url', 'http://localhost:3000')
        self.api_key = getattr(settings, 'claimsiq_api_key', '')
        self.enabled = getattr(settings, 'claimsiq_enabled', False)
        self.timeout = 30.0
    
    async def submit_deposit_claim(
        self,
        lease_id: UUID,
        org_id: UUID,
        claimant_email: str,
        property_address: str,
        unit_number: str,
        move_in_hash: str,
        move_out_hash: str,
        damaged_items: List[Dict[str, Any]],
        total_damage_cents: int,
        deposit_amount_cents: int,
        evidence_hashes: List[str],
    ) -> ClaimSubmissionResult:
        """
        Submit a deposit dispute claim to ClaimsIQ.
        
        Args:
            lease_id: The lease being disputed
            org_id: Organization (landlord) ID
            claimant_email: Landlord's email
            property_address: Property address
            unit_number: Unit number
            move_in_hash: SHA-256 of move-in inspection
            move_out_hash: SHA-256 of move-out inspection
            damaged_items: List of damaged items with costs
            total_damage_cents: Total damage estimate in cents
            deposit_amount_cents: Security deposit amount in cents
            evidence_hashes: List of evidence file hashes
            
        Returns:
            ClaimSubmissionResult with decision or error
        """
        if not self.enabled:
            return ClaimSubmissionResult(
                success=False,
                error="ClaimsIQ integration not enabled"
            )
        
        # Build incident description
        description = self._build_description(
            property_address=property_address,
            unit_number=unit_number,
            damaged_items=damaged_items,
            total_damage_cents=total_damage_cents,
        )
        description_hash = hashlib.sha256(description.encode()).hexdigest()
        
        # Build claim submission
        claim = ClaimSubmission(
            id=f"prop-deposit-{lease_id}",
            intake_timestamp=datetime.utcnow().isoformat() + "Z",
            policy_snapshot_id=f"org_{org_id}",  # Org acts as policy
            claimant_did=f"did:proveniq:org:{org_id}",
            asset_id=f"lease_{lease_id}",
            incident_vector=IncidentVector(
                type="PROPERTY_DAMAGE",
                location={"type": "Point", "coordinates": [0, 0]},  # Could geocode address
                severity=self._calculate_severity(total_damage_cents, deposit_amount_cents),
                description_hash=description_hash,
            ),
            claim_type=ClaimType.DEPOSIT_DISPUTE,
            lease_id=str(lease_id),
            evidence={
                "move_in_inspection_hash": move_in_hash,
                "move_out_inspection_hash": move_out_hash,
                "evidence_file_hashes": evidence_hashes,
                "damaged_items": damaged_items,
                "total_damage_cents": total_damage_cents,
                "deposit_amount_cents": deposit_amount_cents,
                "property_address": property_address,
                "unit_number": unit_number,
            },
        )
        
        return await self._submit_claim(claim)
    
    async def submit_str_damage_claim(
        self,
        booking_id: UUID,
        org_id: UUID,
        guest_name: str,
        property_address: str,
        unit_number: str,
        pre_stay_hash: Optional[str],
        post_stay_hash: str,
        damaged_items: List[Dict[str, Any]],
        total_damage_cents: int,
        evidence_hashes: List[str],
        platform: str = "manual",  # airbnb, vrbo, etc.
    ) -> ClaimSubmissionResult:
        """
        Submit an STR guest damage claim to ClaimsIQ.
        
        Args:
            booking_id: The booking with damage
            org_id: Organization (host) ID
            guest_name: Guest name
            property_address: Property address
            unit_number: Unit number
            pre_stay_hash: SHA-256 of pre-stay inspection (if exists)
            post_stay_hash: SHA-256 of post-stay inspection
            damaged_items: List of damaged items with costs
            total_damage_cents: Total damage estimate in cents
            evidence_hashes: List of evidence file hashes
            platform: Booking platform (airbnb, vrbo, manual)
            
        Returns:
            ClaimSubmissionResult with decision or error
        """
        if not self.enabled:
            return ClaimSubmissionResult(
                success=False,
                error="ClaimsIQ integration not enabled"
            )
        
        description = self._build_str_description(
            guest_name=guest_name,
            property_address=property_address,
            unit_number=unit_number,
            damaged_items=damaged_items,
            total_damage_cents=total_damage_cents,
            platform=platform,
        )
        description_hash = hashlib.sha256(description.encode()).hexdigest()
        
        claim = ClaimSubmission(
            id=f"prop-str-{booking_id}",
            intake_timestamp=datetime.utcnow().isoformat() + "Z",
            policy_snapshot_id=f"org_{org_id}",
            claimant_did=f"did:proveniq:org:{org_id}",
            asset_id=f"booking_{booking_id}",
            incident_vector=IncidentVector(
                type="STR_GUEST_DAMAGE",
                location={"type": "Point", "coordinates": [0, 0]},
                severity=self._calculate_str_severity(total_damage_cents),
                description_hash=description_hash,
            ),
            claim_type=ClaimType.STR_GUEST_DAMAGE,
            booking_id=str(booking_id),
            evidence={
                "pre_stay_inspection_hash": pre_stay_hash,
                "post_stay_inspection_hash": post_stay_hash,
                "evidence_file_hashes": evidence_hashes,
                "damaged_items": damaged_items,
                "total_damage_cents": total_damage_cents,
                "guest_name": guest_name,
                "platform": platform,
                "property_address": property_address,
                "unit_number": unit_number,
            },
        )
        
        return await self._submit_claim(claim)
    
    async def _submit_claim(self, claim: ClaimSubmission) -> ClaimSubmissionResult:
        """Submit claim to ClaimsIQ API."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/claims",
                    json=claim.model_dump(),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "X-Source-App": "proveniq-properties",
                    },
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return ClaimSubmissionResult(
                        success=True,
                        claim_id=claim.id,
                        decision=data.get("decision", {}).get("decision"),
                        seal=data.get("seal"),
                    )
                elif response.status_code == 409:
                    # Already processed (idempotent)
                    return ClaimSubmissionResult(
                        success=True,
                        claim_id=claim.id,
                        error="Claim already processed"
                    )
                else:
                    return ClaimSubmissionResult(
                        success=False,
                        claim_id=claim.id,
                        error=f"ClaimsIQ returned {response.status_code}: {response.text}"
                    )
                    
        except httpx.TimeoutException:
            return ClaimSubmissionResult(
                success=False,
                claim_id=claim.id,
                error="ClaimsIQ request timed out"
            )
        except httpx.RequestError as e:
            return ClaimSubmissionResult(
                success=False,
                claim_id=claim.id,
                error=f"ClaimsIQ connection error: {str(e)}"
            )
    
    async def get_claim_status(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a submitted claim."""
        if not self.enabled:
            return None
            
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/claims/{claim_id}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )
                
                if response.status_code == 200:
                    return response.json()
                return None
                
        except Exception:
            return None
    
    def _build_description(
        self,
        property_address: str,
        unit_number: str,
        damaged_items: List[Dict[str, Any]],
        total_damage_cents: int,
    ) -> str:
        """Build human-readable claim description."""
        items_text = "\n".join([
            f"- {item['room']}/{item['item']}: ${item.get('estimated_cents', 0) / 100:.2f}"
            for item in damaged_items
        ])
        
        return f"""DEPOSIT DISPUTE CLAIM
Property: {property_address}
Unit: {unit_number}
Total Damage: ${total_damage_cents / 100:.2f}

Damaged Items:
{items_text}

Evidence: Move-in and move-out inspections with SHA-256 hashes.
Generated by PROVENIQ Properties."""
    
    def _build_str_description(
        self,
        guest_name: str,
        property_address: str,
        unit_number: str,
        damaged_items: List[Dict[str, Any]],
        total_damage_cents: int,
        platform: str,
    ) -> str:
        """Build human-readable STR claim description."""
        items_text = "\n".join([
            f"- {item['room']}/{item['item']}: ${item.get('estimated_cents', 0) / 100:.2f}"
            for item in damaged_items
        ])
        
        return f"""STR GUEST DAMAGE CLAIM
Property: {property_address}
Unit: {unit_number}
Guest: {guest_name}
Platform: {platform}
Total Damage: ${total_damage_cents / 100:.2f}

Damaged Items:
{items_text}

Evidence: Pre-stay and post-stay inspections with SHA-256 hashes.
Generated by PROVENIQ Properties."""
    
    def _calculate_severity(self, damage_cents: int, deposit_cents: int) -> int:
        """Calculate severity 1-10 based on damage vs deposit."""
        if deposit_cents == 0:
            return 10
        ratio = damage_cents / deposit_cents
        if ratio <= 0.25:
            return 3
        elif ratio <= 0.5:
            return 5
        elif ratio <= 1.0:
            return 7
        else:
            return 9
    
    def _calculate_str_severity(self, damage_cents: int) -> int:
        """Calculate severity 1-10 for STR claims."""
        if damage_cents < 10000:  # $100
            return 2
        elif damage_cents < 50000:  # $500
            return 4
        elif damage_cents < 100000:  # $1000
            return 6
        elif damage_cents < 500000:  # $5000
            return 8
        else:
            return 10


def get_claimsiq_client() -> ClaimsIQClient:
    """Get ClaimsIQ client singleton."""
    return ClaimsIQClient()
