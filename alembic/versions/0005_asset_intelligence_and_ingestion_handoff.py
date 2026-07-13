"""asset intelligence and ingestion handoff

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_aliases",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "site_id",
            sa.String(length=64),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.String(length=64),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("site_id", "normalized_alias", name="uq_asset_alias_site"),
    )
    op.create_index("ix_asset_aliases_site_id", "asset_aliases", ["site_id"])
    op.create_index("ix_asset_aliases_asset_id", "asset_aliases", ["asset_id"])
    op.create_index(
        "ix_asset_aliases_normalized_alias",
        "asset_aliases",
        ["normalized_alias"],
    )

    op.create_table(
        "asset_relationships",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "site_id",
            sa.String(length=64),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_asset_id",
            sa.String(length=64),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_asset_id",
            sa.String(length=64),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "source_document_id",
            sa.String(length=64),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "evidence_region_id",
            sa.String(length=64),
            sa.ForeignKey("evidence_regions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "site_id",
            "source_asset_id",
            "relationship_type",
            "target_asset_id",
            name="uq_asset_relationship",
        ),
    )
    op.create_index(
        "ix_asset_relationships_site_id",
        "asset_relationships",
        ["site_id"],
    )
    op.create_index(
        "ix_asset_relationships_source_asset_id",
        "asset_relationships",
        ["source_asset_id"],
    )
    op.create_index(
        "ix_asset_relationships_target_asset_id",
        "asset_relationships",
        ["target_asset_id"],
    )
    op.create_index(
        "ix_asset_relationships_source_document_id",
        "asset_relationships",
        ["source_document_id"],
    )
    op.create_index(
        "ix_asset_relationships_evidence_region_id",
        "asset_relationships",
        ["evidence_region_id"],
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=64),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organisation_id",
            sa.String(length=64),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_id",
            sa.String(length=64),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("gateway", sa.String(length=64), nullable=False),
        sa.Column("chunks_created", sa.Integer(), nullable=False),
        sa.Column("entities_created", sa.Integer(), nullable=False),
        sa.Column("relationships_created", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=128), nullable=True),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("response_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingestion_runs_document_id", "ingestion_runs", ["document_id"])
    op.create_index(
        "ix_ingestion_runs_organisation_id",
        "ingestion_runs",
        ["organisation_id"],
    )
    op.create_index("ix_ingestion_runs_site_id", "ingestion_runs", ["site_id"])

    op.create_table(
        "ingestion_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "ingestion_run_id",
            sa.String(length=64),
            sa.ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ingestion_events_ingestion_run_id",
        "ingestion_events",
        ["ingestion_run_id"],
    )


def downgrade() -> None:
    op.drop_table("ingestion_events")
    op.drop_table("ingestion_runs")
    op.drop_table("asset_relationships")
    op.drop_table("asset_aliases")
