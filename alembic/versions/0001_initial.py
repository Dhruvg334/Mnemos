"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "sites",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organisation_id", sa.String(length=64), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("organisation_id", "code"),
    )
    op.create_index("ix_sites_organisation_id", "sites", ["organisation_id"])
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organisation_id", sa.String(length=64), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.String(length=64), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("user_id", "organisation_id", "site_id", name="uq_membership_scope"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_organisation_id", "memberships", ["organisation_id"])
    op.create_index("ix_memberships_site_id", "memberships", ["site_id"])
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("site_id", sa.String(length=64), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_tag", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("site_id", "asset_tag"),
    )
    op.create_index("ix_assets_site_id", "assets", ["site_id"])
    op.create_index("ix_assets_asset_tag", "assets", ["asset_tag"])
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organisation_id", sa.String(length=64), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.String(length=64), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_organisation_id", "documents", ["organisation_id"])
    op.create_index("ix_documents_site_id", "documents", ["site_id"])
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_table(
        "queries",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organisation_id", sa.String(length=64), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.String(length=64), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("confidence_label", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("missing_evidence", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("related_entities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_queries_organisation_id", "queries", ["organisation_id"])
    op.create_index("ix_queries_site_id", "queries", ["site_id"])
    op.create_index("ix_queries_user_id", "queries", ["user_id"])
    op.create_table(
        "citations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("query_id", sa.String(length=64), sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("support_status", sa.String(length=32), nullable=False),
        sa.Column("document_title", sa.String(length=512), nullable=False),
        sa.Column("page_or_sheet", sa.String(length=64), nullable=True),
        sa.Column("locator", sa.String(length=255), nullable=True),
        sa.Column("text_excerpt", sa.Text(), nullable=True),
        sa.Column("access_allowed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_citations_query_id", "citations", ["query_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organisation_id", sa.String(length=64), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_organisation_id", "audit_events", ["organisation_id"])
    op.create_index("ix_audit_events_site_id", "audit_events", ["site_id"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("citations")
    op.drop_table("queries")
    op.drop_table("documents")
    op.drop_table("assets")
    op.drop_table("memberships")
    op.drop_table("sites")
    op.drop_table("users")
    op.drop_table("organisations")
