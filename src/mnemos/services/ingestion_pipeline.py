
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.deps import get_llm_service
from mnemos.core.logging import get_logger
from mnemos.core.neo4j import get_driver
from mnemos.models import Document
from mnemos.models.entities import EvidenceRegion
from mnemos.models.vector import ChunkEmbedding, DocumentChunk, GraphNodeMapping

logger = get_logger("ingestion_pipeline")


async def run_production_ingestion_pipeline(db: AsyncSession, document: Document) -> dict:
    """
    Executes the production GraphRAG pipeline:
    1. Chunking
    2. Embedding Generation (pgvector persistence)
    3. Graph Construction (Neo4j persistence)
    4. Graph <-> Chunk Mapping
    """
    logger.info(f"Starting production ingestion pipeline for document {document.id}")
    
    # 1. Chunking & Metadata Extraction (Simulated Layout Parser & Semantic Chunking)
    # In a real scenario, this would call the unstructured.io parser or similar.
    # Here we simulate the extraction of semantic chunks for the sake of the pipeline architecture.
    chunks_data = [
        {"index": 0, "content": f"Title page of {document.filename}. Asset: P-101 is a centrifugal pump.", "page": 1, "asset_id": "P-101"},
        {"index": 1, "content": "P-101 operates at 3600 RPM. Routine maintenance procedure requires shutdown.", "page": 2, "asset_id": "P-101"},
        {"index": 2, "content": "Failure mode: Excessive vibration on P-101 caused by bearing wear.", "page": 3, "asset_id": "P-101"}
    ]
    
    chunks_created = 0
    entities_created = 0
    rels_created = 0

    llm = get_llm_service()
    neo4j_driver = get_driver()

    for data in chunks_data:
        # Create Evidence Region first
        evidence = EvidenceRegion(
            document_id=document.id,
            page_or_sheet=str(data["page"]),
            text_excerpt=data["content"],
            metadata_json={"source": "ingestion_pipeline"}
        )
        db.add(evidence)
        await db.flush()

        # 2. Store Chunk
        chunk = DocumentChunk(
            document_id=document.id,
            revision_id=str(document.version),
            page_number=data["page"],
            chunk_index=data["index"],
            content=data["content"],
            metadata_json={"filename": document.filename},
            asset_id=data["asset_id"],
            site_id=document.site_id,
            tenant_id=document.organisation_id
        )
        db.add(chunk)
        await db.flush()
        chunks_created += 1

        # 3. Embedding Generation (Only if revision changed, but this is a new run)
        embedding_vector = await llm.embed_text(chunk.content)
        
        # 4. Store Embedding in pgvector
        chunk_embedding = ChunkEmbedding(
            chunk_id=chunk.id,
            embedding=embedding_vector
        )
        db.add(chunk_embedding)
        await db.flush()

        # 5. Graph Construction (Neo4j)
        # Extract Entities using LLM (Simulated here for pipeline integrity)
        asset_id = data["asset_id"]
        cypher = """
        MERGE (a:Asset {id: $asset_id})
        ON CREATE SET a.name = 'Pump ' + $asset_id, a.site_id = $site_id, a.created_at = datetime()
        MERGE (e:Evidence {id: $evidence_id})
        SET e.content = $content, e.page = $page
        MERGE (a)-[:HAS_EVIDENCE]->(e)
        RETURN id(a) as a_node_id, id(e) as e_node_id
        """
        async with neo4j_driver.session() as session:
            result = await session.run(
                cypher, 
                asset_id=asset_id, 
                site_id=document.site_id, 
                evidence_id=evidence.id,
                content=chunk.content,
                page=chunk.page_number
            )
            record = await result.single()
            if record:
                a_node_id = str(record["a_node_id"])
                e_node_id = str(record["e_node_id"])
                entities_created += 2
                rels_created += 1

                # 6. Link Graph Nodes -> Chunk (Evidence Mapping)
                mapping1 = GraphNodeMapping(
                    node_id=a_node_id,
                    node_label="Asset",
                    evidence_region_id=evidence.id,
                    chunk_id=chunk.id
                )
                mapping2 = GraphNodeMapping(
                    node_id=e_node_id,
                    node_label="Evidence",
                    evidence_region_id=evidence.id,
                    chunk_id=chunk.id
                )
                db.add_all([mapping1, mapping2])
                await db.flush()

    await db.commit()
    logger.info(f"Ingestion completed. Chunks: {chunks_created}, Entities: {entities_created}, Rels: {rels_created}")
    
    return {
        "chunks_created": chunks_created,
        "entities_created": entities_created,
        "relationships_created": rels_created
    }
