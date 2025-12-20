"""Auth schemas."""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.base import BaseSchema


class MagicLinkRequest(BaseSchema):
    """Request to send magic link to tenant."""

    email: EmailStr
    lease_id: str = Field(..., description="UUID of the lease")


class MagicLinkVerify(BaseSchema):
    """Verify magic link token."""

    token: str = Field(..., min_length=32, max_length=128)


class MagicLinkResponse(BaseSchema):
    """Response after magic link verification."""

    firebase_custom_token: str
    message: str = "Token verified. Exchange this for a Firebase ID token."


class CurrentUserResponse(BaseSchema):
    """Current authenticated user info."""

    uid: str
    email: str | None = None
    email_verified: bool = False
    db_user_id: str | None = None
    org_id: str | None = None
    org_role: str | None = None
