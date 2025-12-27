"""Mason Auto-Agent API Router.

Endpoints for managing Mason's automated recommendations and actions.
All actions require explicit owner approval before execution.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_org_member, AuthenticatedUser
from app.services.mason_agent import MasonAgentService, AgentActionType

router = APIRouter(prefix="/mason-agent", tags=["mason-agent"])


# =============================================================================
# SCHEMAS
# =============================================================================

class AnalyzeRequest(BaseModel):
    property_id: UUID
    unit_id: Optional[UUID] = None
    trigger_type: str  # inspection_complete, maintenance_request, booking_checkout, damage_detected
    trigger_data: dict


class ActionResponse(BaseModel):
    action_id: str
    action_type: str
    title: str
    description: str
    reasoning: str
    estimated_cost_cents: Optional[int]
    urgency: str
    status: str
    created_at: str
    expires_at: str


class ApproveRequest(BaseModel):
    action_id: UUID


class RejectRequest(BaseModel):
    action_id: UUID
    reason: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/analyze", response_model=List[ActionResponse])
async def analyze_and_recommend(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Analyze a trigger event and generate action recommendations.
    
    Trigger types:
    - inspection_complete: Move-out inspection finished
    - maintenance_request: New maintenance ticket
    - booking_checkout: STR guest checked out
    - damage_detected: Damage found in inspection
    
    Returns list of recommended actions pending owner approval.
    """
    agent = MasonAgentService(db)
    
    actions = await agent.analyze_and_recommend(
        org_id=current_user.org_id,
        property_id=request.property_id,
        unit_id=request.unit_id,
        trigger_type=request.trigger_type,
        trigger_data=request.trigger_data,
    )
    
    await db.commit()
    
    return [
        ActionResponse(
            action_id=str(a.action_id),
            action_type=a.action_type.value,
            title=a.title,
            description=a.description,
            reasoning=a.reasoning,
            estimated_cost_cents=a.estimated_cost_cents,
            urgency=a.urgency,
            status=a.status.value,
            created_at=a.created_at.isoformat(),
            expires_at=a.expires_at.isoformat(),
        )
        for a in actions
    ]


@router.get("/pending", response_model=List[ActionResponse])
async def get_pending_actions(
    property_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get all pending actions awaiting owner approval."""
    agent = MasonAgentService(db)
    
    actions = await agent.get_pending_actions(
        org_id=current_user.org_id,
        property_id=property_id,
    )
    
    return [
        ActionResponse(
            action_id=str(a.action_id),
            action_type=a.action_type.value,
            title=a.title,
            description=a.description,
            reasoning=a.reasoning,
            estimated_cost_cents=a.estimated_cost_cents,
            urgency=a.urgency,
            status=a.status.value,
            created_at=a.created_at.isoformat(),
            expires_at=a.expires_at.isoformat(),
        )
        for a in actions
    ]


@router.post("/approve")
async def approve_action(
    request: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Approve a pending action for execution.
    
    GUARDRAIL: Only property owners/managers can approve actions.
    """
    agent = MasonAgentService(db)
    
    result = await agent.approve_action(
        action_id=request.action_id,
        approved_by=current_user.user_id,
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )
    
    await db.commit()
    return result


@router.post("/reject")
async def reject_action(
    request: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Reject a pending action.
    
    Optionally provide a reason for rejection (for audit trail).
    """
    agent = MasonAgentService(db)
    
    result = await agent.reject_action(
        action_id=request.action_id,
        rejected_by=current_user.user_id,
        reason=request.reason,
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )
    
    await db.commit()
    return result


@router.post("/execute")
async def execute_approved_actions(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Execute all approved actions for the organization.
    
    This triggers execution of service scheduling, vendor dispatch, and claim filing
    for all actions that have been approved by the owner.
    
    GUARDRAIL: Only executes actions that were explicitly approved.
    """
    agent = MasonAgentService(db)
    
    results = await agent.execute_approved_actions(org_id=current_user.org_id)
    
    await db.commit()
    
    return {
        "executed": len(results),
        "results": results,
    }


@router.get("/stats")
async def get_agent_stats(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get statistics on Mason agent activity."""
    agent = MasonAgentService(db)
    
    pending = await agent.get_pending_actions(org_id=current_user.org_id)
    
    # Count by type and urgency
    by_type = {}
    by_urgency = {"urgent": 0, "high": 0, "normal": 0, "low": 0}
    
    for action in pending:
        action_type = action.action_type.value
        by_type[action_type] = by_type.get(action_type, 0) + 1
        by_urgency[action.urgency] = by_urgency.get(action.urgency, 0) + 1
    
    return {
        "pending_count": len(pending),
        "by_type": by_type,
        "by_urgency": by_urgency,
        "disclaimer": "All actions require explicit owner approval before execution.",
    }
