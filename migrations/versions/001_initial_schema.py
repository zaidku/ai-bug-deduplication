"""Initial schema migration.

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create initial database schema."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create bugs table
    op.create_table(
        "bugs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("product", sa.String(100), nullable=False),
        sa.Column("component", sa.String(100), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="minor"),
        sa.Column(
            "environment", sa.String(50), nullable=False, server_default="production"
        ),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="pending_review"
        ),
        sa.Column("reporter_email", sa.String(255), nullable=True),
        sa.Column("steps_to_reproduce", postgresql.JSONB(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("attachments", postgresql.JSONB(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column(
            "is_recurring_issue", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column("jira_key", sa.String(50), nullable=True),
        sa.Column("tp_defect_id", sa.String(50), nullable=True),
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
    op.create_index("idx_bugs_product", "bugs", ["product"])
    op.create_index("idx_bugs_status", "bugs", ["status"])
    op.create_index(
        "idx_bugs_created_at",
        "bugs",
        ["created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_bugs_duplicate_of",
        "bugs",
        ["duplicate_of_id"],
        postgresql_where=sa.text("duplicate_of_id IS NOT NULL"),
    )
    op.create_index(
        "idx_bugs_jira_key",
        "bugs",
        ["jira_key"],
        unique=True,
        postgresql_where=sa.text("jira_key IS NOT NULL"),
    )

    # Foreign key for duplicate_of
    op.create_foreign_key(
        "fk_bugs_duplicate_of", "bugs", "bugs", ["duplicate_of_id"], ["id"]
    )

    # Create duplicate_history table
    op.create_table(
        "duplicate_history",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        ),
        sa.Column("original_bug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duplicate_bug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("action_taken", sa.String(50), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index(
        "idx_duplicate_history_original", "duplicate_history", ["original_bug_id"]
    )
    op.create_index(
        "idx_duplicate_history_duplicate", "duplicate_history", ["duplicate_bug_id"]
    )
    op.create_foreign_key(
        "fk_dup_history_original",
        "duplicate_history",
        "bugs",
        ["original_bug_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_dup_history_duplicate",
        "duplicate_history",
        "bugs",
        ["duplicate_bug_id"],
        ["id"],
    )

    # Create low_quality_queue table
    op.create_table(
        "low_quality_queue",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        ),
        sa.Column("bug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("issues", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index("idx_low_quality_status", "low_quality_queue", ["status"])
    op.create_foreign_key(
        "fk_low_quality_bug", "low_quality_queue", "bugs", ["bug_id"], ["id"]
    )

    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("bug_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index("idx_audit_log_action", "audit_log", ["action"])
    op.create_index("idx_audit_log_user", "audit_log", ["user_id"])
    op.create_index(
        "idx_audit_log_created_at",
        "audit_log",
        ["created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    # Create system_metrics table
    op.create_table(
        "system_metrics",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        ),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index("idx_system_metrics_name", "system_metrics", ["metric_name"])
    op.create_index(
        "idx_system_metrics_timestamp",
        "system_metrics",
        ["timestamp"],
        postgresql_ops={"timestamp": "DESC"},
    )


def downgrade():
    """Drop all tables."""
    op.drop_table("system_metrics")
    op.drop_table("audit_log")
    op.drop_table("low_quality_queue")
    op.drop_table("duplicate_history")
    op.drop_table("bugs")
    op.execute("DROP EXTENSION IF EXISTS vector")
