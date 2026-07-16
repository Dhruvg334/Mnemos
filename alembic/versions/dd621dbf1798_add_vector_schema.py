"""add vector schema

Revision ID: dd621dbf1798
Revises: 0007
Create Date: 2026-07-16 15:20:53.419457
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'dd621dbf1798'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table('document_chunks',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('document_id', sa.String(length=64), nullable=False),
    sa.Column('revision_id', sa.String(length=64), nullable=True),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('metadata', sa.JSON(), nullable=False),
    sa.Column('asset_id', sa.String(length=64), nullable=True),
    sa.Column('site_id', sa.String(length=64), nullable=True),
    sa.Column('tenant_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_chunks'))
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_asset_id'), 'document_chunks', ['asset_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_site_id'), 'document_chunks', ['site_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_tenant_id'), 'document_chunks', ['tenant_id'], unique=False)

    import pgvector.sqlalchemy
    op.create_table('chunk_embeddings',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('chunk_id', sa.String(length=64), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1536), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], name=op.f('fk_chunk_embeddings_chunk_id_document_chunks'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chunk_embeddings'))
    )
    op.create_index(op.f('ix_chunk_embeddings_chunk_id'), 'chunk_embeddings', ['chunk_id'], unique=False)
    # HNSW Index
    op.execute('CREATE INDEX ix_chunk_embedding_vector ON chunk_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);')

    op.create_table('graph_node_mappings',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('node_id', sa.String(length=255), nullable=False),
    sa.Column('node_label', sa.String(length=128), nullable=False),
    sa.Column('evidence_region_id', sa.String(length=64), nullable=True),
    sa.Column('chunk_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], name=op.f('fk_graph_node_mappings_chunk_id_document_chunks'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evidence_region_id'], ['evidence_regions.id'], name=op.f('fk_graph_node_mappings_evidence_region_id_evidence_regions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_graph_node_mappings'))
    )
    op.create_index(op.f('ix_graph_node_mappings_node_id'), 'graph_node_mappings', ['node_id'], unique=False)


def downgrade() -> None:
    op.drop_table('graph_node_mappings')
    op.drop_table('chunk_embeddings')
    op.drop_table('document_chunks')
