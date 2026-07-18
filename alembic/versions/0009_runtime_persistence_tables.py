"""Add durable runtime persistence tables (P0 #4, P0 #5).

Adds:
- runtime_checkpoints     : durable workflow state snapshots
- runtime_audit_entries   : durable agent/tool/decision audit log
- runtime_investigation_events : durable investigation event log
- runtime_approval_requests   : durable approval queue (P0 #3)

Revision ID: 0009
Revises: dd621dbf1798
Create Date: 2026-07-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "dd621dbf1798"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # runtime_checkpoints (P0 #4)
    # ------------------------------------------------------------------
    op.create_table(
        "runtime_checkpoints",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("investigation_id", sa.String(64), nullable=False),
        sa.Column("checkpoint_type", sa.String(32), nullable=False),
        sa.Column("phase", sa.String(64), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True, server_default=""),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("state_snapshot", sa.JSON(), nullable=False),
        sa.Column("event_log_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_runtime_checkpoints_investigation_id",
        "runtime_checkpoints",
        ["investigation_id"],
    )
    op.create_index(
        "ix_runtime_checkpoints_created_at",
        "runtime_checkpoints",
        ["created_at"],
    )

    # ------------------------------------------------------------------
    # runtime_audit_entries (P0 #5)
    # ------------------------------------------------------------------
    op.create_table(
        "runtime_audit_entries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("investigation_id", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("guardrail_checks", sa.JSON(), nullable=True),
        sa.Column("guardrail_verdicts", sa.JSON(), nullable=True),
        sa.Column("approval_gate", sa.String(64), nullable=True),
        sa.Column("approval_decision", sa.String(32), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_runtime_audit_entries_investigation_id",
        "runtime_audit_entries",
        ["investigation_id"],
    )
    op.create_index(
        "ix_runtime_audit_entries_trace_id",
        "runtime_audit_entries",
        ["trace_id"],
    )
    op.create_index(
        "ix_runtime_audit_entries_agent_name",
        "runtime_audit_entries",
        ["agent_name"],
    )
    op.create_index(
        "ix_runtime_audit_entries_action",
        "runtime_audit_entries",
        ["action"],
    )
    op.create_index(
        "ix_runtime_audit_entries_tool_name",
        "runtime_audit_entries",
        ["tool_name"],
    )
    op.create_index(
        "ix_runtime_audit_entries_created_at",
        "runtime_audit_entries",
        ["created_at"],
    )

    # ------------------------------------------------------------------
    # runtime_investigation_events (P0 #5)
    # ------------------------------------------------------------------
    op.create_table(
        "runtime_investigation_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("investigation_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(64), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("data_json", sa.JSON(), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_runtime_investigation_events_investigation_id",
        "runtime_investigation_events",
        ["investigation_id"],
    )
    op.create_index(
        "ix_runtime_investigation_events_event_type",
        "runtime_investigation_events",
        ["event_type"],
    )
    op.create_index(
        "ix_runtime_investigation_events_phase",
        "runtime_investigation_events",
        ["phase"],
    )
    op.create_index(
        "ix_runtime_investigation_events_agent_name",
        "runtime_investigation_events",
        ["agent_name"],
    )
    op.create_index(
        "ix_runtime_investigation_events_created_at",
        "runtime_investigation_events",
        ["created_at"],
    )

    # ------------------------------------------------------------------
    # runtime_approval_requests (P0 #3 durable approval queue)
    # ------------------------------------------------------------------
    op.create_table(
        "runtime_approval_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("investigation_id", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("gate_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True, server_default=""),
        sa.Column("findings_json", sa.JSON(), nullable=True),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("triggered_by", sa.String(128), nullable=True, server_default="supervisor"),
        # status: pending | approved | rejected | changes_requested | expired | cancelled
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        # Reviewer fields — populated when decision submitted
        sa.Column("reviewer", sa.String(255), nullable=True),
        sa.Column("reviewer_decision", sa.String(32), nullable=True),
        sa.Column("reviewer_comments", sa.Text(), nullable=True),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        # Frozen investigation state so the workflow can resume
        sa.Column("state_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_runtime_approval_requests_investigation_id",
        "runtime_approval_requests",
        ["investigation_id"],
    )
    op.create_index(
        "ix_runtime_approval_requests_status",
        "runtime_approval_requests",
        ["status"],
    )
    op.create_index(
        "ix_runtime_approval_requests_created_at",
        "runtime_approval_requests",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("runtime_approval_requests")
    op.drop_table("runtime_investigation_events")
    op.drop_table("runtime_audit_entries")
    op.drop_table("runtime_checkpoints")
