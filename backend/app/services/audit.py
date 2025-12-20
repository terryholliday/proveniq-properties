"""Audit logging service."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditAction


class AuditService:
    """Service for creating audit log entries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: UUID,
        org_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        entry = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            user_id=user_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def log_invite_sent(
        self,
        lease_id: UUID,
        org_id: UUID,
        user_id: UUID,
        tenant_email: str,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log tenant invite sent."""
        return await self.log(
            action=AuditAction.INVITE_SENT,
            resource_type="lease",
            resource_id=lease_id,
            org_id=org_id,
            user_id=user_id,
            details={"tenant_email": tenant_email},
            ip_address=ip_address,
        )

    async def log_invite_accepted(
        self,
        lease_id: UUID,
        user_id: UUID,
        tenant_email: str,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log tenant invite accepted."""
        return await self.log(
            action=AuditAction.INVITE_ACCEPTED,
            resource_type="lease",
            resource_id=lease_id,
            user_id=user_id,
            details={"tenant_email": tenant_email},
            ip_address=ip_address,
        )

    async def log_inspection_submitted(
        self,
        inspection_id: UUID,
        org_id: Optional[UUID],
        user_id: UUID,
        content_hash: str,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log inspection submitted."""
        return await self.log(
            action=AuditAction.INSPECTION_SUBMITTED,
            resource_type="inspection",
            resource_id=inspection_id,
            org_id=org_id,
            user_id=user_id,
            details={"content_hash": content_hash},
            ip_address=ip_address,
        )

    async def log_inspection_signed(
        self,
        inspection_id: UUID,
        org_id: Optional[UUID],
        user_id: UUID,
        signature_type: str,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log inspection signed."""
        return await self.log(
            action=AuditAction.INSPECTION_SIGNED,
            resource_type="inspection",
            resource_id=inspection_id,
            org_id=org_id,
            user_id=user_id,
            details={"signature_type": signature_type},
            ip_address=ip_address,
        )

    async def log_vendor_assigned(
        self,
        ticket_id: UUID,
        org_id: UUID,
        user_id: UUID,
        vendor_id: Optional[UUID] = None,
        org_member_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log vendor/member assigned to maintenance ticket."""
        return await self.log(
            action=AuditAction.VENDOR_ASSIGNED,
            resource_type="maintenance_ticket",
            resource_id=ticket_id,
            org_id=org_id,
            user_id=user_id,
            details={
                "vendor_id": str(vendor_id) if vendor_id else None,
                "org_member_id": str(org_member_id) if org_member_id else None,
            },
            ip_address=ip_address,
        )

    async def log_evidence_confirmed(
        self,
        evidence_id: UUID,
        inspection_id: UUID,
        user_id: UUID,
        file_hash: str,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log evidence upload confirmed."""
        return await self.log(
            action=AuditAction.EVIDENCE_CONFIRMED,
            resource_type="inspection_evidence",
            resource_id=evidence_id,
            user_id=user_id,
            details={
                "inspection_id": str(inspection_id),
                "file_hash": file_hash,
            },
            ip_address=ip_address,
        )
