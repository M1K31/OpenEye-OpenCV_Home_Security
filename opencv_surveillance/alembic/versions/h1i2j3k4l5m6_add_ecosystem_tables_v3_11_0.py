"""Add ecosystem integration tables v3.11.0

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2025-12-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from backend.database.migration_guards import (
    add_column_if_missing,
    create_index_if_missing,
    create_table_if_missing,
)



# revision identifiers, used by Alembic.
revision = 'h1i2j3k4l5m6'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ecosystem_connections table (v3.11.1: enhanced with multi-device support)
    create_table_if_missing(
        'ecosystem_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('app_name', sa.String(50), nullable=False, index=True),
        sa.Column('app_version', sa.String(20), nullable=True),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('remote_token', sa.String(512), nullable=True),
        sa.Column('local_token', sa.String(512), nullable=False, unique=True, index=True),
        sa.Column('capabilities', sa.String(), default='[]'),
        sa.Column('webhook_url', sa.String(255), nullable=True),
        sa.Column('connected_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        sa.Column('device_info', sa.String(255), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        # v3.11.1: Multi-device/multi-user support
        sa.Column('device_id', sa.String(100), nullable=True, index=True),
        sa.Column('device_name', sa.String(100), nullable=True),
        sa.Column('location', sa.String(100), nullable=True, index=True),
        sa.Column('associated_users', sa.String(), nullable=True),
        sa.Column('subscribed_cameras', sa.String(), nullable=True),
        sa.Column('notification_preferences', sa.String(), default='{}'),
        sa.Column('automation_scope', sa.String(), nullable=True),
        sa.Column('priority', sa.Integer(), default=0),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create notification_dedup table
    create_table_if_missing(
        'notification_dedup',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dedupe_key', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False, index=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create mobile_devices table
    create_table_if_missing(
        'mobile_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('platform', sa.String(20), nullable=False),
        sa.Column('device_token', sa.String(512), nullable=False),
        sa.Column('app_version', sa.String(20), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('notification_preferences', sa.String(), default='{}'),
        sa.Column('registered_at', sa.DateTime(), nullable=True),
        sa.Column('last_active', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create face_training_sessions table
    create_table_if_missing(
        'face_training_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('person_name', sa.String(100), nullable=False),
        sa.Column('camera_id', sa.String(100), nullable=True),
        sa.Column('photos_required', sa.Integer(), default=5),
        sa.Column('auto_capture', sa.Boolean(), default=True),
        sa.Column('photos_captured', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('captured_photos', sa.String(), default='[]'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # v3.11.1: Create user_preferences table
    create_table_if_missing(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True, index=True),
        # Notification Preferences (JSON)
        sa.Column('notification_types', sa.String(), default='{"motion": true, "face_known": true, "face_unknown": true, "doorbell": true, "alarm": true}'),
        sa.Column('notification_channels', sa.String(), default='{"push": true, "email": false, "sms": false}'),
        sa.Column('quiet_hours', sa.String(), default='{"enabled": false, "start": "22:00", "end": "07:00"}'),
        # Camera Access Permissions (JSON array)
        sa.Column('camera_access', sa.String(), nullable=True),
        # Face Recognition Associations (JSON array)
        sa.Column('face_associations', sa.String(), nullable=True),
        # UI Preferences (JSON)
        sa.Column('ui_preferences', sa.String(), default='{"theme": "dark", "default_view": "grid", "show_timestamps": true}'),
        sa.Column('dashboard_preferences', sa.String(), default='{"cameras_per_row": 2, "show_events": true, "max_events": 10}'),
        # Ecosystem Preferences (JSON)
        sa.Column('ecosystem_preferences', sa.String(), default='{"sync_enabled": true, "receive_from": [], "send_to": []}'),
        sa.Column('presence_settings', sa.String(), default='{"home_detection": "face", "away_timeout_minutes": 30}'),
        sa.Column('automation_preferences', sa.String(), default='{"automation_ids": [], "can_trigger": true, "can_receive": true}'),
        # Mobile Push Settings
        sa.Column('push_token', sa.String(512), nullable=True),
        sa.Column('push_platform', sa.String(20), nullable=True),
        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # v3.11.1: Add new columns to users table
    add_column_if_missing('users', sa.Column('display_name', sa.String(100), nullable=True))
    add_column_if_missing('users', sa.Column('avatar_url', sa.String(255), nullable=True))
    add_column_if_missing('users', sa.Column('face_profile_name', sa.String(100), nullable=True))
    add_column_if_missing('users', sa.Column('synced_from', sa.String(50), nullable=True))
    add_column_if_missing('users', sa.Column('synced_at', sa.DateTime(), nullable=True))
    add_column_if_missing('users', sa.Column('external_id', sa.String(255), nullable=True))
    add_column_if_missing('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    
    # Create indexes for ecosystem_connections
    create_index_if_missing('ix_ecosystem_connections_app_host', 'ecosystem_connections', ['app_name', 'host'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_ecosystem_connections_app_host', 'ecosystem_connections')
    
    # v3.11.1: Remove columns from users table
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('display_name')
        batch_op.drop_column('avatar_url')
        batch_op.drop_column('face_profile_name')
        batch_op.drop_column('synced_from')
        batch_op.drop_column('synced_at')
        batch_op.drop_column('external_id')
        batch_op.drop_column('last_login')
    
    # v3.11.1: Drop user_preferences table
    op.drop_table('user_preferences')
    
    # Drop tables
    op.drop_table('face_training_sessions')
    op.drop_table('mobile_devices')
    op.drop_table('notification_dedup')
    op.drop_table('ecosystem_connections')

