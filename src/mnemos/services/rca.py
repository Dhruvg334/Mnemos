from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models import RCAAction, RCACase, RCAHypothesis, RCAObservation


async def load_rca_bundle(db: AsyncSession, rca: RCACase) -> dict:
    observations = list(
        (
            await db.scalars(
                select(RCAObservation)
                .where(RCAObservation.rca_id == rca.id)
                .order_by(RCAObservation.created_at)
            )
        ).all()
    )
    hypotheses = list(
        (
            await db.scalars(
                select(RCAHypothesis)
                .where(RCAHypothesis.rca_id == rca.id)
                .order_by(RCAHypothesis.created_at)
            )
        ).all()
    )
    actions = list(
        (
            await db.scalars(
                select(RCAAction).where(RCAAction.rca_id == rca.id).order_by(RCAAction.created_at)
            )
        ).all()
    )
    return {"rca": rca, "observations": observations, "hypotheses": hypotheses, "actions": actions}


def rca_snapshot(bundle: dict) -> dict:
    rca = bundle["rca"]
    return {
        "id": rca.id,
        "title": rca.title,
        "problem_statement": rca.problem_statement,
        "severity": rca.severity,
        "observations": [
            {
                "id": item.id,
                "type": item.observation_type,
                "text": item.text,
                "evidence_region_id": item.evidence_region_id,
            }
            for item in bundle["observations"]
        ],
        "hypotheses": [
            {
                "id": item.id,
                "text": item.text,
                "support_status": item.support_status,
                "confidence_score": item.confidence_score,
                "evidence_region_ids": item.evidence_region_ids,
            }
            for item in bundle["hypotheses"]
        ],
        "actions": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "owner_id": item.owner_id,
            }
            for item in bundle["actions"]
        ],
    }
