"""STR Turnover support - cleaner roles and turnover workflow.

Revision ID: 004_str_turnover
Revises: 003_golden_master
Create Date: 2024-12-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '004_str_turnover'
down_revision = '003_golden_master'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create turnover status enum (IF NOT EXISTS)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE turnoverstatus AS ENUM (
                'pending', 'in_progress', 'completed', 'verified', 'flagged'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    # Create turnover photo type enum (IF NOT EXISTS)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE turnoverphoto AS ENUM (
                'bed', 'kitchen', 'bathroom', 'towels', 'keys', 'inventory'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    # Add ORG_CLEANER to orgrole enum
    op.execute("ALTER TYPE orgrole ADD VALUE IF NOT EXISTS 'ORG_CLEANER'")
    
    # Create turnovers table using raw SQL to bypass SQLAlchemy enum auto-creation
    op.execute("""
        CREATE TABLE turnovers (
            id UUID PRIMARY KEY,
            unit_id UUID NOT NULL REFERENCES units(id) ON DELETE CASCADE,
            checkout_booking_id UUID REFERENCES bookings(id) ON DELETE SET NULL,
            checkin_booking_id UUID REFERENCES bookings(id) ON DELETE SET NULL,
            assigned_cleaner_id UUID REFERENCES users(id) ON DELETE SET NULL,
            scheduled_date TIMESTAMP NOT NULL,
            due_by TIMESTAMP,
            status turnoverstatus NOT NULL DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            verified_at TIMESTAMP,
            verified_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            cleaner_notes TEXT,
            host_notes TEXT,
            has_damage BOOLEAN DEFAULT FALSE,
            needs_restock BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.create_index('ix_turnovers_unit_id', 'turnovers', ['unit_id'])
    op.create_index('ix_turnovers_assigned_cleaner_id', 'turnovers', ['assigned_cleaner_id'])
    op.create_index('ix_turnovers_status', 'turnovers', ['status'])
    
    # Create turnover_photos table using raw SQL
    op.execute("""
        CREATE TABLE turnover_photos (
            id UUID PRIMARY KEY,
            turnover_id UUID NOT NULL REFERENCES turnovers(id) ON DELETE CASCADE,
            photo_type turnoverphoto NOT NULL,
            object_path VARCHAR(500) NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            mime_type VARCHAR(100) DEFAULT 'image/jpeg',
            file_size_bytes INTEGER NOT NULL,
            notes TEXT,
            is_flagged BOOLEAN DEFAULT FALSE,
            uploaded_at TIMESTAMP DEFAULT NOW(),
            uploaded_by_id UUID REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    op.create_index('ix_turnover_photos_turnover_id', 'turnover_photos', ['turnover_id'])
    
    # Create turnover_inventory table
    op.execute("""
        CREATE TABLE turnover_inventory (
            id UUID PRIMARY KEY,
            turnover_id UUID NOT NULL REFERENCES turnovers(id) ON DELETE CASCADE,
            item_name VARCHAR(255) NOT NULL,
            location VARCHAR(255) DEFAULT '',
            expected_quantity INTEGER DEFAULT 0,
            actual_quantity INTEGER DEFAULT 0,
            is_missing BOOLEAN DEFAULT FALSE,
            is_damaged BOOLEAN DEFAULT FALSE,
            notes TEXT,
            checked_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.create_index('ix_turnover_inventory_turnover_id', 'turnover_inventory', ['turnover_id'])
    
    # Create unique constraint for photo type per turnover
    op.create_unique_constraint(
        'uq_turnover_photo_type',
        'turnover_photos',
        ['turnover_id', 'photo_type']
    )


def downgrade() -> None:
    op.drop_constraint('uq_turnover_photo_type', 'turnover_photos', type_='unique')
    op.drop_table('turnover_inventory')
    op.drop_table('turnover_photos')
    op.drop_table('turnovers')
    op.execute("DROP TYPE IF EXISTS turnoverphoto")
    op.execute("DROP TYPE IF EXISTS turnoverstatus")
