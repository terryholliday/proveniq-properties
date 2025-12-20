"""Add STR (Short-Term Rental) support

Revision ID: 002_str_support
Revises: 001_initial_schema
Create Date: 2025-12-19

Adds:
- occupancy_model enum and column on properties
- inspection_scope enum and column on inspections
- inspection_signed_by enum and columns on inspections
- booking_status enum
- bookings table
- Constraints for booking-scoped inspections
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_str_support'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create new enums using raw SQL to avoid SQLAlchemy auto-creation issues
    op.execute("CREATE TYPE occupancymodel AS ENUM ('long_term_residential', 'commercial_lease', 'short_term_rental')")
    op.execute("CREATE TYPE inspectionscope AS ENUM ('lease', 'booking')")
    op.execute("CREATE TYPE inspectionsignedby AS ENUM ('TENANT', 'LANDLORD_ORG_MEMBER', 'HOST_SYSTEM')")
    op.execute("CREATE TYPE bookingstatus AS ENUM ('upcoming', 'checked_in', 'checked_out', 'cancelled', 'disputed')")

    # Extend inspection_type enum with STR types
    # Must commit first to use new values in constraints
    op.execute("COMMIT")
    op.execute("ALTER TYPE inspectiontype ADD VALUE IF NOT EXISTS 'pre_stay'")
    op.execute("ALTER TYPE inspectiontype ADD VALUE IF NOT EXISTS 'post_stay'")
    op.execute("BEGIN")

    # Add occupancy_model to properties
    op.add_column(
        'properties',
        sa.Column(
            'occupancy_model',
            sa.Enum('long_term_residential', 'commercial_lease', 'short_term_rental', name='occupancymodel'),
            server_default='long_term_residential',
            nullable=False
        )
    )

    # Add STR fields to inspections
    op.add_column(
        'inspections',
        sa.Column(
            'scope',
            sa.Enum('lease', 'booking', name='inspectionscope'),
            server_default='lease',
            nullable=False
        )
    )
    op.add_column(
        'inspections',
        sa.Column('booking_id', sa.String(255), nullable=True)
    )
    op.add_column(
        'inspections',
        sa.Column(
            'signed_by',
            sa.Enum('TENANT', 'LANDLORD_ORG_MEMBER', 'HOST_SYSTEM', name='inspectionsignedby'),
            nullable=True
        )
    )
    op.add_column(
        'inspections',
        sa.Column('signed_actor_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        'inspections',
        sa.Column('signed_at', sa.DateTime(), nullable=True)
    )

    # Add index on booking_id for efficient lookups
    op.create_index('ix_inspections_booking_id', 'inspections', ['booking_id'])

    # Add foreign key for signed_actor_id
    op.create_foreign_key(
        'fk_inspections_signed_actor_id',
        'inspections', 'users',
        ['signed_actor_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add constraints for booking-scoped inspections
    op.create_check_constraint(
        'ck_inspection_booking_scope',
        'inspections',
        "(scope = 'booking' AND booking_id IS NOT NULL) OR (scope = 'lease')"
    )
    op.create_check_constraint(
        'ck_inspection_scope_type',
        'inspections',
        "(scope = 'booking' AND inspection_type IN ('pre_stay', 'post_stay')) OR "
        "(scope = 'lease' AND inspection_type IN ('move_in', 'move_out', 'periodic'))"
    )

    # Create bookings table using raw SQL to avoid enum recreation
    op.execute("""
        CREATE TABLE bookings (
            id UUID PRIMARY KEY,
            unit_id UUID NOT NULL REFERENCES units(id) ON DELETE CASCADE,
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            external_id VARCHAR(100),
            source VARCHAR(50) NOT NULL DEFAULT 'manual',
            guest_name VARCHAR(255),
            guest_count INTEGER NOT NULL DEFAULT 1,
            check_in_date DATE NOT NULL,
            check_out_date DATE NOT NULL,
            actual_check_in TIMESTAMP,
            actual_check_out TIMESTAMP,
            status bookingstatus NOT NULL DEFAULT 'upcoming',
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # Add indexes for bookings
    op.create_index('ix_bookings_unit_id', 'bookings', ['unit_id'])
    op.create_index('ix_bookings_status', 'bookings', ['status'])
    op.create_index('ix_bookings_external_id', 'bookings', ['external_id'])
    op.create_index('ix_bookings_check_in_date', 'bookings', ['check_in_date'])


def downgrade() -> None:
    # Drop bookings table and indexes
    op.drop_index('ix_bookings_check_in_date')
    op.drop_index('ix_bookings_external_id')
    op.drop_index('ix_bookings_status')
    op.drop_index('ix_bookings_unit_id')
    op.drop_table('bookings')

    # Drop constraints on inspections
    op.drop_constraint('ck_inspection_scope_type', 'inspections')
    op.drop_constraint('ck_inspection_booking_scope', 'inspections')

    # Drop foreign key and index
    op.drop_constraint('fk_inspections_signed_actor_id', 'inspections')
    op.drop_index('ix_inspections_booking_id')

    # Drop STR columns from inspections
    op.drop_column('inspections', 'signed_at')
    op.drop_column('inspections', 'signed_actor_id')
    op.drop_column('inspections', 'signed_by')
    op.drop_column('inspections', 'booking_id')
    op.drop_column('inspections', 'scope')

    # Drop occupancy_model from properties
    op.drop_column('properties', 'occupancy_model')

    # Drop enums (note: can't easily remove values from inspection_type enum)
    op.execute("DROP TYPE IF EXISTS bookingstatus")
    op.execute("DROP TYPE IF EXISTS inspectionsignedby")
    op.execute("DROP TYPE IF EXISTS inspectionscope")
    op.execute("DROP TYPE IF EXISTS occupancymodel")
