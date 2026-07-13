"""agent query execution

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("queries", sa.Column("context_asset_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("queries", sa.Column("context_document_ids", sa.JSON(), nullable=False, server_default="[]"))

    op.create_table(
        "query_claims",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("query_id", sa.String(length=64), sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("support_status", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("query_id", "external_id"),
    )
    op.create_index("ix_query_claims_query_id", "query_claims", ["query_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("query_id", sa.String(length=64), sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organisation_id", sa.String(length=64), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("gateway", sa.String(length=32), nullable=False),
        sa.Column("pipeline_version", sa.String(length=128), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("response_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_runs_query_id", "agent_runs", ["query_id"])
    op.create_index("ix_agent_runs_organisation_id", "agent_runs", ["organisation_id"])
    op.create_index("ix_agent_runs_site_id", "agent_runs", ["site_id"])

    op.create_table(
        "query_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("query_id", sa.String(length=64), sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_query_events_query_id", "query_events", ["query_id"])

    op.add_column("citations", sa.Column("claim_id", sa.String(length=64), nullable=True))
    op.add_column("citations", sa.Column("document_id", sa.String(length=64), nullable=True))
    op.add_column("citations", sa.Column("document_version", sa.Integer(), nullable=True))
    op.add_column("citations", sa.Column("chunk_id", sa.String(length=128), nullable=True))
    op.add_column("citations", sa.Column("evidence_region_id", sa.String(length=64), nullable=True))
    op.add_column("citations", sa.Column("retrieval_sources", sa.JSON(), nullable=False, server_default="[]"))
    op.create_foreign_key("fk_citations_claim_id_query_claims", "citations", "query_claims", ["claim_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_citations_claim_id", "citations", ["claim_id"])
    op.create_index("ix_citations_document_id", "citations", ["document_id"])
    op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"])
    op.create_index("ix_citations_evidence_region_id", "citations", ["evidence_region_id"])


def downgrade() -> None:
    op.drop_column("queries", "context_document_ids")
    op.drop_column("queries", "context_asset_ids")
    op.drop_index("ix_citations_evidence_region_id", table_name="citations")
    op.drop_index("ix_citations_chunk_id", table_name="citations")
    op.drop_index("ix_citations_document_id", table_name="citations")
    op.drop_index("ix_citations_claim_id", table_name="citations")
    op.drop_constraint("fk_citations_claim_id_query_claims", "citations", type_="foreignkey")
    op.drop_column("citations", "retrieval_sources")
    op.drop_column("citations", "evidence_region_id")
    op.drop_column("citations", "chunk_id")
    op.drop_column("citations", "document_version")
    op.drop_column("citations", "document_id")
    op.drop_column("citations", "claim_id")
    op.drop_table("query_events")
    op.drop_table("agent_runs")
    op.drop_table("query_claims")
