from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from mnemos.schemas.common import APIModel


class AgentScope(APIModel):
    asset_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    allowed_document_types: list[str] = Field(default_factory=list)
    access_classifications: list[str] = Field(default_factory=lambda: ["internal"])


class AgentOptions(APIModel):
    include_graph_context: bool = True
    include_missing_evidence: bool = True
    include_conflicts: bool = True


class AgentQueryRequest(APIModel):
    run_id: str
    query_id: str
    organisation_id: str
    site_id: str
    user_id: str
    query_type: str
    question: str
    scope: AgentScope
    options: AgentOptions = Field(default_factory=AgentOptions)


class AgentConfidence(APIModel):
    label: Literal["low", "medium", "high"]
    score: float = Field(ge=0.0, le=1.0)


class AgentClaim(APIModel):
    id: str
    text: str
    support_status: Literal[
        "supported",
        "partially_supported",
        "conflicting",
        "unsupported",
        "not_evaluated",
    ]
    citation_ids: list[str] = Field(default_factory=list)


class AgentCitation(APIModel):
    id: str
    document_id: str | None = None
    document_title: str
    document_version: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    evidence_region_id: str | None = None
    page_or_sheet: str | None = None
    locator: str | None = None
    text_excerpt: str | None = None
    retrieval_sources: list[str] = Field(default_factory=list)
    access_allowed: bool = True


class AgentRelatedEntity(APIModel):
    entity_type: str
    entity_id: str
    label: str


class AgentRunMetadata(APIModel):
    pipeline_version: str | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    token_usage: dict[str, int] = Field(default_factory=dict)


class AgentQueryResult(APIModel):
    run_id: str
    status: Literal["succeeded", "partially_succeeded", "failed"]
    answer: str | None = None
    confidence: AgentConfidence | None = None
    claims: list[AgentClaim] = Field(default_factory=list)
    citations: list[AgentCitation] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    related_entities: list[AgentRelatedEntity] = Field(default_factory=list)
    run_metadata: AgentRunMetadata = Field(default_factory=AgentRunMetadata)
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_result(self):
        if self.status == "failed":
            if not self.error_code:
                raise ValueError("Failed agent results require error_code")
            return self
        if not self.answer or self.confidence is None:
            raise ValueError("Successful agent results require answer and confidence")
        citation_ids = {citation.id for citation in self.citations}
        for claim in self.claims:
            missing = set(claim.citation_ids) - citation_ids
            if missing:
                raise ValueError(
                    f"Claim {claim.id} references unknown citations: {sorted(missing)}"
                )
        return self
