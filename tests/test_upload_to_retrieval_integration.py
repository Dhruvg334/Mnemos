import pytest

from mnemos.models import Document, EvidenceRegion, ProcessingJob
from mnemos.models.vector import DocumentChunk
from mnemos.services.ingestion.lifecycle import IngestionLifecycle


class _Storage:
    async def read_object(self, key: str) -> bytes:
        assert key == "tenant/site/doc/pump-maintenance.txt"
        return (
            b"Asset P-117 experienced recurring seal leakage after alignment work.\n"
            b"The inspection recorded elevated vibration at the drive-end bearing.\n"
            b"Recommended action: verify shaft alignment and bearing condition."
        )


class _Db:
    def __init__(self) -> None:
        self.records: list[object] = []

    def add(self, record: object) -> None:
        self.records.append(record)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_uploaded_text_becomes_retrievable_evidence_and_chunks():
    db = _Db()
    document = Document(
        organisation_id="org_test",
        site_id="site_test",
        filename="pump-maintenance.txt",
        mime_type="text/plain",
        size_bytes=190,
        sha256="a" * 64,
        document_type="maintenance_record",
        storage_key="tenant/site/doc/pump-maintenance.txt",
        version=1,
    )
    job = ProcessingJob(document_id="doc_test")
    lifecycle = IngestionLifecycle()
    lifecycle.storage = _Storage()

    await lifecycle.run(db, document, job)

    evidence = [item for item in db.records if isinstance(item, EvidenceRegion)]
    chunks = [item for item in db.records if isinstance(item, DocumentChunk)]
    searchable_text = "\n".join(item.content for item in chunks)

    assert job.status == "succeeded"
    assert document.status == "ready"
    assert evidence
    assert chunks
    assert "P-117" in searchable_text
    assert "elevated vibration" in searchable_text
    assert all(item.tenant_id == "org_test" for item in chunks)
    assert all(item.site_id == "site_test" for item in chunks)
    assert all(item.metadata_json["embedding_status"] == "pending" for item in chunks)
