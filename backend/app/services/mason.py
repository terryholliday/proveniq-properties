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
