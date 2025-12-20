"""Organization router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, AuthenticatedUser
from app.models.user import User
from app.models.org import Organization, OrgMembership
from app.models.enums import OrgRole
from app.schemas.org import (
    OrgCreate, OrgUpdate, OrgResponse, OrgWithMembership,
    OrgMemberResponse, OrgMemberListResponse, OrgInviteRequest, OrgInviteResponse,
)

router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrgCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a new organization. Creator becomes ORG_OWNER."""
    # Check if slug is unique
    result = await db.execute(
        select(Organization).where(Organization.slug == data.slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already exists",
        )

    # Ensure user exists in DB
    user_result = await db.execute(
        select(User).where(User.firebase_uid == current_user.uid)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        # Create user record
        user = User(
            firebase_uid=current_user.uid,
            email=current_user.email or "",
            full_name=current_user.claims.get("name"),
        )
        db.add(user)
        await db.flush()

    # Check if user already belongs to an org
    membership_result = await db.execute(
        select(OrgMembership).where(OrgMembership.user_id == user.id)
    )
    if membership_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to an organization",
        )

    # Create organization
    org = Organization(
        name=data.name,
        slug=data.slug,
        email=data.email,
        phone=data.phone,
        address=data.address,
        timezone=data.timezone,
    )
    db.add(org)
    await db.flush()

    # Create membership as owner
    membership = OrgMembership(
        org_id=org.id,
        user_id=user.id,
        role=OrgRole.ORG_OWNER,
    )
    db.add(membership)

    await db.commit()
    await db.refresh(org)

    return OrgResponse.model_validate(org)


@router.get("/me", response_model=OrgWithMembership)
async def get_my_organization(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get current user's organization context."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not belong to an organization",
        )

    result = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    response = OrgWithMembership(
        id=org.id,
        name=org.name,
        slug=org.slug,
        email=org.email,
        phone=org.phone,
        address=org.address,
        timezone=org.timezone,
        created_at=org.created_at,
        updated_at=org.updated_at,
        current_user_role=OrgRole(current_user.org_role),
    )

    return response


@router.patch("/me", response_model=OrgResponse)
async def update_my_organization(
    data: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Update current user's organization (admin/owner only)."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not belong to an organization",
        )

    if current_user.org_role not in ["ORG_OWNER", "ORG_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    result = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    await db.commit()
    await db.refresh(org)

    return OrgResponse.model_validate(org)


@router.get("/members", response_model=OrgMemberListResponse)
async def list_organization_members(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List all members of the current user's organization."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not belong to an organization",
        )

    result = await db.execute(
        select(OrgMembership, User)
        .join(User, OrgMembership.user_id == User.id)
        .where(OrgMembership.org_id == current_user.org_id)
        .order_by(OrgMembership.created_at.desc())
    )
    rows = result.all()

    members = []
    for membership, user in rows:
        members.append(OrgMemberResponse(
            id=str(membership.id),
            email=user.email,
            name=user.full_name,
            role=membership.role.value,
            joined_at=membership.created_at.isoformat(),
            last_active=user.updated_at.isoformat() if user.updated_at else None,
        ))

    return OrgMemberListResponse(members=members)


@router.post("/invite", response_model=OrgInviteResponse)
async def invite_member(
    data: OrgInviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Invite a new member to the organization (admin/owner only)."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not belong to an organization",
        )

    if current_user.org_role not in ["ORG_OWNER", "ORG_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to invite members",
        )

    # Check if user already exists
    user_result = await db.execute(
        select(User).where(User.email == data.email)
    )
    existing_user = user_result.scalar_one_or_none()

    if existing_user:
        # Check if already a member
        membership_result = await db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == existing_user.id,
                OrgMembership.org_id == current_user.org_id,
            )
        )
        if membership_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization",
            )

    # TODO: In production, send actual invite email
    
    return OrgInviteResponse(
        email=data.email,
        role=data.role,
        message=f"Invite sent to {data.email}",
    )
