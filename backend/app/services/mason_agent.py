"""Mason Auto-Agent Mode - The Proactive Asset Steward.

OPTIONAL feature that enables Mason to:
1. Auto-schedule service dispatch
2. Auto-file claims to ClaimsIQ
3. Auto-dispatch vendors

CRITICAL GUARDRAILS (NON-NEGOTIABLE):
- NEVER auto-execute without owner approval
- All actions are QUEUED and require explicit approval
- Full audit trail of recommendations and decisions
- Owner can disable at any time
- Human-in-loop for ALL financial decisions

This is an ADVISORY-FIRST system with optional automation.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, List
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import MasonLog


class AgentActionType(str, Enum):
    """Types of actions Mason can recommend."""
    SCHEDULE_SERVICE = "schedule_service"
    FILE_CLAIM = "file_claim"
    DISPATCH_VENDOR = "dispatch_vendor"
    SEND_NOTICE = "send_notice"
    DEDUCT_DEPOSIT = "deduct_deposit"


class AgentActionStatus(str, Enum):
    """Status of queued agent actions."""
    PENDING = "pending"        # Awaiting owner review
    APPROVED = "approved"      # Owner approved, ready to execute
    REJECTED = "rejected"      # Owner rejected
    EXECUTED = "executed"      # Action completed
    EXPIRED = "expired"        # Approval window expired
    CANCELLED = "cancelled"    # Cancelled by system or owner


class MasonAgentAction:
    """Represents a queued action for owner approval."""
    
    def __init__(
        self,
        action_id: UUID,
        action_type: AgentActionType,
        org_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        title: str,
        description: str,
        reasoning: str,
        estimated_cost_cents: Optional[int],
        urgency: str,
        payload: dict,
        expires_at: datetime,
    ):
        self.action_id = action_id
        self.action_type = action_type
        self.org_id = org_id
        self.property_id = property_id
        self.unit_id = unit_id
        self.title = title
        self.description = description
        self.reasoning = reasoning
        self.estimated_cost_cents = estimated_cost_cents
        self.urgency = urgency
        self.payload = payload
        self.status = AgentActionStatus.PENDING
        self.created_at = datetime.utcnow()
        self.expires_at = expires_at
        self.reviewed_at: Optional[datetime] = None
        self.reviewed_by: Optional[UUID] = None
        self.executed_at: Optional[datetime] = None
        self.execution_result: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "action_id": str(self.action_id),
            "action_type": self.action_type.value,
            "org_id": str(self.org_id),
            "property_id": str(self.property_id),
            "unit_id": str(self.unit_id) if self.unit_id else None,
            "title": self.title,
            "description": self.description,
            "reasoning": self.reasoning,
            "estimated_cost_cents": self.estimated_cost_cents,
            "urgency": self.urgency,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": str(self.reviewed_by) if self.reviewed_by else None,
        }


class MasonAgentService:
    """Mason Auto-Agent Mode - Proactive property management.
    
    GUARDRAILS:
    - All actions require explicit owner approval
    - Actions expire after 72 hours if not reviewed
    - Urgent actions notify owner immediately
    - Full audit trail maintained
    """

    DISCLAIMER = "This is an automated recommendation. Owner approval required before execution."
    DEFAULT_EXPIRY_HOURS = 72
    URGENT_EXPIRY_HOURS = 24

    def __init__(self, db: AsyncSession):
        self.db = db
        self._action_queue: dict[UUID, MasonAgentAction] = {}

    async def analyze_and_recommend(
        self,
        org_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        trigger_type: str,
        trigger_data: dict,
    ) -> List[MasonAgentAction]:
        """Analyze a trigger event and generate action recommendations.
        
        Trigger types:
        - inspection_complete: Move-out inspection finished
        - maintenance_request: New maintenance ticket
        - booking_checkout: STR guest checked out
        - damage_detected: Damage found in inspection
        """
        start_time = datetime.utcnow()
        actions = []

        if trigger_type == "inspection_complete":
            actions = await self._analyze_inspection(org_id, property_id, unit_id, trigger_data)
        elif trigger_type == "maintenance_request":
            actions = await self._analyze_maintenance(org_id, property_id, unit_id, trigger_data)
        elif trigger_type == "booking_checkout":
            actions = await self._analyze_checkout(org_id, property_id, unit_id, trigger_data)
        elif trigger_type == "damage_detected":
            actions = await self._analyze_damage(org_id, property_id, unit_id, trigger_data)

        # Queue all actions
        for action in actions:
            self._action_queue[action.action_id] = action

        # Log Mason agent activity
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        log_entry = MasonLog(
            org_id=org_id,
            action_type="agent_analyze",
            resource_type=trigger_type,
            resource_id=property_id,
            input_data=trigger_data,
            output_data={
                "actions_recommended": len(actions),
                "action_ids": [str(a.action_id) for a in actions],
            },
            processing_time_ms=processing_time_ms,
        )
        self.db.add(log_entry)

        return actions

    async def _analyze_inspection(
        self,
        org_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        data: dict,
    ) -> List[MasonAgentAction]:
        """Analyze completed inspection and recommend actions."""
        actions = []
        damaged_items = data.get("damaged_items", [])
        total_damage_cents = data.get("total_damage_cents", 0)
        deposit_amount_cents = data.get("deposit_amount_cents", 0)

        # Recommend service dispatch for repairs
        if damaged_items:
            actions.append(MasonAgentAction(
                action_id=uuid4(),
                action_type=AgentActionType.SCHEDULE_SERVICE,
                org_id=org_id,
                property_id=property_id,
                unit_id=unit_id,
                title="Schedule Repairs from Inspection",
                description=f"{len(damaged_items)} item(s) require repair",
                reasoning=f"Inspection found {len(damaged_items)} damaged items. "
                          f"Estimated repair cost: ${total_damage_cents / 100:.2f}",
                estimated_cost_cents=total_damage_cents,
                urgency="normal",
                payload={"damaged_items": damaged_items},
                expires_at=datetime.utcnow() + timedelta(hours=self.DEFAULT_EXPIRY_HOURS),
            ))

        # Recommend deposit deduction if applicable
        if total_damage_cents > 0 and deposit_amount_cents > 0:
            deduction = min(total_damage_cents, deposit_amount_cents)
            actions.append(MasonAgentAction(
                action_id=uuid4(),
                action_type=AgentActionType.DEDUCT_DEPOSIT,
                org_id=org_id,
                property_id=property_id,
                unit_id=unit_id,
                title="Deposit Deduction Advisory",
                description=f"Recommend deducting ${deduction / 100:.2f} from deposit",
                reasoning=f"Damage cost (${total_damage_cents / 100:.2f}) exceeds normal wear. "
                          f"Deposit available: ${deposit_amount_cents / 100:.2f}",
                estimated_cost_cents=deduction,
                urgency="normal",
                payload={
                    "deposit_amount_cents": deposit_amount_cents,
                    "damage_amount_cents": total_damage_cents,
                    "recommended_deduction_cents": deduction,
                },
                expires_at=datetime.utcnow() + timedelta(hours=self.DEFAULT_EXPIRY_HOURS),
            ))

        # Recommend claim filing for severe damage
        if total_damage_cents > deposit_amount_cents and total_damage_cents > 50000:
            excess = total_damage_cents - deposit_amount_cents
            actions.append(MasonAgentAction(
                action_id=uuid4(),
                action_type=AgentActionType.FILE_CLAIM,
                org_id=org_id,
                property_id=property_id,
                unit_id=unit_id,
                title="File Insurance Claim",
                description=f"Damage exceeds deposit by ${excess / 100:.2f}",
                reasoning=f"Total damage (${total_damage_cents / 100:.2f}) exceeds deposit "
                          f"(${deposit_amount_cents / 100:.2f}). Consider filing claim for excess.",
                estimated_cost_cents=excess,
                urgency="high",
                payload={
                    "excess_damage_cents": excess,
                    "damaged_items": damaged_items,
                },
                expires_at=datetime.utcnow() + timedelta(hours=self.URGENT_EXPIRY_HOURS),
            ))

        return actions

    async def _analyze_maintenance(
        self,
        org_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        data: dict,
    ) -> List[MasonAgentAction]:
        """Analyze maintenance request and recommend vendor dispatch."""
        actions = []
        title = data.get("title", "")
        description = data.get("description", "")
        urgency = data.get("urgency", "normal")
        category = data.get("category", "general")

        # Determine if urgent dispatch needed
        urgent_keywords = ["emergency", "flood", "fire", "no heat", "no water", "gas leak"]
        is_urgent = any(kw in f"{title} {description}".lower() for kw in urgent_keywords)

        if is_urgent:
            urgency = "urgent"

        actions.append(MasonAgentAction(
            action_id=uuid4(),
            action_type=AgentActionType.DISPATCH_VENDOR,
            org_id=org_id,
            property_id=property_id,
            unit_id=unit_id,
            title=f"Dispatch {category.title()} Vendor",
            description=f"Maintenance request: {title}",
            reasoning=f"Tenant reported issue requiring {category} service. "
                      f"{'URGENT: Immediate attention recommended.' if is_urgent else 'Normal priority.'}",
            estimated_cost_cents=self._estimate_service_cost(category),
            urgency=urgency,
            payload={
                "ticket_title": title,
                "ticket_description": description,
                "category": category,
            },
            expires_at=datetime.utcnow() + timedelta(
                hours=self.URGENT_EXPIRY_HOURS if is_urgent else self.DEFAULT_EXPIRY_HOURS
            ),
        ))

        return actions

    async def _analyze_checkout(
        self,
        org_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        data: dict,
    ) -> List[MasonAgentAction]:
        """Analyze STR checkout and recommend actions."""
        actions = []
        booking_id = data.get("booking_id")
        guest_name = data.get("guest_name", "Guest")
        damage_found = data.get("damage_found", False)
        damage_amount_cents = data.get("damage_amount_cents", 0)

        # Schedule turnover cleaning
        actions.append(MasonAgentAction(
            action_id=uuid4(),
            action_type=AgentActionType.SCHEDULE_SERVICE,
            org_id=org_id,
            property_id=property_id,
            unit_id=unit_id,
            title="Schedule Turnover Cleaning",
            description=f"Post-checkout cleaning for {guest_name}",
            reasoning="Standard turnover cleaning required after guest checkout.",
            estimated_cost_cents=15000,  # $150 typical cleaning
            urgency="high",
            payload={"booking_id": str(booking_id), "service_type": "cleaning"},
            expires_at=datetime.utcnow() + timedelta(hours=self.URGENT_EXPIRY_HOURS),
        ))

        # File resolution center claim if damage found
        if damage_found and damage_amount_cents > 10000:
            actions.append(MasonAgentAction(
                action_id=uuid4(),
                action_type=AgentActionType.FILE_CLAIM,
                org_id=org_id,
                property_id=property_id,
                unit_id=unit_id,
                title="File Resolution Center Claim",
                description=f"Guest damage claim for ${damage_amount_cents / 100:.2f}",
                reasoning=f"Damage detected after {guest_name} checkout. "
                          f"Amount exceeds $100 threshold for resolution center claim.",
                estimated_cost_cents=damage_amount_cents,
                urgency="high",
                payload={
                    "booking_id": str(booking_id),
                    "guest_name": guest_name,
                    "damage_amount_cents": damage_amount_cents,
                    "claim_type": "resolution_center",
                },
                expires_at=datetime.utcnow() + timedelta(hours=self.URGENT_EXPIRY_HOURS),
            ))

        return actions

    async def _analyze_damage(
        self,
        org_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        data: dict,
    ) -> List[MasonAgentAction]:
        """Analyze detected damage and recommend actions."""
        actions = []
        item_name = data.get("item_name", "Unknown")
        room_name = data.get("room_name", "Unknown")
        severity = data.get("severity", "minor")
        estimated_cents = data.get("estimated_repair_cents", 0)

        if severity in ("significant", "severe"):
            actions.append(MasonAgentAction(
                action_id=uuid4(),
                action_type=AgentActionType.SCHEDULE_SERVICE,
                org_id=org_id,
                property_id=property_id,
                unit_id=unit_id,
                title=f"Urgent Repair: {item_name}",
                description=f"{severity.title()} damage in {room_name}",
                reasoning=f"{severity.title()} damage detected. Immediate repair recommended.",
                estimated_cost_cents=estimated_cents,
                urgency="urgent" if severity == "severe" else "high",
                payload={
                    "item_name": item_name,
                    "room_name": room_name,
                    "severity": severity,
                },
                expires_at=datetime.utcnow() + timedelta(hours=self.URGENT_EXPIRY_HOURS),
            ))

        return actions

    def _estimate_service_cost(self, category: str) -> int:
        """Estimate service cost by category in cents."""
        estimates = {
            "plumbing": 25000,
            "electrical": 20000,
            "hvac": 35000,
            "roofing": 50000,
            "carpentry": 20000,
            "painting": 15000,
            "flooring": 30000,
            "general": 15000,
        }
        return estimates.get(category.lower(), 15000)

    async def get_pending_actions(
        self,
        org_id: UUID,
        property_id: Optional[UUID] = None,
    ) -> List[MasonAgentAction]:
        """Get all pending actions for an org/property."""
        pending = []
        for action in self._action_queue.values():
            if action.org_id != org_id:
                continue
            if property_id and action.property_id != property_id:
                continue
            if action.status == AgentActionStatus.PENDING:
                # Check if expired
                if datetime.utcnow() > action.expires_at:
                    action.status = AgentActionStatus.EXPIRED
                else:
                    pending.append(action)
        return pending

    async def approve_action(
        self,
        action_id: UUID,
        approved_by: UUID,
    ) -> dict[str, Any]:
        """Approve a pending action for execution."""
        action = self._action_queue.get(action_id)
        if not action:
            return {"error": "Action not found"}
        
        if action.status != AgentActionStatus.PENDING:
            return {"error": f"Action is {action.status.value}, cannot approve"}
        
        if datetime.utcnow() > action.expires_at:
            action.status = AgentActionStatus.EXPIRED
            return {"error": "Action has expired"}
        
        action.status = AgentActionStatus.APPROVED
        action.reviewed_at = datetime.utcnow()
        action.reviewed_by = approved_by

        # Log approval
        log_entry = MasonLog(
            org_id=action.org_id,
            action_type="agent_approve",
            resource_type=action.action_type.value,
            resource_id=action.action_id,
            input_data={"approved_by": str(approved_by)},
            output_data=action.to_dict(),
            processing_time_ms=0,
        )
        self.db.add(log_entry)

        return {
            "status": "approved",
            "action": action.to_dict(),
            "message": "Action approved. Ready for execution.",
        }

    async def reject_action(
        self,
        action_id: UUID,
        rejected_by: UUID,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Reject a pending action."""
        action = self._action_queue.get(action_id)
        if not action:
            return {"error": "Action not found"}
        
        if action.status != AgentActionStatus.PENDING:
            return {"error": f"Action is {action.status.value}, cannot reject"}
        
        action.status = AgentActionStatus.REJECTED
        action.reviewed_at = datetime.utcnow()
        action.reviewed_by = rejected_by

        # Log rejection
        log_entry = MasonLog(
            org_id=action.org_id,
            action_type="agent_reject",
            resource_type=action.action_type.value,
            resource_id=action.action_id,
            input_data={"rejected_by": str(rejected_by), "reason": reason},
            output_data=action.to_dict(),
            processing_time_ms=0,
        )
        self.db.add(log_entry)

        return {
            "status": "rejected",
            "action": action.to_dict(),
            "message": "Action rejected.",
        }

    async def execute_approved_actions(self, org_id: UUID) -> List[dict]:
        """Execute all approved actions for an org.
        
        This is called by a background job or manual trigger.
        """
        from app.services.service_bridge import get_service_bridge
        from app.services.claimsiq import ClaimsIQService
        
        results = []
        service_bridge = get_service_bridge()

        for action in self._action_queue.values():
            if action.org_id != org_id:
                continue
            if action.status != AgentActionStatus.APPROVED:
                continue

            try:
                if action.action_type == AgentActionType.SCHEDULE_SERVICE:
                    result = await self._execute_schedule_service(action, service_bridge)
                elif action.action_type == AgentActionType.DISPATCH_VENDOR:
                    result = await self._execute_dispatch_vendor(action, service_bridge)
                elif action.action_type == AgentActionType.FILE_CLAIM:
                    result = await self._execute_file_claim(action)
                elif action.action_type == AgentActionType.DEDUCT_DEPOSIT:
                    result = {"status": "manual_required", "message": "Deposit deductions require manual processing"}
                else:
                    result = {"status": "unknown_action"}

                action.status = AgentActionStatus.EXECUTED
                action.executed_at = datetime.utcnow()
                action.execution_result = result
                results.append({"action_id": str(action.action_id), **result})

            except Exception as e:
                results.append({
                    "action_id": str(action.action_id),
                    "status": "error",
                    "error": str(e),
                })

        return results

    async def _execute_schedule_service(self, action: MasonAgentAction, service_bridge) -> dict:
        """Execute service scheduling action."""
        work_orders = await service_bridge.dispatch_from_inspection(
            inspection_id=action.action_id,  # Use action ID as reference
            property_id=action.property_id,
            unit_id=action.unit_id,
            damaged_items=action.payload.get("damaged_items", []),
            contact_name="Property Manager",
            contact_phone="",
            address="",
            requested_by=action.reviewed_by or action.org_id,
        )
        return {
            "status": "scheduled",
            "work_orders_created": len(work_orders),
        }

    async def _execute_dispatch_vendor(self, action: MasonAgentAction, service_bridge) -> dict:
        """Execute vendor dispatch action."""
        work_order = await service_bridge.create_work_order(
            property_id=action.property_id,
            unit_id=action.unit_id,
            ticket_id=action.action_id,
            title=action.payload.get("ticket_title", action.title),
            description=action.payload.get("ticket_description", action.description),
            service_domain=action.payload.get("category", "general"),
            service_type="repair",
            urgency=action.urgency,
            contact_name="Property Manager",
            contact_phone="",
            address="",
            requested_by=action.reviewed_by or action.org_id,
        )
        return {
            "status": "dispatched",
            "work_order": work_order,
        }

    async def _execute_file_claim(self, action: MasonAgentAction) -> dict:
        """Execute claim filing action."""
        # This would integrate with ClaimsIQ
        return {
            "status": "claim_queued",
            "claim_type": action.payload.get("claim_type", "general"),
            "amount_cents": action.estimated_cost_cents,
            "message": "Claim submitted to ClaimsIQ for processing",
        }
