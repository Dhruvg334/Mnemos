from mnemos.schemas.agent import (
    AgentCitation,
    AgentClaim,
    AgentConfidence,
    AgentQueryRequest,
    AgentQueryResult,
    AgentRelatedEntity,
    AgentRunMetadata,
)


class MockAgentGateway:
    name = "mock"

    async def execute_query(self, request: AgentQueryRequest) -> AgentQueryResult:
        question = request.question.lower()
        if "exact vibration frequency" in question or "frequency peak" in question:
            return AgentQueryResult(
                run_id=request.run_id,
                status="partially_succeeded",
                answer=(
                    "The exact vibration frequency peak cannot be determined because the "
                    "spectrum attachment is missing."
                ),
                confidence=AgentConfidence(label="high", score=0.98),
                claims=[
                    AgentClaim(
                        id="claim_missing_spectrum",
                        text="The vibration spectrum attachment is missing.",
                        support_status="supported",
                        citation_ids=["citation_missing_spectrum"],
                    )
                ],
                citations=[
                    AgentCitation(
                        id="citation_missing_spectrum",
                        document_id="doc_005",
                        document_title="P-117 Vibration Route Inspection",
                        document_version=1,
                        chunk_id="chunk_doc_005_01",
                        page_or_sheet="1",
                        locator="Evidence limitation",
                        text_excerpt="The spectrum attachment is absent from the document package.",
                        retrieval_sources=["vector", "graph"],
                    )
                ],
                missing_evidence=["Missing vibration spectrum attachment for P-117"],
                run_metadata=AgentRunMetadata(pipeline_version="mock-0.2", latency_ms=60),
            )
        if "pt-204" in question or "calibration" in question:
            return AgentQueryResult(
                run_id=request.run_id,
                status="succeeded",
                answer=(
                    "The PT-204 calibration records conflict. The field record marks the "
                    "instrument within tolerance, while the later bench calibration records "
                    "a +4.8 percent drift."
                ),
                confidence=AgentConfidence(label="high", score=0.94),
                claims=[
                    AgentClaim(
                        id="claim_pt204_conflict",
                        text="PT-204 has conflicting calibration records.",
                        support_status="conflicting",
                        citation_ids=["citation_pt204_field", "citation_pt204_bench"],
                    )
                ],
                citations=[
                    AgentCitation(
                        id="citation_pt204_field",
                        document_id="doc_032",
                        document_title="PT-204 Field Calibration Record",
                        document_version=1,
                        page_or_sheet="1",
                        locator="paragraph 1",
                        text_excerpt="PT-204 was recorded as within tolerance.",
                        retrieval_sources=["vector"],
                    ),
                    AgentCitation(
                        id="citation_pt204_bench",
                        document_id="doc_033",
                        document_title="PT-204 Bench Calibration Record",
                        document_version=1,
                        page_or_sheet="1",
                        locator="paragraph 1",
                        text_excerpt="PT-204 was found reading high by 4.8 percent.",
                        retrieval_sources=["vector", "graph"],
                    ),
                ],
                conflicts=[{"topic": "PT-204 calibration status"}],
                run_metadata=AgentRunMetadata(pipeline_version="mock-0.2", latency_ms=75),
            )
        if "p-117" in question:
            return AgentQueryResult(
                run_id=request.run_id,
                status="succeeded",
                answer=(
                    "P-117 had three seal-leak failures in the first half of 2026. "
                    "Misalignment and lubrication-related conditions are supported contributors, "
                    "but the missing vibration spectrum prevents one definitive root cause."
                ),
                confidence=AgentConfidence(label="high", score=0.91),
                claims=[
                    AgentClaim(
                        id="claim_p117_recurrence",
                        text="P-117 experienced recurring seal leakage.",
                        support_status="supported",
                        citation_ids=["citation_p117_event", "citation_p117_findings"],
                    )
                ],
                citations=[
                    AgentCitation(
                        id="citation_p117_event",
                        document_id="doc_003",
                        document_title="WO-2026-048 — P-117 Recurring Seal Failure",
                        document_version=1,
                        chunk_id="chunk_doc_003_event",
                        page_or_sheet="1",
                        locator="Event",
                        text_excerpt="A third seal leak occurred on 18 June 2026.",
                        retrieval_sources=["vector", "graph"],
                    ),
                    AgentCitation(
                        id="citation_p117_findings",
                        document_id="doc_003",
                        document_title="WO-2026-048 — P-117 Recurring Seal Failure",
                        document_version=1,
                        chunk_id="chunk_doc_003_findings",
                        page_or_sheet="1",
                        locator="Findings",
                        text_excerpt="The coupling was offset and bearing lubrication was overdue.",
                        retrieval_sources=["vector", "graph", "metadata"],
                    ),
                ],
                missing_evidence=["Missing vibration spectrum attachment for P-117"],
                related_entities=[
                    AgentRelatedEntity(entity_type="asset", entity_id="ast_m117_n", label="M-117")
                ],
                run_metadata=AgentRunMetadata(pipeline_version="mock-0.2", latency_ms=90),
            )
        return AgentQueryResult(
            run_id=request.run_id,
            status="partially_succeeded",
            answer="The available corpus does not contain enough evidence to answer this question.",
            confidence=AgentConfidence(label="low", score=0.2),
            missing_evidence=["Relevant source evidence"],
            run_metadata=AgentRunMetadata(pipeline_version="mock-0.2", latency_ms=35),
        )
