"""Golden Master v2.3.1 schema upgrade

Revision ID: 003_golden_master
Revises: 002_str_support
Create Date: 2025-12-19

Golden Master v2.3.1 schema changes:
- New enums: tenant_role, invite_status, inspection_condition, evidence_source, etc.
- jobs_outbox table for async side effects
- tenant_access: role, status, invite timestamps
- inspection_items: room_key/item_key/ordinal/condition pattern
- inspection_evidence: idempotency, storage instance tracking
- inspections: canonical JSON blob, certificate paths
- Split audit_log into audit_log_core + activity_log
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_golden_master'
down_revision = '002_str_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === CREATE NEW ENUMS ===
    op.execute("CREATE TYPE tenantrole AS ENUM ('PRIMARY', 'OCCUPANT')")
    op.execute("CREATE TYPE invitestatus AS ENUM ('INVITED', 'ACCEPTED', 'REVOKED')")
    op.execute("CREATE TYPE inspectioncondition AS ENUM ('good', 'fair', 'damaged', 'not_present')")
    op.execute("CREATE TYPE evidencesource AS ENUM ('tenant', 'landlord', 'vendor', 'system')")
    op.execute("CREATE TYPE signaturetype AS ENUM ('none', 'ed25519', 'p256')")
    op.execute("CREATE TYPE contextverdict AS ENUM ('unknown', 'match', 'mismatch', 'inconclusive')")
    op.execute("CREATE TYPE storageinstancekind AS ENUM ('gcs_generation', 's3_etag')")
    op.execute("CREATE TYPE jobstatus AS ENUM ('pending', 'processing', 'completed', 'failed', 'dead_letter')")

    # === JOBS_OUTBOX TABLE ===
    op.execute("""
        CREATE TABLE jobs_outbox (
            id UUID PRIMARY KEY,
            type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL,
            status jobstatus NOT NULL DEFAULT 'pending',
            unique_scope VARCHAR(500) NOT NULL UNIQUE,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            last_error TEXT,
            run_after TIMESTAMP NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    op.create_index('ix_jobs_outbox_type', 'jobs_outbox', ['type'])
    op.create_index('ix_jobs_outbox_status', 'jobs_outbox', ['status'])

    # === TENANT_ACCESS CHANGES ===
    # Add new columns
    op.add_column('tenant_access', sa.Column('role', sa.Enum('PRIMARY', 'OCCUPANT', name='tenantrole'), server_default='PRIMARY', nullable=False))
    op.add_column('tenant_access', sa.Column('status', sa.Enum('INVITED', 'ACCEPTED', 'REVOKED', name='invitestatus'), server_default='INVITED', nullable=False))
    op.add_column('tenant_access', sa.Column('invited_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('tenant_access', sa.Column('accepted_at', sa.DateTime(), nullable=True))
    op.add_column('tenant_access', sa.Column('revoked_at', sa.DateTime(), nullable=True))
    
    # Rename user_id to tenant_user_id
    op.alter_column('tenant_access', 'user_id', new_column_name='tenant_user_id')
    
    # Drop old column and add unique constraint
    op.drop_column('tenant_access', 'is_primary')
    op.drop_column('tenant_access', 'created_at')
    op.create_unique_constraint('uq_tenant_access_lease_user', 'tenant_access', ['lease_id', 'tenant_user_id'])

    # === INSPECTION CHANGES ===
    # Add Golden Master v2.3.1 columns
    op.add_column('inspections', sa.Column('locked_at', sa.DateTime(), nullable=True))
    op.add_column('inspections', sa.Column('device_signed_at', sa.DateTime(), nullable=True))
    op.add_column('inspections', sa.Column('captured_offline', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('inspections', sa.Column('canonical_json_blob', postgresql.JSONB(), nullable=True))
    op.add_column('inspections', sa.Column('canonical_json_sha256', sa.String(64), nullable=True))
    op.add_column('inspections', sa.Column('certificate_pdf_path', sa.String(500), nullable=True))
    op.add_column('inspections', sa.Column('certificate_pdf_sha256', sa.String(64), nullable=True))

    # === INSPECTION_ITEMS CHANGES ===
    # Rename columns to Golden Master pattern
    op.alter_column('inspection_items', 'room_name', new_column_name='room_key')
    op.alter_column('inspection_items', 'item_name', new_column_name='item_key')
    
    # Add new columns
    op.add_column('inspection_items', sa.Column('ordinal', sa.Integer(), server_default='0', nullable=False))
    op.add_column('inspection_items', sa.Column('condition', sa.Enum('good', 'fair', 'damaged', 'not_present', name='inspectioncondition'), server_default='good', nullable=False))
    
    # Rename condition_notes to notes (simpler)
    op.alter_column('inspection_items', 'condition_notes', new_column_name='notes')
    
    # Drop old columns
    op.drop_column('inspection_items', 'condition_rating')
    op.drop_column('inspection_items', 'is_damaged')
    op.drop_column('inspection_items', 'damage_description')
    
    # Add unique constraint
    op.create_unique_constraint('uq_inspection_item_order', 'inspection_items', ['inspection_id', 'room_key', 'ordinal', 'item_key'])

    # === INSPECTION_EVIDENCE CHANGES ===
    # This is a significant schema change - we'll recreate the table
    op.rename_table('inspection_evidence', 'inspection_evidence_old')
    
    op.execute("""
        CREATE TABLE inspection_evidence (
            id UUID PRIMARY KEY,
            inspection_item_id UUID NOT NULL REFERENCES inspection_items(id) ON DELETE CASCADE,
            object_path VARCHAR(500) NOT NULL UNIQUE,
            mime_type VARCHAR(100) NOT NULL,
            size_bytes BIGINT NOT NULL,
            file_sha256_claimed VARCHAR(64) NOT NULL,
            file_sha256_verified VARCHAR(64),
            confirmed_at TIMESTAMP NOT NULL,
            evidence_source evidencesource NOT NULL DEFAULT 'tenant',
            storage_instance_kind storageinstancekind NOT NULL,
            storage_instance_id VARCHAR(255) NOT NULL,
            confirm_idempotency_key VARCHAR(255) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_evidence_confirm UNIQUE (inspection_item_id, confirm_idempotency_key)
        )
    """)
    # Index created inline in CREATE TABLE
    
    # Migrate data from old table (best effort - some columns won't map directly)
    op.execute("""
        INSERT INTO inspection_evidence (
            id, inspection_item_id, object_path, mime_type, size_bytes,
            file_sha256_claimed, file_sha256_verified, confirmed_at,
            evidence_source, storage_instance_kind, storage_instance_id,
            confirm_idempotency_key, created_at
        )
        SELECT 
            id, item_id, object_path, mime_type, file_size_bytes,
            file_hash, CASE WHEN is_confirmed THEN file_hash ELSE NULL END,
            COALESCE(confirmed_at, created_at),
            'tenant', 'gcs_generation', 'migrated-' || id::text,
            'migrated-' || id::text, created_at
        FROM inspection_evidence_old
    """)
    
    op.drop_table('inspection_evidence_old')

    # === AUDIT LOG CHANGES ===
    # Rename audit_log to audit_log_core
    op.rename_table('audit_log', 'audit_log_core')
    
    # Create activity_log table
    op.execute("""
        CREATE TABLE activity_log (
            id UUID PRIMARY KEY,
            org_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            activity_type VARCHAR(50) NOT NULL,
            resource_type VARCHAR(50),
            resource_id UUID,
            details JSONB,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.create_index('ix_activity_log_org_id', 'activity_log', ['org_id'])
    op.create_index('ix_activity_log_user_id', 'activity_log', ['user_id'])
    op.create_index('ix_activity_log_activity_type', 'activity_log', ['activity_type'])


def downgrade() -> None:
    # Drop activity_log
    op.drop_index('ix_activity_log_activity_type')
    op.drop_index('ix_activity_log_user_id')
    op.drop_index('ix_activity_log_org_id')
    op.drop_table('activity_log')
    
    # Rename audit_log_core back to audit_log
    op.rename_table('audit_log_core', 'audit_log')
    
    # Recreate old inspection_evidence structure
    op.rename_table('inspection_evidence', 'inspection_evidence_new')
    
    op.execute("""
        CREATE TABLE inspection_evidence (
            id UUID PRIMARY KEY,
            item_id UUID NOT NULL REFERENCES inspection_items(id) ON DELETE CASCADE,
            evidence_type VARCHAR(20) NOT NULL DEFAULT 'photo',
            object_path VARCHAR(500) NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            confirmed_at TIMESTAMP,
            file_metadata JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    
    # Migrate data back (best effort)
    op.execute("""
        INSERT INTO inspection_evidence (
            id, item_id, object_path, file_name, mime_type, file_size_bytes,
            file_hash, is_confirmed, confirmed_at, created_at
        )
        SELECT 
            id, inspection_item_id, object_path, 'migrated-file', mime_type, size_bytes,
            file_sha256_claimed, file_sha256_verified IS NOT NULL, confirmed_at, created_at
        FROM inspection_evidence_new
    """)
    
    op.drop_table('inspection_evidence_new')
    op.create_index('ix_inspection_evidence_item_id', 'inspection_evidence', ['item_id'])
    
    # Revert inspection_items changes
    op.drop_constraint('uq_inspection_item_order', 'inspection_items')
    op.add_column('inspection_items', sa.Column('damage_description', sa.Text(), nullable=True))
    op.add_column('inspection_items', sa.Column('is_damaged', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('inspection_items', sa.Column('condition_rating', sa.Integer(), nullable=True))
    op.alter_column('inspection_items', 'notes', new_column_name='condition_notes')
    op.drop_column('inspection_items', 'condition')
    op.drop_column('inspection_items', 'ordinal')
    op.alter_column('inspection_items', 'item_key', new_column_name='item_name')
    op.alter_column('inspection_items', 'room_key', new_column_name='room_name')
    
    # Revert inspection changes
    op.drop_column('inspections', 'certificate_pdf_sha256')
    op.drop_column('inspections', 'certificate_pdf_path')
    op.drop_column('inspections', 'canonical_json_sha256')
    op.drop_column('inspections', 'canonical_json_blob')
    op.drop_column('inspections', 'captured_offline')
    op.drop_column('inspections', 'device_signed_at')
    op.drop_column('inspections', 'locked_at')
    
    # Revert tenant_access changes
    op.drop_constraint('uq_tenant_access_lease_user', 'tenant_access')
    op.add_column('tenant_access', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('tenant_access', sa.Column('is_primary', sa.Boolean(), server_default='true', nullable=False))
    op.alter_column('tenant_access', 'tenant_user_id', new_column_name='user_id')
    op.drop_column('tenant_access', 'revoked_at')
    op.drop_column('tenant_access', 'accepted_at')
    op.drop_column('tenant_access', 'invited_at')
    op.drop_column('tenant_access', 'status')
    op.drop_column('tenant_access', 'role')
    
    # Drop jobs_outbox
    op.drop_index('ix_jobs_outbox_status')
    op.drop_index('ix_jobs_outbox_type')
    op.drop_table('jobs_outbox')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS jobstatus")
    op.execute("DROP TYPE IF EXISTS storageinstancekind")
    op.execute("DROP TYPE IF EXISTS contextverdict")
    op.execute("DROP TYPE IF EXISTS signaturetype")
    op.execute("DROP TYPE IF EXISTS evidencesource")
    op.execute("DROP TYPE IF EXISTS inspectioncondition")
    op.execute("DROP TYPE IF EXISTS invitestatus")
    op.execute("DROP TYPE IF EXISTS tenantrole")
