from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime.guardrail_policy import GuardrailPolicyEngine
from mnemos.core.db import SessionLocal
from mnemos.core.errors import AppError
from mnemos.integrations.agents import get_agent_gateway
from mnemos.models import AgentRun, Citation, Query, QueryClaim, QueryEvent
from mnemos.schemas.agent import AgentOptions, AgentQueryRequest, AgentScope
from mnemos.services.agent_validation import validate_agent_result

_query_policy = GuardrailPolicyEngine()


_SAFE_ERROR_MESSAGES = {
    "AGENT_EXECUTION_FAILED": "Agent execution failed.",
    "AI_ORCHESTRATION_FAILED": "The analysis could not be completed.",
    "AI_ORCHESTRATION_TIMEOUT": "The analysis request timed out.",
    "AGENT_RESPONSE_INVALID": "The agent returned an invalid response.",
    "AGENT_EVIDENCE_FORBIDDEN": "The agent returned forbidden evidence.",
    "AGENT_EVIDENCE_INVALID": "The agent returned invalid evidence.",
    "AGENT_EVIDENCE_OUT_OF_SCOPE": "The agent returned out-of-scope evidence.",
}


def _hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_error(exc: Exception) -> tuple[str, str]:
    code = getattr(exc, "code", "AGENT_EXECUTION_FAILED")
    if not isinstance(code, str) or not code:
        code = "AGENT_EXECUTION_FAILED"
    return code, _SAFE_ERROR_MESSAGES.get(code, "Query execution failed.")


async def add_query_event(
    db: AsyncSession,
    *,
    query_id: str,
    stage: str,
    progress_percent: int,
    message: str,
) -> None:
    db.add(
        QueryEvent(
            query_id=query_id,
            stage=stage,
            progress_percent=progress_percent,
            message=message,
        )
    )
    await db.flush()


async def execute_query_background(query_id: str) -> None:
    async with SessionLocal() as db:
        query = await db.scalar(select(Query).where(Query.id == query_id).with_for_update())
        if query is None or query.status not in {"queued", "running"}:
            return

        gateway = get_agent_gateway()
        run = AgentRun(
            query_id=query.id,
            organisation_id=query.organisation_id,
            site_id=query.site_id,
            status="running",
            gateway=gateway.name,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        query.status = "running"
        await add_query_event(
            db,
            query_id=query.id,
            stage="classifying_query",
            progress_percent=10,
            message="Classifying query",
        )
        await db.commit()

        request = AgentQueryRequest(
            run_id=run.id,
            query_id=query.id,
            organisation_id=query.organisation_id,
            site_id=query.site_id,
            user_id=query.user_id,
            query_type=query.mode,
            question=query.question,
            scope=AgentScope(
                asset_ids=list(query.context_asset_ids or []),
                document_ids=list(query.context_document_ids or []),
            ),
            options=AgentOptions(),
        )
        run.request_payload_hash = _hash_payload(request.model_dump(mode="json"))

        run_id = run.id
        try:
            await add_query_event(
                db,
                query_id=query.id,
                stage="retrieving_evidence",
                progress_percent=35,
                message="Retrieving evidence",
            )
            await db.commit()
            result = await gateway.execute_query(request)
            await db.refresh(query)
            if query.status == "cancelled":
                run.status = "cancelled"
                run.completed_at = datetime.now(UTC)
                await db.commit()
                return
            await validate_agent_result(db, query=query, result=result)
            run.response_payload_hash = _hash_payload(result.model_dump(mode="json"))

            if result.status == "failed":
                raise AppError(
                    result.error_code or "AGENT_EXECUTION_FAILED",
                    result.error_message or "Agent execution failed.",
                    502,
                )

            await add_query_event(
                db,
                query_id=query.id,
                stage="verifying_evidence",
                progress_percent=80,
                message="Validating claims and evidence",
            )

            query.answer = result.answer
            query.confidence_label = result.confidence.label if result.confidence else None
            query.confidence_score = result.confidence.score if result.confidence else None
            query.missing_evidence = result.missing_evidence
            query.conflicts = result.conflicts
            query.related_entities = [item.model_dump() for item in result.related_entities]
            query.status = result.status
            if result.status == "pending_approval":
                query.completed_at = None
            else:
                query.completed_at = datetime.now(UTC)

            claim_map: dict[str, QueryClaim] = {}
            for item in result.claims:
                claim = QueryClaim(
                    query_id=query.id,
                    external_id=item.id,
                    text=item.text,
                    support_status=item.support_status,
                )
                db.add(claim)
                claim_map[item.id] = claim
            await db.flush()

            citation_to_claim: dict[str, QueryClaim] = {}
            for item in result.claims:
                for citation_id in item.citation_ids:
                    citation_to_claim.setdefault(citation_id, claim_map[item.id])

            for item in result.citations:
                linked_claim = citation_to_claim.get(item.id)
                db.add(
                    Citation(
                        query_id=query.id,
                        claim_id=linked_claim.id if linked_claim else None,
                        claim_text=linked_claim.text if linked_claim else "Evidence",
                        support_status=(
                            linked_claim.support_status if linked_claim else "not_evaluated"
                        ),
                        document_id=item.document_id,
                        document_title=item.document_title,
                        document_version=item.document_version,
                        chunk_id=item.chunk_id,
                        evidence_region_id=item.evidence_region_id,
                        page_or_sheet=item.page_or_sheet,
                        locator=item.locator,
                        text_excerpt=item.text_excerpt,
                        retrieval_sources=item.retrieval_sources,
                        access_allowed=item.access_allowed,
                    )
                )

            run.status = result.status
            run.pipeline_version = result.run_metadata.pipeline_version
            run.latency_ms = result.run_metadata.latency_ms
            if result.status == "pending_approval":
                run.completed_at = None
                await add_query_event(
                    db,
                    query_id=query.id,
                    stage="pending_approval",
                    progress_percent=90,
                    message="Query paused pending human approval",
                )
            else:
                run.completed_at = datetime.now(UTC)
                await add_query_event(
                    db,
                    query_id=query.id,
                    stage="completed",
                    progress_percent=100,
                    message="Query completed",
                )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            error_code, error_message = _safe_error(exc)
            query = await db.get(Query, query_id)
            run = await db.get(AgentRun, run_id)
            if query is not None:
                query.status = "failed"
                query.completed_at = datetime.now(UTC)
            if run is not None:
                run.status = "failed"
                run.error_code = error_code
                run.error_message = error_message
                run.completed_at = datetime.now(UTC)
            await add_query_event(
                db,
                query_id=query_id,
                stage="failed",
                progress_percent=100,
                message="Query execution failed",
            )
            await db.commit()
