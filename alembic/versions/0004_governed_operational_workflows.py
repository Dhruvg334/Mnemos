"""governed operational workflows

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("rca_cases",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(64), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by", sa.String(64)), sa.Column("approved_by", sa.String(64)), sa.Column("rejected_by", sa.String(64)),
        sa.Column("review_note", sa.Text()), sa.Column("approved_snapshot", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)), sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("closed_at", sa.DateTime(timezone=True)))
    for c in ["organisation_id", "site_id", "asset_id", "created_by"]: op.create_index(f"ix_rca_cases_{c}", "rca_cases", [c])
    op.create_table("rca_observations", sa.Column("id", sa.String(64), primary_key=True), sa.Column("rca_id", sa.String(64), sa.ForeignKey("rca_cases.id", ondelete="CASCADE"), nullable=False), sa.Column("observation_type", sa.String(64), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("evidence_region_id", sa.String(64)), sa.Column("occurred_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_rca_observations_rca_id", "rca_observations", ["rca_id"]); op.create_index("ix_rca_observations_evidence_region_id", "rca_observations", ["evidence_region_id"])
    op.create_table("rca_hypotheses", sa.Column("id", sa.String(64), primary_key=True), sa.Column("rca_id", sa.String(64), sa.ForeignKey("rca_cases.id", ondelete="CASCADE"), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("support_status", sa.String(32), nullable=False), sa.Column("confidence_score", sa.Float()), sa.Column("evidence_region_ids", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_rca_hypotheses_rca_id", "rca_hypotheses", ["rca_id"])
    op.create_table("rca_actions", sa.Column("id", sa.String(64), primary_key=True), sa.Column("rca_id", sa.String(64), sa.ForeignKey("rca_cases.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("owner_id", sa.String(64)), sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_rca_actions_rca_id", "rca_actions", ["rca_id"])
    op.create_table("compliance_requirements", sa.Column("id", sa.String(64), primary_key=True), sa.Column("organisation_id", sa.String(64), nullable=False), sa.Column("code", sa.String(128), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("source", sa.String(255), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("organisation_id", "code"))
    op.create_index("ix_compliance_requirements_organisation_id", "compliance_requirements", ["organisation_id"])
    op.create_table("compliance_evaluations", sa.Column("id", sa.String(64), primary_key=True), sa.Column("organisation_id", sa.String(64), nullable=False), sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False), sa.Column("asset_id", sa.String(64), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False), sa.Column("requirement_ids", sa.JSON(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("overall_result", sa.String(32)), sa.Column("findings", sa.JSON(), nullable=False), sa.Column("missing_evidence", sa.JSON(), nullable=False), sa.Column("conflicts", sa.JSON(), nullable=False), sa.Column("created_by", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("reviewed_by", sa.String(64)), sa.Column("review_note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    for c in ["organisation_id", "site_id", "asset_id", "created_by"]: op.create_index(f"ix_compliance_evaluations_{c}", "compliance_evaluations", [c])
    op.create_table("knowledge_cards", sa.Column("id", sa.String(64), primary_key=True), sa.Column("organisation_id", sa.String(64), nullable=False), sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False), sa.Column("asset_id", sa.String(64), sa.ForeignKey("assets.id", ondelete="SET NULL")), sa.Column("title", sa.String(255), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("author_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("reviewer_id", sa.String(64)), sa.Column("review_note", sa.Text()), sa.Column("supersedes_id", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("submitted_at", sa.DateTime(timezone=True)), sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    for c in ["organisation_id", "site_id", "asset_id", "author_id", "supersedes_id"]: op.create_index(f"ix_knowledge_cards_{c}", "knowledge_cards", [c])


def downgrade() -> None:
    op.drop_table("knowledge_cards")
    op.drop_table("compliance_evaluations")
    op.drop_table("compliance_requirements")
    op.drop_table("rca_actions")
    op.drop_table("rca_hypotheses")
    op.drop_table("rca_observations")
    op.drop_table("rca_cases")
