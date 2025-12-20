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
    # Create turnover status enum
    op.execute("""
        CREATE TYPE turnoverstatus AS ENUM (
            'pending', 'in_progress', 'completed', 'verified', 'flagged'
        )
    """)
    
    # Create turnover photo type enum
    op.execute("""
        CREATE TYPE turnoverphoto AS ENUM (
            'bed', 'kitchen', 'bathroom', 'towels', 'keys', 'inventory'
        )
    """)
    
    # Add ORG_CLEANER to orgrole enum
    op.execute("ALTER TYPE orgrole ADD VALUE IF NOT EXISTS 'ORG_CLEANER'")
    
    # Create turnovers table
    op.create_table(
        'turnovers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('unit_id', UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('checkout_booking_id', UUID(as_uuid=True), sa.ForeignKey('bookings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('checkin_booking_id', UUID(as_uuid=True), sa.ForeignKey('bookings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_cleaner_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('due_by', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'verified', 'flagged', name='turnoverstatus', create_type=False), nullable=False, default='pending', index=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('verified_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cleaner_notes', sa.Text(), nullable=True),
        sa.Column('host_notes', sa.Text(), nullable=True),
        sa.Column('has_damage', sa.Boolean(), default=False),
        sa.Column('needs_restock', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create turnover_photos table
    op.create_table(
        'turnover_photos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('turnover_id', UUID(as_uuid=True), sa.ForeignKey('turnovers.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('photo_type', sa.Enum('bed', 'kitchen', 'bathroom', 'towels', 'keys', 'inventory', name='turnoverphoto', create_type=False), nullable=False),
        sa.Column('object_path', sa.String(500), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('mime_type', sa.String(100), default='image/jpeg'),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_flagged', sa.Boolean(), default=False),
        sa.Column('uploaded_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('uploaded_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    
    # Create turnover_inventory table
    op.create_table(
        'turnover_inventory',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('turnover_id', UUID(as_uuid=True), sa.ForeignKey('turnovers.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_name', sa.String(255), nullable=False),
        sa.Column('location', sa.String(255), default=''),
        sa.Column('expected_quantity', sa.Integer(), default=0),
        sa.Column('actual_quantity', sa.Integer(), default=0),
        sa.Column('is_missing', sa.Boolean(), default=False),
        sa.Column('is_damaged', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(), default=sa.func.now()),
    )
    
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
