"""document ingestion foundation
Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("document_versions",sa.Column("id",sa.String(64),primary_key=True),sa.Column("document_id",sa.String(64),sa.ForeignKey("documents.id",ondelete="CASCADE"),nullable=False),sa.Column("version",sa.Integer(),nullable=False),sa.Column("storage_key",sa.String(1024),nullable=False),sa.Column("sha256",sa.String(64),nullable=False),sa.Column("size_bytes",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("document_id","version")); op.create_index("ix_document_versions_document_id","document_versions",["document_id"])
    op.create_table("upload_sessions",sa.Column("id",sa.String(64),primary_key=True),sa.Column("document_id",sa.String(64),sa.ForeignKey("documents.id",ondelete="CASCADE"),nullable=False),sa.Column("object_key",sa.String(1024),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True)); op.create_index("ix_upload_sessions_document_id","upload_sessions",["document_id"])
    op.create_table("processing_jobs",sa.Column("id",sa.String(64),primary_key=True),sa.Column("document_id",sa.String(64),sa.ForeignKey("documents.id",ondelete="CASCADE"),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("stage",sa.String(64),nullable=False),sa.Column("progress_percent",sa.Integer(),nullable=False),sa.Column("warnings",sa.JSON(),nullable=False),sa.Column("error_code",sa.String(128),nullable=True),sa.Column("error_message",sa.Text(),nullable=True),sa.Column("retry_count",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("started_at",sa.DateTime(timezone=True),nullable=True),sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True)); op.create_index("ix_processing_jobs_document_id","processing_jobs",["document_id"])
    op.create_table("evidence_regions",sa.Column("id",sa.String(64),primary_key=True),sa.Column("document_id",sa.String(64),sa.ForeignKey("documents.id",ondelete="CASCADE"),nullable=False),sa.Column("page_or_sheet",sa.String(64),nullable=True),sa.Column("locator",sa.String(255),nullable=True),sa.Column("text_excerpt",sa.Text(),nullable=True),sa.Column("metadata",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False)); op.create_index("ix_evidence_regions_document_id","evidence_regions",["document_id"])

def downgrade() -> None:
    op.drop_table("evidence_regions"); op.drop_table("processing_jobs"); op.drop_table("upload_sessions"); op.drop_table("document_versions")
