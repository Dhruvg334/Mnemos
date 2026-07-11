from dataclasses import dataclass, field


@dataclass
class MockCitation:
    claim_text: str
    support_status: str
    document_title: str
    page_or_sheet: str | None
    locator: str | None
    text_excerpt: str | None
    access_allowed: bool = True


@dataclass
class MockAgentResult:
    answer: str
    confidence_label: str
    confidence_score: float
    citations: list[MockCitation] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    related_entities: list[dict] = field(default_factory=list)
    partial: bool = False


class MockAgentGateway:
    async def execute_query(self, question: str) -> MockAgentResult:
        q = question.lower()

        if "pt-204" in q or "calibration" in q:
            return MockAgentResult(
                answer=(
                    "The PT-204 calibration records conflict. The field record marks the "
                    "instrument within tolerance, while the later bench calibration records "
                    "a +4.8 percent drift."
                ),
                confidence_label="high",
                confidence_score=0.94,
                citations=[
                    MockCitation(
                        claim_text="The field record marked PT-204 within tolerance.",
                        support_status="supported",
                        document_title="PT-204 Field Calibration Record",
                        page_or_sheet="1",
                        locator="paragraph 1",
                        text_excerpt="Field calibration dated 10 June 2026 records PT-204 as within tolerance.",
                    ),
                    MockCitation(
                        claim_text="The bench record found a +4.8 percent drift.",
                        support_status="supported",
                        document_title="PT-204 Bench Calibration Record",
                        page_or_sheet="1",
                        locator="paragraph 1",
                        text_excerpt="Bench calibration dated 29 June 2026 found PT-204 reading high by 4.8 percent.",
                    ),
                ],
                conflicts=[
                    {
                        "topic": "PT-204 calibration status",
                        "documents": [
                            "PT-204 Field Calibration Record",
                            "PT-204 Bench Calibration Record",
                        ],
                    }
                ],
            )

        if "exact vibration frequency" in q or "frequency peak" in q:
            return MockAgentResult(
                answer=(
                    "The exact vibration frequency peak cannot be determined because the "
                    "spectrum attachment is missing."
                ),
                confidence_label="high",
                confidence_score=0.98,
                citations=[
                    MockCitation(
                        claim_text="The spectrum attachment is missing.",
                        support_status="supported",
                        document_title="P-117 Vibration Route Inspection",
                        page_or_sheet="1",
                        locator="Evidence limitation",
                        text_excerpt="The spectrum attachment is absent from the document package.",
                    )
                ],
                missing_evidence=["Missing vibration spectrum attachment for P-117"],
                partial=True,
            )

        if "p-117" in q:
            return MockAgentResult(
                answer=(
                    "P-117 had three seal-leak failures in the first half of 2026. "
                    "Misalignment and lubrication-related conditions are supported contributors, "
                    "but the missing vibration spectrum prevents one definitive root cause."
                ),
                confidence_label="high",
                confidence_score=0.91,
                citations=[
                    MockCitation(
                        claim_text="P-117 experienced a third seal leak on 18 June 2026.",
                        support_status="supported",
                        document_title="WO-2026-048 — P-117 Recurring Seal Failure",
                        page_or_sheet="1",
                        locator="Event",
                        text_excerpt="A third seal leak occurred on 18 June 2026.",
                    ),
                    MockCitation(
                        claim_text="Coupling offset and overdue lubrication were found.",
                        support_status="supported",
                        document_title="WO-2026-048 — P-117 Recurring Seal Failure",
                        page_or_sheet="1",
                        locator="Findings",
                        text_excerpt=(
                            "The coupling was offset. Motor M-117 drive-end bearing lubrication "
                            "was 18 days overdue."
                        ),
                    ),
                ],
                missing_evidence=["Missing vibration spectrum attachment for P-117"],
                related_entities=[
                    {
                        "entity_type": "asset",
                        "entity_id": "ast_m117_n",
                        "label": "M-117",
                    }
                ],
            )

        return MockAgentResult(
            answer="The available corpus does not contain enough evidence to answer this question.",
            confidence_label="low",
            confidence_score=0.2,
            missing_evidence=["Relevant source evidence"],
            partial=True,
        )
