"""Firebase JWT verification middleware and security utilities."""

import hashlib
import json
from typing import Any, Optional
from uuid import UUID

import firebase_admin
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    if settings.google_application_credentials:
        cred = credentials.Certificate(settings.google_application_credentials)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()

security = HTTPBearer()


class AuthenticatedUser:
    """Represents an authenticated user from Firebase JWT."""

    def __init__(
        self,
        uid: str,
        email: Optional[str] = None,
        email_verified: bool = False,
        claims: Optional[dict[str, Any]] = None,
    ):
        self.uid = uid
        self.email = email
        self.email_verified = email_verified
        self.claims = claims or {}
        self.db_user_id: Optional[UUID] = None
        self.org_id: Optional[UUID] = None
        self.org_role: Optional[str] = None


async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthenticatedUser:
    """Verify Firebase JWT and return authenticated user.
    
    This middleware NEVER mints JWTs - it only verifies tokens issued by Firebase.
    """
    token = credentials.credentials

    try:
        decoded_token = auth.verify_id_token(token)
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        uid=decoded_token["uid"],
        email=decoded_token.get("email"),
        email_verified=decoded_token.get("email_verified", False),
        claims=decoded_token,
    )


async def get_current_user(
    auth_user: AuthenticatedUser = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    """Get current user with database context (user_id, org_id, org_role)."""
    from app.models.user import User
    from app.models.org import OrgMembership

    # Find user by Firebase UID
    result = await db.execute(
        select(User).where(User.firebase_uid == auth_user.uid)
    )
    user = result.scalar_one_or_none()

    if user:
        auth_user.db_user_id = user.id

        # Get org membership
        membership_result = await db.execute(
            select(OrgMembership).where(OrgMembership.user_id == user.id)
        )
        membership = membership_result.scalar_one_or_none()

        if membership:
            auth_user.org_id = membership.org_id
            auth_user.org_role = membership.role.value

    return auth_user


def require_org_member(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require user to be a member of an organization."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )
    return current_user


def require_org_admin(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require user to be an org admin or owner."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )
    if current_user.org_role not in ["ORG_OWNER", "ORG_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_org_owner(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require user to be the org owner."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )
    if current_user.org_role != "ORG_OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner privileges required",
        )
    return current_user


def compute_content_hash(data: dict[str, Any], schema_version: int = 1) -> str:
    """Compute SHA-256 hash of canonical JSON for inspection immutability.
    
    Args:
        data: Dictionary containing inspection header, ordered items, and evidence
        schema_version: Schema version for forward compatibility
        
    Returns:
        Hex-encoded SHA-256 hash
    """
    # Add schema version to data
    canonical_data = {
        "schema_version": schema_version,
        **data,
    }
    
    # Canonical JSON: sorted keys, no whitespace
    canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
    
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()
