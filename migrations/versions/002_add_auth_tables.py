"""Add authentication tables.

Revision ID: 002_auth
Revises: 001_initial
Create Date: 2024-01-15 11:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = "002_auth"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade():
    """Add authentication and API key tables."""
    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_ip", sa.String(45), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create indexes
    op.create_index("idx_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("idx_api_keys_is_active", "api_keys", ["is_active"])
    op.create_index("idx_api_keys_role", "api_keys", ["role"])

    # Add tracking columns to bugs table
    op.add_column("bugs", sa.Column("submitted_by", sa.String(255), nullable=True))
    op.add_column(
        "bugs",
        sa.Column(
            "submitted_via_api_key", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column("bugs", sa.Column("submission_ip", sa.String(45), nullable=True))
    op.add_column("bugs", sa.Column("user_agent", sa.String(500), nullable=True))
    op.add_column(
        "bugs",
        sa.Column("is_automated", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("bugs", sa.Column("client_version", sa.String(50), nullable=True))

    # Create indexes on new columns
    op.create_index("idx_bugs_submitted_by", "bugs", ["submitted_by"])
    op.create_index("idx_bugs_is_automated", "bugs", ["is_automated"])

    # Foreign key for API key
    op.create_foreign_key(
        "fk_bugs_api_key", "bugs", "api_keys", ["submitted_via_api_key"], ["id"]
    )


def downgrade():
    """Remove authentication tables and columns."""
    # Drop foreign key
    op.drop_constraint("fk_bugs_api_key", "bugs", type_="foreignkey")

    # Drop indexes
    op.drop_index("idx_bugs_is_automated", "bugs")
    op.drop_index("idx_bugs_submitted_by", "bugs")

    # Drop columns from bugs
    op.drop_column("bugs", "client_version")
    op.drop_column("bugs", "is_automated")
    op.drop_column("bugs", "user_agent")
    op.drop_column("bugs", "submission_ip")
    op.drop_column("bugs", "submitted_via_api_key")
    op.drop_column("bugs", "submitted_by")

    # Drop api_keys table
    op.drop_table("api_keys")
