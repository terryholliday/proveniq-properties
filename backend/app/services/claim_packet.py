"""
PROVENIQ Properties - Claim Packet Service

Generates exportable claim packets for deposit disputes and insurance claims.
Used for Airbnb/VRBO resolution centers and insurance filings.

Output: ZIP file containing:
- claim_summary.json (metadata + hashes)
- claim_summary.pdf (human-readable report)
- evidence/ (all photos with original hashes)
"""

import io
import json
import zipfile
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inspection import Inspection, InspectionItem, InspectionEvidence
from app.models.lease import Lease
from app.models.property import Property, Unit
from app.models.enums import InspectionType, InspectionStatus
from app.services.mason import MasonService
from app.services.storage import get_storage_service


class ClaimPacketService:
    """
    Generates claim packets from inspection diffs.
    
    A claim packet contains:
    1. Claim summary (JSON) - machine-readable
    2. Claim report (PDF) - human-readable
    3. Evidence files - all photos with integrity hashes
    4. Inspection certificates - signed inspection records
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.mason = MasonService(db)
        self.storage = get_storage_service()
    
    async def generate_packet(
        self,
        lease_id: UUID,
        org_id: UUID,
        include_evidence: bool = True,
    ) -> tuple[bytes, str]:
        """
        Generate a claim packet ZIP for a lease.
        
        Args:
            lease_id: The lease to generate packet for
            org_id: Organization ID for authorization
            include_evidence: Whether to include evidence files
            
        Returns:
            Tuple of (zip_bytes, filename)
        """
        # Get lease with property info
        lease = await self._get_lease(lease_id, org_id)
        
        # Get move-in and move-out inspections
        move_in = await self._get_inspection(lease_id, InspectionType.MOVE_IN)
        move_out = await self._get_inspection(lease_id, InspectionType.MOVE_OUT)
        
        if not move_in:
            raise ValueError("No signed move-in inspection found")
        if not move_out:
            raise ValueError("No signed move-out inspection found")
        
        # Build diff
        diff_items = self._build_diff(move_in, move_out)
        
        # Get cost estimates from Mason
        estimates = await self.mason.estimate_diff_costs(
            [
                {
                    "room_name": item["room_name"],
                    "item_name": item["item_name"],
                    "condition_change": item["condition_change"],
                }
                for item in diff_items
            ],
            org_id=org_id,
        )
        
        # Build claim summary
        claim_summary = self._build_claim_summary(
            lease=lease,
            move_in=move_in,
            move_out=move_out,
            diff_items=diff_items,
            estimates=estimates,
        )
        
        # Generate ZIP
        zip_bytes = await self._create_zip(
            claim_summary=claim_summary,
            move_in=move_in,
            move_out=move_out,
            include_evidence=include_evidence,
        )
        
        # Generate filename
        property_name = lease["property_name"].replace(" ", "_")
        unit_number = lease["unit_number"]
        date_str = datetime.utcnow().strftime("%Y%m%d")
        filename = f"claim_packet_{property_name}_{unit_number}_{date_str}.zip"
        
        return zip_bytes, filename
    
    async def _get_lease(self, lease_id: UUID, org_id: UUID) -> Dict[str, Any]:
        """Get lease with property details."""
        result = await self.db.execute(
            select(Lease, Unit, Property)
            .join(Unit, Lease.unit_id == Unit.id)
            .join(Property, Unit.property_id == Property.id)
            .where(
                Lease.id == lease_id,
                Property.org_id == org_id,
            )
        )
        row = result.first()
        
        if not row:
            raise ValueError("Lease not found or access denied")
        
        lease, unit, property = row
        
        return {
            "id": str(lease.id),
            "tenant_email": lease.tenant_email,
            "tenant_name": lease.tenant_name,
            "start_date": lease.start_date.isoformat() if lease.start_date else None,
            "end_date": lease.end_date.isoformat() if lease.end_date else None,
            "deposit_amount_cents": lease.deposit_amount_cents,
            "unit_id": str(unit.id),
            "unit_number": unit.unit_number,
            "property_id": str(property.id),
            "property_name": property.name,
            "property_address": f"{property.address_line1}, {property.city}, {property.state} {property.zip_code}",
        }
    
    async def _get_inspection(
        self,
        lease_id: UUID,
        inspection_type: InspectionType,
    ) -> Optional[Inspection]:
        """Get signed inspection of given type."""
        result = await self.db.execute(
            select(Inspection)
            .options(
                selectinload(Inspection.items).selectinload(InspectionItem.evidence)
            )
            .where(
                Inspection.lease_id == lease_id,
                Inspection.inspection_type == inspection_type,
                Inspection.status == InspectionStatus.SIGNED,
            )
            .order_by(Inspection.inspection_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    def _build_diff(
        self,
        move_in: Inspection,
        move_out: Inspection,
    ) -> List[Dict[str, Any]]:
        """Build diff between move-in and move-out inspections."""
        move_in_items = {
            (i.room_name, i.item_name): i for i in move_in.items
        }
        
        diff_items = []
        
        for item in move_out.items:
            key = (item.room_name, item.item_name)
            move_in_item = move_in_items.get(key)
            
            move_in_condition = move_in_item.condition_rating if move_in_item else 5
            move_out_condition = item.condition_rating or 5
            condition_change = move_out_condition - move_in_condition
            
            # Get evidence
            evidence_list = []
            for ev in item.evidence:
                if ev.is_confirmed:
                    evidence_list.append({
                        "file_hash": ev.file_hash,
                        "mime_type": ev.mime_type,
                        "object_path": ev.object_path,
                        "file_size_bytes": ev.file_size_bytes,
                    })
            
            diff_items.append({
                "room_name": item.room_name,
                "item_name": item.item_name,
                "move_in_condition": move_in_condition,
                "move_out_condition": move_out_condition,
                "condition_change": condition_change,
                "is_damaged": item.is_damaged,
                "damage_description": item.damage_description,
                "evidence": evidence_list,
            })
        
        return diff_items
    
    def _build_claim_summary(
        self,
        lease: Dict[str, Any],
        move_in: Inspection,
        move_out: Inspection,
        diff_items: List[Dict[str, Any]],
        estimates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the claim summary document."""
        # Filter to only damaged items
        damaged_items = [
            item for item in diff_items
            if item["condition_change"] < 0 or item["is_damaged"]
        ]
        
        return {
            "version": "1.0",
            "generated_at": datetime.utcnow().isoformat(),
            "generator": "PROVENIQ Properties",
            
            # Property info
            "property": {
                "name": lease["property_name"],
                "address": lease["property_address"],
                "unit": lease["unit_number"],
            },
            
            # Lease info
            "lease": {
                "id": lease["id"],
                "tenant_email": lease["tenant_email"],
                "tenant_name": lease["tenant_name"],
                "start_date": lease["start_date"],
                "end_date": lease["end_date"],
                "deposit_amount_cents": lease["deposit_amount_cents"],
            },
            
            # Inspection records
            "inspections": {
                "move_in": {
                    "id": str(move_in.id),
                    "date": move_in.inspection_date.isoformat(),
                    "content_hash": move_in.content_hash,
                    "signed_at": move_in.signed_at.isoformat() if move_in.signed_at else None,
                },
                "move_out": {
                    "id": str(move_out.id),
                    "date": move_out.inspection_date.isoformat(),
                    "content_hash": move_out.content_hash,
                    "signed_at": move_out.signed_at.isoformat() if move_out.signed_at else None,
                },
            },
            
            # Damage assessment
            "damages": {
                "total_items_inspected": len(diff_items),
                "items_with_damage": len(damaged_items),
                "items": [
                    {
                        "room": item["room_name"],
                        "item": item["item_name"],
                        "condition_before": item["move_in_condition"],
                        "condition_after": item["move_out_condition"],
                        "change": item["condition_change"],
                        "description": item["damage_description"],
                        "evidence_count": len(item["evidence"]),
                    }
                    for item in damaged_items
                ],
            },
            
            # Cost estimate
            "estimate": {
                "total_cents": estimates["total_estimated_repair_cents"],
                "total_formatted": f"${estimates['total_estimated_repair_cents'] / 100:.2f}",
                "disclaimer": estimates["disclaimer"],
                "items": [
                    {
                        "room": item["room_name"],
                        "item": item["item_name"],
                        "estimated_cents": item.get("estimated_repair_cents", 0),
                    }
                    for item in estimates["items"]
                    if item.get("estimated_repair_cents", 0) > 0
                ],
            },
            
            # Integrity
            "integrity": {
                "move_in_hash": move_in.content_hash,
                "move_out_hash": move_out.content_hash,
                "evidence_hashes": [
                    ev["file_hash"]
                    for item in damaged_items
                    for ev in item["evidence"]
                ],
            },
        }
    
    async def _create_zip(
        self,
        claim_summary: Dict[str, Any],
        move_in: Inspection,
        move_out: Inspection,
        include_evidence: bool,
    ) -> bytes:
        """Create the ZIP file with all claim materials."""
        buffer = io.BytesIO()
        
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add claim summary JSON
            zf.writestr(
                "claim_summary.json",
                json.dumps(claim_summary, indent=2),
            )
            
            # Add README
            readme = self._generate_readme(claim_summary)
            zf.writestr("README.txt", readme)
            
            # Add evidence files if requested
            if include_evidence:
                evidence_index = []
                
                for damage in claim_summary["damages"]["items"]:
                    room = damage["room"]
                    item = damage["item"]
                    
                    # Find matching diff item with evidence
                    for diff_item in self._get_diff_items_from_inspections(move_out):
                        if diff_item["room_name"] == room and diff_item["item_name"] == item:
                            for i, ev in enumerate(diff_item.get("evidence", [])):
                                try:
                                    # Download evidence from storage
                                    file_bytes = await self.storage.download(ev["object_path"])
                                    
                                    # Determine extension
                                    ext = self._get_extension(ev["mime_type"])
                                    filename = f"evidence/{room}_{item}_{i+1}{ext}"
                                    
                                    zf.writestr(filename, file_bytes)
                                    evidence_index.append({
                                        "file": filename,
                                        "hash": ev["file_hash"],
                                        "room": room,
                                        "item": item,
                                    })
                                except Exception as e:
                                    # Log but continue if evidence fetch fails
                                    evidence_index.append({
                                        "file": f"evidence/{room}_{item}_{i+1}_MISSING",
                                        "hash": ev["file_hash"],
                                        "error": str(e),
                                    })
                
                # Add evidence index
                if evidence_index:
                    zf.writestr(
                        "evidence/index.json",
                        json.dumps(evidence_index, indent=2),
                    )
        
        buffer.seek(0)
        return buffer.read()
    
    def _get_diff_items_from_inspections(self, inspection: Inspection) -> List[Dict[str, Any]]:
        """Extract items with evidence from inspection."""
        items = []
        for item in inspection.items:
            evidence_list = []
            for ev in item.evidence:
                if ev.is_confirmed:
                    evidence_list.append({
                        "file_hash": ev.file_hash,
                        "mime_type": ev.mime_type,
                        "object_path": ev.object_path,
                    })
            
            items.append({
                "room_name": item.room_name,
                "item_name": item.item_name,
                "evidence": evidence_list,
            })
        return items
    
    def _generate_readme(self, claim_summary: Dict[str, Any]) -> str:
        """Generate human-readable README for the claim packet."""
        lines = [
            "=" * 60,
            "PROVENIQ PROPERTIES - CLAIM PACKET",
            "=" * 60,
            "",
            f"Generated: {claim_summary['generated_at']}",
            "",
            "PROPERTY INFORMATION",
            "-" * 40,
            f"Property: {claim_summary['property']['name']}",
            f"Address:  {claim_summary['property']['address']}",
            f"Unit:     {claim_summary['property']['unit']}",
            "",
            "TENANT INFORMATION",
            "-" * 40,
            f"Name:  {claim_summary['lease']['tenant_name'] or 'N/A'}",
            f"Email: {claim_summary['lease']['tenant_email']}",
            f"Lease: {claim_summary['lease']['start_date']} to {claim_summary['lease']['end_date']}",
            "",
            "INSPECTION RECORDS",
            "-" * 40,
            f"Move-In:  {claim_summary['inspections']['move_in']['date']}",
            f"  Hash:   {claim_summary['inspections']['move_in']['content_hash']}",
            f"Move-Out: {claim_summary['inspections']['move_out']['date']}",
            f"  Hash:   {claim_summary['inspections']['move_out']['content_hash']}",
            "",
            "DAMAGE SUMMARY",
            "-" * 40,
            f"Items Inspected: {claim_summary['damages']['total_items_inspected']}",
            f"Items Damaged:   {claim_summary['damages']['items_with_damage']}",
            "",
        ]
        
        for damage in claim_summary["damages"]["items"]:
            lines.append(f"  • {damage['room']} / {damage['item']}")
            lines.append(f"    Condition: {damage['condition_before']} → {damage['condition_after']}")
            if damage["description"]:
                lines.append(f"    Description: {damage['description']}")
            lines.append(f"    Evidence: {damage['evidence_count']} file(s)")
            lines.append("")
        
        lines.extend([
            "COST ESTIMATE",
            "-" * 40,
            f"Total Estimated: {claim_summary['estimate']['total_formatted']}",
            "",
            f"⚠️  {claim_summary['estimate']['disclaimer']}",
            "",
            "FILES IN THIS PACKET",
            "-" * 40,
            "• claim_summary.json - Machine-readable claim data",
            "• README.txt - This file",
            "• evidence/ - Photo evidence with integrity hashes",
            "",
            "INTEGRITY VERIFICATION",
            "-" * 40,
            "All inspection records are cryptographically hashed using SHA-256.",
            "Evidence files can be verified against hashes in claim_summary.json.",
            "",
            "For disputes, submit this entire ZIP file to your resolution center.",
            "",
            "=" * 60,
            "© PROVENIQ Technologies - Immutable Evidence",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def _get_extension(self, mime_type: str) -> str:
        """Get file extension from MIME type."""
        extensions = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/heic": ".heic",
            "application/pdf": ".pdf",
        }
        return extensions.get(mime_type, ".bin")
