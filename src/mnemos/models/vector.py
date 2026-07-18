from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mnemos.core.db import Base
from mnemos.models.entities import new_id, utcnow


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("chk"))
    document_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    revision_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    asset_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationship to embeddings
    embeddings: Mapped[list["ChunkEmbedding"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("emb"))
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chunk: Mapped["DocumentChunk"] = relationship(back_populates="embeddings")

    __table_args__ = (
        Index(
            "ix_chunk_embedding_vector",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class GraphNodeMapping(Base):
    __tablename__ = "graph_node_mappings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("gnm"))
    node_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    node_label: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_region_id: Mapped[str | None] = mapped_column(
        ForeignKey("evidence_regions.id", ondelete="CASCADE"), index=True, nullable=True
    )
    chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
