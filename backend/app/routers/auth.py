"""Auth router - Magic link flow for tenant invites."""

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from firebase_admin import auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, AuthenticatedUser
from app.models.user import User
from app.models.lease import Lease, TenantAccess
from app.models.property import Property, Unit
from app.schemas.auth import (
    MagicLinkRequest,
    MagicLinkVerify,
    MagicLinkResponse,
    CurrentUserResponse,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/auth", tags=["auth"])


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/magic-link/request", status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(
    request: Request,
    data: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Request to send magic link to tenant (org member only).
    
    This generates a one-time token and stores its hash.
    The actual email sending would be handled by a separate service.
    """
    from uuid import UUID
    
    # Verify user is org member
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )

    # Get lease
    lease_id = UUID(data.lease_id)
    lease_result = await db.execute(
        select(Lease, Property.org_id)
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(Lease.id == lease_id)
    )
    lease_row = lease_result.first()
    if lease_row:
        lease, lease_org_id = lease_row
    else:
        lease, lease_org_id = None, None

    if not lease:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    # Verify lease belongs to caller's org
    if not lease_org_id or lease_org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lease does not belong to your organization",
        )

    # Verify email matches
    if lease.tenant_email.lower() != data.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email does not match lease tenant email",
        )

    # Generate token
    token = secrets.token_urlsafe(48)
    token_hash = hash_token(token)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    # Update lease
    lease.invite_token_hash = token_hash
    lease.invite_expires_at = expires_at
    lease.invite_sent_at = datetime.utcnow()
    lease.status = "pending"

    # Audit log
    audit = AuditService(db)
    await audit.log_invite_sent(
        lease_id=lease_id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        tenant_email=data.email,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    # In production, send email here with token
    # For now, return success (token would be in email)
    return {
        "message": "Invite sent successfully",
        "lease_id": str(lease_id),
        "tenant_email": data.email,
    }


@router.post("/magic-link/verify", response_model=MagicLinkResponse)
async def verify_magic_link(
    request: Request,
    data: MagicLinkVerify,
    db: AsyncSession = Depends(get_db),
):
    """Verify magic link token and return Firebase custom token.
    
    Client exchanges custom token for Firebase ID token.
    """
    token_hash = hash_token(data.token)

    # Find lease with matching token
    result = await db.execute(
        select(Lease).where(
            Lease.invite_token_hash == token_hash,
            Lease.invite_expires_at > datetime.utcnow(),
        )
    )
    lease = result.scalar_one_or_none()

    if not lease:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Invalidate token (one-time use)
    lease.invite_token_hash = None
    lease.invite_expires_at = None
    lease.status = "active"

    # Find or create user
    user_result = await db.execute(
        select(User).where(User.email == lease.tenant_email)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        # Create Firebase user first
        try:
            firebase_user = auth.create_user(
                email=lease.tenant_email,
                display_name=lease.tenant_name,
            )
        except auth.EmailAlreadyExistsError:
            firebase_user = auth.get_user_by_email(lease.tenant_email)

        # Create local user
        user = User(
            firebase_uid=firebase_user.uid,
            email=lease.tenant_email,
            full_name=lease.tenant_name,
            phone=lease.tenant_phone,
        )
        db.add(user)
        await db.flush()

    # Create tenant access
    access_result = await db.execute(
        select(TenantAccess).where(
            TenantAccess.lease_id == lease.id,
            TenantAccess.tenant_user_id == user.id,
        )
    )
    existing_access = access_result.scalar_one_or_none()

    if not existing_access:
        tenant_access = TenantAccess(
            lease_id=lease.id,
            user_id=user.id,
            is_primary=True,
        )
        db.add(tenant_access)

    # Audit log
    audit = AuditService(db)
    await audit.log_invite_accepted(
        lease_id=lease.id,
        user_id=user.id,
        tenant_email=lease.tenant_email,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    # Generate Firebase custom token
    custom_token = auth.create_custom_token(user.firebase_uid)

    return MagicLinkResponse(
        firebase_custom_token=custom_token.decode("utf-8"),
        message="Token verified. Exchange this for a Firebase ID token.",
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return CurrentUserResponse(
        uid=current_user.uid,
        email=current_user.email,
        email_verified=current_user.email_verified,
        db_user_id=str(current_user.db_user_id) if current_user.db_user_id else None,
        org_id=str(current_user.org_id) if current_user.org_id else None,
        org_role=current_user.org_role,
    )
