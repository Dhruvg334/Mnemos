from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime.guardrail_policy import GuardrailPolicyEngine
from mnemos.core.db import SessionLocal
from mnemos.core.errors import AppError
from mnemos.core.logging import get_logger
from mnemos.integrations.agents import get_agent_gateway
from mnemos.models import AgentRun, Citation, Membership, Query, QueryClaim, QueryEvent
from mnemos.schemas.agent import AgentOptions, AgentQueryRequest, AgentScope
from mnemos.services.agent_validation import validate_agent_result

_query_policy = GuardrailPolicyEngine()
logger = get_logger("mnemos.query_execution")


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


async def _resolve_query_membership(
    db: AsyncSession,
    *,
    user_id: str,
    organisation_id: str,
    site_id: str,
) -> Membership:
    """Resolve the effective membership for an asynchronous query run.

    Background execution must not reuse the role that existed when the query
    was created. Memberships may be revoked or narrowed before execution
    begins, so the worker re-resolves authorization immediately before calling
    the agentic runtime. Site-specific memberships take precedence over
    organisation-wide memberships.
    """
    memberships = list(
        (
            await db.scalars(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.organisation_id == organisation_id,
                    (Membership.site_id == site_id) | (Membership.site_id.is_(None)),
                )
            )
        ).all()
    )
    if not memberships:
        raise AppError(
            "QUERY_ACCESS_REVOKED",
            "Access to this query scope is no longer available.",
            403,
        )

    memberships.sort(key=lambda membership: membership.site_id is None)
    return memberships[0]


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

        try:
            membership = await _resolve_query_membership(
                db,
                user_id=query.user_id,
                organisation_id=query.organisation_id,
                site_id=query.site_id,
            )
        except AppError:
            query.status = "failed"
            query.completed_at = datetime.now(UTC)
            await add_query_event(
                db,
                query_id=query.id,
                stage="authorization_failed",
                progress_percent=100,
                message="Query access was revoked before execution",
            )
            await db.commit()
            return

        gateway = get_agent_gateway()
        logger.info(
            "Query execution started",
            extra={
                "query_id": query.id,
                "tenant_id": query.organisation_id,
                "site_id": query.site_id,
                "execution_stage": "dispatch",
                "query_status": "running",
                "provider": gateway.name,
            },
        )
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
            membership_id=membership.id,
            actor_role=membership.role,
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
            logger.info(
                "Agent gateway returned",
                extra={
                    "query_id": query.id,
                    "tenant_id": query.organisation_id,
                    "site_id": query.site_id,
                    "execution_stage": "agent_response",
                    "provider": gateway.name,
                    "verified_evidence_count": len(result.citations),
                    "query_status": result.status,
                    "fallback_activated": bool(result.run_metadata.fallback_used)
                    if hasattr(result.run_metadata, "fallback_used")
                    else False,
                },
            )
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
            logger.info(
                "Query execution completed",
                extra={
                    "query_id": query.id,
                    "tenant_id": query.organisation_id,
                    "site_id": query.site_id,
                    "execution_stage": "completed",
                    "verified_evidence_count": len(result.citations),
                    "query_status": result.status,
                },
            )
        except Exception as exc:
            await db.rollback()
            error_code, error_message = _safe_error(exc)
            logger.error(
                "Query execution failed",
                extra={
                    "query_id": query_id,
                    "execution_stage": "failed",
                    "error_category": error_code,
                    "query_status": "failed",
                },
                exc_info=True,
            )
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


async def resume_query_after_approval(request_id: str) -> None:
    """Resume or terminate a query after a durable approval decision.

    This callback is scheduled by the approvals API only after the decision is
    committed. It re-resolves the user's current membership before resuming so
    approval cannot bypass access revocation that happened while the workflow
    was paused.
    """
    from mnemos.agentic.runtime.approval_queue import DurableApprovalQueue

    queue = DurableApprovalQueue(session_factory=SessionLocal)
    approval = await queue.get_request(request_id)
    decision = await queue.get_decision(request_id)
    if approval is None or decision is None:
        return

    async with SessionLocal() as db:
        query = await db.scalar(
            select(Query).where(Query.id == approval.investigation_id).with_for_update()
        )
        if query is None or query.status != "pending_approval":
            return

        run = await db.scalar(
            select(AgentRun)
            .where(
                AgentRun.query_id == query.id,
                AgentRun.status == "pending_approval",
            )
            .order_by(AgentRun.started_at.desc())
            .with_for_update()
        )
        if run is None:
            query.status = "failed"
            query.completed_at = datetime.now(UTC)
            await add_query_event(
                db,
                query_id=query.id,
                stage="approval_resume_failed",
                progress_percent=100,
                message="Approval was recorded but no resumable run was found",
            )
            await db.commit()
            return

        if decision.decision != "approve":
            query.status = "failed"
            query.completed_at = datetime.now(UTC)
            run.status = "failed"
            run.error_code = "APPROVAL_REJECTED"
            run.error_message = "The workflow was not approved for completion."
            run.completed_at = datetime.now(UTC)
            await add_query_event(
                db,
                query_id=query.id,
                stage="approval_rejected",
                progress_percent=100,
                message="Human review did not approve the workflow",
            )
            await db.commit()
            return

        try:
            membership = await _resolve_query_membership(
                db,
                user_id=query.user_id,
                organisation_id=query.organisation_id,
                site_id=query.site_id,
            )
        except AppError:
            query.status = "failed"
            query.completed_at = datetime.now(UTC)
            run.status = "failed"
            run.error_code = "QUERY_ACCESS_REVOKED"
            run.error_message = "Access was revoked before approval resume."
            run.completed_at = datetime.now(UTC)
            await add_query_event(
                db,
                query_id=query.id,
                stage="authorization_failed",
                progress_percent=100,
                message="Query access was revoked before approval resume",
            )
            await db.commit()
            return

        request = AgentQueryRequest(
            run_id=run.id,
            query_id=query.id,
            organisation_id=query.organisation_id,
            site_id=query.site_id,
            user_id=query.user_id,
            membership_id=membership.id,
            actor_role=membership.role,
            query_type=query.mode,
            question=query.question,
            scope=AgentScope(
                asset_ids=list(query.context_asset_ids or []),
                document_ids=list(query.context_document_ids or []),
            ),
            options=AgentOptions(),
        )

        gateway = get_agent_gateway()
        resume = getattr(gateway, "resume_query", None)
        if resume is None:
            query.status = "failed"
            query.completed_at = datetime.now(UTC)
            run.status = "failed"
            run.error_code = "APPROVAL_RESUME_UNSUPPORTED"
            run.error_message = "The configured agent gateway cannot resume workflows."
            run.completed_at = datetime.now(UTC)
            await add_query_event(
                db,
                query_id=query.id,
                stage="approval_resume_failed",
                progress_percent=100,
                message="The configured agent gateway cannot resume workflows",
            )
            await db.commit()
            return

        try:
            await add_query_event(
                db,
                query_id=query.id,
                stage="approval_received",
                progress_percent=92,
                message="Approval received; resuming workflow",
            )
            await db.commit()
            result = await resume(request, request_id)
            await validate_agent_result(db, query=query, result=result)
            if result.status == "failed":
                raise AppError(
                    result.error_code or "AGENT_EXECUTION_FAILED",
                    result.error_message or "Agent resume failed.",
                    502,
                )

            query.answer = result.answer
            query.confidence_label = result.confidence.label if result.confidence else None
            query.confidence_score = result.confidence.score if result.confidence else None
            query.missing_evidence = result.missing_evidence
            query.conflicts = result.conflicts
            query.related_entities = [item.model_dump() for item in result.related_entities]
            query.status = "succeeded"
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

            run.status = "succeeded"
            run.pipeline_version = result.run_metadata.pipeline_version
            run.latency_ms = result.run_metadata.latency_ms
            run.response_payload_hash = _hash_payload(result.model_dump(mode="json"))
            run.completed_at = datetime.now(UTC)
            await add_query_event(
                db,
                query_id=query.id,
                stage="completed",
                progress_percent=100,
                message="Query completed after human approval",
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            error_code, error_message = _safe_error(exc)
            query = await db.get(Query, approval.investigation_id)
            run = await db.get(AgentRun, run.id)
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
                query_id=approval.investigation_id,
                stage="approval_resume_failed",
                progress_percent=100,
                message="Workflow could not resume after approval",
            )
            await db.commit()
