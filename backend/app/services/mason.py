"""Mason AI service - The Asset Steward.

Deterministic advisor-only rules engine for:
- Inspection Diff Cost Estimation
- Maintenance Triage
- Deposit Advisory

GUARDRAILS (NON-NEGOTIABLE):
- Always label outputs as non-binding estimates
- Never auto-deny maintenance
- Never auto-dispatch vendors
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import MasonLog
from app.models.enums import VendorSpecialty

# Cost estimation rules (per-item base costs in cents)
REPAIR_COST_MATRIX = {
    # Room -> Item -> Base repair cost in cents
    "kitchen": {
        "sink": 15000,
        "faucet": 12000,
        "countertop": 50000,
        "cabinet": 25000,
        "appliance": 75000,
        "flooring": 40000,
        "default": 20000,
    },
    "bathroom": {
        "toilet": 25000,
        "sink": 15000,
        "faucet": 12000,
        "shower": 45000,
        "bathtub": 60000,
        "tile": 35000,
        "mirror": 10000,
        "default": 18000,
    },
    "bedroom": {
        "carpet": 35000,
        "flooring": 40000,
        "closet_door": 15000,
        "window": 25000,
        "blinds": 8000,
        "default": 15000,
    },
    "living_room": {
        "carpet": 45000,
        "flooring": 50000,
        "window": 25000,
        "blinds": 8000,
        "fireplace": 80000,
        "default": 20000,
    },
    "default": {
        "door": 20000,
        "wall": 15000,
        "ceiling": 25000,
        "light_fixture": 10000,
        "outlet": 8000,
        "switch": 5000,
        "default": 15000,
    },
}

# Condition degradation multipliers
CONDITION_MULTIPLIERS = {
    -4: 1.0,   # 5 -> 1: Major damage
    -3: 0.8,   # 5 -> 2 or 4 -> 1
    -2: 0.5,   # Moderate degradation
    -1: 0.25,  # Minor degradation
    0: 0.0,    # No change
}

# Maintenance category mapping
CATEGORY_KEYWORDS = {
    VendorSpecialty.PLUMBING: ["leak", "water", "drain", "pipe", "faucet", "toilet", "shower", "sink"],
    VendorSpecialty.HVAC: ["heat", "cool", "ac", "air", "furnace", "thermostat", "vent"],
    VendorSpecialty.ELECTRICAL: ["electric", "outlet", "switch", "light", "power", "wire", "breaker"],
    VendorSpecialty.ROOFING: ["roof", "shingle", "gutter", "leak", "ceiling"],
}


class MasonService:
    """Mason AI - The Asset Steward."""

    DISCLAIMER = "This is a non-binding advisory estimate. Actual costs may vary."

    def __init__(self, db: AsyncSession):
        self.db = db

    async def estimate_item_repair_cost(
        self,
        room_name: str,
        item_name: str,
        condition_change: int,
    ) -> int:
        """Estimate repair cost for a single item in cents."""
        room_key = room_name.lower().replace(" ", "_")
        item_key = item_name.lower().replace(" ", "_")

        # Get room costs or default
        room_costs = REPAIR_COST_MATRIX.get(room_key, REPAIR_COST_MATRIX["default"])
        
        # Get item base cost or default
        base_cost = room_costs.get(item_key, room_costs.get("default", 15000))
        
        # Apply condition multiplier
        multiplier = CONDITION_MULTIPLIERS.get(condition_change, 0.5)
        
        return int(base_cost * multiplier)

    async def estimate_diff_costs(
        self,
        diff_items: list[dict[str, Any]],
        org_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Estimate repair costs for inspection diff.
        
        Args:
            diff_items: List of items with room_name, item_name, condition_change
            org_id: Organization ID for logging
            
        Returns:
            Dict with item estimates and totals
        """
        start_time = datetime.utcnow()
        
        results = []
        total_cents = 0

        for item in diff_items:
            if item.get("condition_change", 0) >= 0:
                # No degradation, no cost
                results.append({
                    **item,
                    "estimated_repair_cents": 0,
                })
                continue

            estimated_cents = await self.estimate_item_repair_cost(
                room_name=item["room_name"],
                item_name=item["item_name"],
                condition_change=item["condition_change"],
            )
            
            results.append({
                **item,
                "estimated_repair_cents": estimated_cents,
            })
            total_cents += estimated_cents

        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        output = {
            "items": results,
            "total_estimated_repair_cents": total_cents,
            "disclaimer": self.DISCLAIMER,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Log Mason decision
        if org_id:
            log_entry = MasonLog(
                org_id=org_id,
                action_type="diff_cost_estimate",
                resource_type="inspection_diff",
                resource_id=UUID("00000000-0000-0000-0000-000000000000"),  # No specific resource
                input_data={"diff_items": diff_items},
                output_data=output,
                processing_time_ms=processing_time_ms,
            )
            self.db.add(log_entry)

        return output

    async def triage_maintenance(
        self,
        ticket_id: UUID,
        title: str,
        description: str,
        org_id: UUID,
    ) -> dict[str, Any]:
        """Triage a maintenance ticket.
        
        GUARDRAILS:
        - Never auto-deny
        - Never auto-dispatch
        - Advisory only
        """
        start_time = datetime.utcnow()
        
        text = f"{title} {description}".lower()

        # Determine category
        suggested_category = VendorSpecialty.GENERAL
        max_matches = 0
        
        for category, keywords in CATEGORY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > max_matches:
                max_matches = matches
                suggested_category = category

        # Determine priority (1-5, 1=highest)
        urgent_keywords = ["emergency", "urgent", "flood", "fire", "no heat", "no water", "broken"]
        high_keywords = ["leak", "not working", "broken", "damage"]
        
        if any(kw in text for kw in urgent_keywords):
            suggested_priority = 1
        elif any(kw in text for kw in high_keywords):
            suggested_priority = 2
        else:
            suggested_priority = 3

        # Estimate cost (rough heuristic)
        estimated_cost_cents = None
        if suggested_category == VendorSpecialty.PLUMBING:
            estimated_cost_cents = 25000
        elif suggested_category == VendorSpecialty.HVAC:
            estimated_cost_cents = 35000
        elif suggested_category == VendorSpecialty.ELECTRICAL:
            estimated_cost_cents = 20000
        elif suggested_category == VendorSpecialty.ROOFING:
            estimated_cost_cents = 50000
        else:
            estimated_cost_cents = 15000

        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        output = {
            "ticket_id": str(ticket_id),
            "suggested_category": suggested_category.value,
            "suggested_priority": suggested_priority,
            "estimated_cost_cents": estimated_cost_cents,
            "reasoning": f"Based on keywords, categorized as {suggested_category.value} with priority {suggested_priority}.",
            "disclaimer": self.DISCLAIMER,
            "triaged_at": datetime.utcnow().isoformat(),
        }

        # Log Mason decision
        log_entry = MasonLog(
            org_id=org_id,
            action_type="maintenance_triage",
            resource_type="maintenance_ticket",
            resource_id=ticket_id,
            input_data={"title": title, "description": description},
            output_data=output,
            processing_time_ms=processing_time_ms,
        )
        self.db.add(log_entry)

        return output

    async def analyze_damage(
        self,
        item_name: str,
        room_name: str,
        condition_before: int,
        condition_after: int,
        description: str,
        photo_hashes: list[str] = None,
        org_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Analyze damage to an inspection item.
        
        Returns:
            Dict with damage severity, estimated cost, recommended action
        """
        start_time = datetime.utcnow()
        condition_change = condition_after - condition_before
        
        # Determine damage severity
        if condition_change >= 0:
            severity = "none"
            severity_score = 0
        elif condition_change == -1:
            severity = "minor"
            severity_score = 25
        elif condition_change == -2:
            severity = "moderate"
            severity_score = 50
        elif condition_change == -3:
            severity = "significant"
            severity_score = 75
        else:
            severity = "severe"
            severity_score = 100
        
        # Estimate repair cost
        estimated_cost = await self.estimate_item_repair_cost(
            room_name=room_name,
            item_name=item_name,
            condition_change=condition_change,
        )
        
        # Determine recommended action
        if severity == "none":
            recommended_action = "no_action"
            action_description = "No damage detected. No action required."
        elif severity == "minor":
            recommended_action = "document_only"
            action_description = "Minor wear. Document for records, no immediate repair needed."
        elif severity == "moderate":
            recommended_action = "schedule_repair"
            action_description = "Moderate damage. Schedule repair before next occupancy."
        elif severity == "significant":
            recommended_action = "immediate_repair"
            action_description = "Significant damage. Repair required before next occupancy."
        else:
            recommended_action = "professional_assessment"
            action_description = "Severe damage. Recommend professional assessment and potential claim."
        
        # Check if claimable
        deposit_deductible = severity in ("moderate", "significant", "severe")
        claim_eligible = severity in ("significant", "severe") and estimated_cost >= 50000
        
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        output = {
            "item_name": item_name,
            "room_name": room_name,
            "condition_before": condition_before,
            "condition_after": condition_after,
            "severity": severity,
            "severity_score": severity_score,
            "estimated_repair_cents": estimated_cost,
            "recommended_action": recommended_action,
            "action_description": action_description,
            "deposit_deductible": deposit_deductible,
            "claim_eligible": claim_eligible,
            "photo_evidence_count": len(photo_hashes) if photo_hashes else 0,
            "disclaimer": self.DISCLAIMER,
            "analyzed_at": datetime.utcnow().isoformat(),
        }
        
        # Log Mason decision
        if org_id:
            log_entry = MasonLog(
                org_id=org_id,
                action_type="damage_analysis",
                resource_type="inspection_item",
                resource_id=UUID("00000000-0000-0000-0000-000000000000"),
                input_data={
                    "item_name": item_name,
                    "room_name": room_name,
                    "condition_before": condition_before,
                    "condition_after": condition_after,
                    "description": description,
                },
                output_data=output,
                processing_time_ms=processing_time_ms,
            )
            self.db.add(log_entry)
        
        return output

    async def generate_deposit_advisory(
        self,
        inspection_id: UUID,
        diff_items: list[dict[str, Any]],
        deposit_amount_cents: int,
        org_id: UUID,
    ) -> dict[str, Any]:
        """Generate deposit deduction advisory for move-out.
        
        GUARDRAILS:
        - Advisory only, not binding
        - Always show reasoning
        - Never auto-deduct
        """
        start_time = datetime.utcnow()
        
        # Analyze all items
        deductible_items = []
        total_deduction = 0
        
        for item in diff_items:
            condition_change = item.get("condition_change", 0)
            if condition_change >= 0:
                continue
            
            analysis = await self.analyze_damage(
                item_name=item["item_name"],
                room_name=item["room_name"],
                condition_before=item.get("condition_before", 5),
                condition_after=item.get("condition_after", 5),
                description=item.get("description", ""),
            )
            
            if analysis["deposit_deductible"]:
                deductible_items.append({
                    **item,
                    "analysis": analysis,
                })
                total_deduction += analysis["estimated_repair_cents"]
        
        # Cap at deposit amount
        recommended_deduction = min(total_deduction, deposit_amount_cents)
        recommended_refund = deposit_amount_cents - recommended_deduction
        
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        output = {
            "inspection_id": str(inspection_id),
            "deposit_amount_cents": deposit_amount_cents,
            "total_damage_cost_cents": total_deduction,
            "recommended_deduction_cents": recommended_deduction,
            "recommended_refund_cents": recommended_refund,
            "deductible_items": deductible_items,
            "deduction_percentage": round(recommended_deduction / deposit_amount_cents * 100, 1) if deposit_amount_cents > 0 else 0,
            "disclaimer": self.DISCLAIMER,
            "advisory_note": "This is a non-binding advisory. Owner must review and approve all deductions.",
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        # Log Mason decision
        log_entry = MasonLog(
            org_id=org_id,
            action_type="deposit_advisory",
            resource_type="inspection",
            resource_id=inspection_id,
            input_data={
                "diff_items_count": len(diff_items),
                "deposit_amount_cents": deposit_amount_cents,
            },
            output_data=output,
            processing_time_ms=processing_time_ms,
        )
        self.db.add(log_entry)
        
        return output
