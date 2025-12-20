"""Initial PROVENIQ Properties schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-12-19

All 14 tables with commercial rules, money as INTEGER CENTS (BIGINT).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === USERS ===
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firebase_uid', sa.String(128), unique=True, nullable=False, index=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # === ORGANIZATIONS ===
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('timezone', sa.String(50), default='America/New_York'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # === ORG MEMBERSHIPS ===
    op.create_table(
        'org_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.Enum('ORG_OWNER', 'ORG_ADMIN', 'ORG_AGENT', name='orgrole'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # === PROPERTIES ===
    op.create_table(
        'properties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('property_type', sa.Enum('residential', 'commercial', 'mixed', name='propertytype'), nullable=False),
        sa.Column('address_line1', sa.String(255), nullable=False),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('state', sa.String(50), nullable=False),
        sa.Column('zip_code', sa.String(20), nullable=False),
        sa.Column('country', sa.String(50), default='USA'),
        sa.Column('total_leasable_sq_ft', sa.Integer(), nullable=True),
        sa.Column('year_built', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(property_type = 'residential') OR (total_leasable_sq_ft IS NOT NULL)",
            name='ck_property_commercial_sq_ft'
        ),
    )

    # === UNITS ===
    op.create_table(
        'units',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('unit_number', sa.String(50), nullable=False),
        sa.Column('status', sa.Enum('occupied', 'vacant', 'maintenance', name='unitstatus'), nullable=False),
        sa.Column('bedrooms', sa.Integer(), nullable=True),
        sa.Column('bathrooms', sa.Integer(), nullable=True),
        sa.Column('sq_ft', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # === LEASES ===
    op.create_table(
        'leases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('lease_type', sa.Enum('residential_gross', 'commercial_gross', 'commercial_nnn', name='leasetype'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending', 'active', 'terminating', 'ended', 'disputed', name='leasestatus'), nullable=False, index=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        # Money as INTEGER CENTS (BIGINT)
        sa.Column('rent_amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('deposit_amount_cents', sa.BigInteger(), default=0),
        sa.Column('pro_rata_share_bps', sa.Integer(), nullable=True),
        sa.Column('cam_budget_cents', sa.BigInteger(), nullable=True),
        sa.Column('tenant_email', sa.String(255), nullable=False),
        sa.Column('tenant_name', sa.String(255), nullable=True),
        sa.Column('tenant_phone', sa.String(50), nullable=True),
        sa.Column('invite_token_hash', sa.String(128), nullable=True),
        sa.Column('invite_expires_at', sa.DateTime(), nullable=True),
        sa.Column('invite_sent_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(pro_rata_share_bps IS NULL) OR (pro_rata_share_bps > 0 AND pro_rata_share_bps <= 10000)",
            name='ck_lease_pro_rata_share_bps_range'
        ),
    )
    op.create_index('ix_leases_unit_status', 'leases', ['unit_id', 'status'])

    # === TENANT ACCESS ===
    op.create_table(
        'tenant_access',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lease_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('leases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('is_primary', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # === INSPECTIONS ===
    op.create_table(
        'inspections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lease_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('leases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('supplemental_to_inspection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inspections.id', ondelete='SET NULL'), nullable=True),
        sa.Column('inspection_type', sa.Enum('move_in', 'move_out', 'periodic', name='inspectiontype'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'submitted', 'reviewed', 'signed', 'archived', name='inspectionstatus'), nullable=False, index=True),
        sa.Column('inspection_date', sa.DateTime(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('schema_version', sa.Integer(), default=1),
        sa.Column('tenant_signed_at', sa.DateTime(), nullable=True),
        sa.Column('landlord_signed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_inspections_lease_type_status', 'inspections', ['lease_id', 'inspection_type', 'status'])

    # === INSPECTION ITEMS ===
    op.create_table(
        'inspection_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('inspection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inspections.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('room_name', sa.String(100), nullable=False),
        sa.Column('item_name', sa.String(100), nullable=False),
        sa.Column('condition_rating', sa.Integer(), nullable=True),
        sa.Column('condition_notes', sa.Text(), nullable=True),
        sa.Column('is_damaged', sa.Boolean(), default=False),
        sa.Column('damage_description', sa.Text(), nullable=True),
        sa.Column('mason_estimated_repair_cents', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # === INSPECTION EVIDENCE ===
    op.create_table(
        'inspection_evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inspection_items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('evidence_type', sa.Enum('photo', 'video', 'audio', 'document', name='evidencetype'), nullable=False),
        sa.Column('object_path', sa.String(500), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('is_confirmed', sa.Boolean(), default=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('file_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # === VENDORS ===
    op.create_table(
        'vendors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('specialty', sa.Enum('GENERAL', 'PLUMBING', 'HVAC', 'ELECTRICAL', 'ROOFING', name='vendorspecialty'), nullable=False),
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_preferred', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # === MAINTENANCE TICKETS ===
    op.create_table(
        'maintenance_tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_org_member_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('open', 'acknowledged', 'scheduled', 'in_progress', 'completed', 'rejected', name='maintenancestatus'), nullable=False, index=True),
        sa.Column('category', sa.Enum('GENERAL', 'PLUMBING', 'HVAC', 'ELECTRICAL', 'ROOFING', name='vendorspecialty'), nullable=True),
        sa.Column('priority', sa.Integer(), default=3),
        sa.Column('maintenance_cost_estimate_cents', sa.Integer(), nullable=True),
        sa.Column('mason_triage_result', postgresql.JSONB(), nullable=True),
        sa.Column('mason_triaged_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_date', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('is_tenant_visible', sa.Boolean(), default=True),
        sa.Column('tenant_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_maintenance_tickets_unit_status', 'maintenance_tickets', ['unit_id', 'status'])

    # === AUDIT LOG ===
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('action', sa.Enum('invite_sent', 'invite_accepted', 'inspection_submitted', 'inspection_signed', 'vendor_assigned', 'maintenance_triaged', 'lease_created', 'lease_activated', 'evidence_confirmed', name='auditaction'), nullable=False, index=True),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # === MASON LOGS ===
    op.create_table(
        'mason_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('input_data', postgresql.JSONB(), nullable=False),
        sa.Column('output_data', postgresql.JSONB(), nullable=False),
        sa.Column('disclaimer', sa.Text(), nullable=False),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('mason_logs')
    op.drop_table('audit_log')
    op.drop_index('ix_maintenance_tickets_unit_status')
    op.drop_table('maintenance_tickets')
    op.drop_table('vendors')
    op.drop_table('inspection_evidence')
    op.drop_table('inspection_items')
    op.drop_index('ix_inspections_lease_type_status')
    op.drop_table('inspections')
    op.drop_table('tenant_access')
    op.drop_index('ix_leases_unit_status')
    op.drop_table('leases')
    op.drop_table('units')
    op.drop_table('properties')
    op.drop_table('org_memberships')
    op.drop_table('organizations')
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS auditaction')
    op.execute('DROP TYPE IF EXISTS maintenancestatus')
    op.execute('DROP TYPE IF EXISTS vendorspecialty')
    op.execute('DROP TYPE IF EXISTS evidencetype')
    op.execute('DROP TYPE IF EXISTS inspectionstatus')
    op.execute('DROP TYPE IF EXISTS inspectiontype')
    op.execute('DROP TYPE IF EXISTS leasestatus')
    op.execute('DROP TYPE IF EXISTS leasetype')
    op.execute('DROP TYPE IF EXISTS unitstatus')
    op.execute('DROP TYPE IF EXISTS propertytype')
    op.execute('DROP TYPE IF EXISTS orgrole')
