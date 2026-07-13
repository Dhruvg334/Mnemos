import asyncio
import os

from sqlalchemy import select

from mnemos.core.config import settings
from mnemos.core.db import SessionLocal
from mnemos.core.security import hash_password, validate_password_strength
from mnemos.models import (
    Asset,
    AssetAlias,
    AssetRelationship,
    Membership,
    Organisation,
    Site,
    User,
)


async def seed() -> None:
    seed_password = os.getenv("SEED_DEFAULT_PASSWORD")
    if settings.app_env.lower() in {"production", "prod"} and not seed_password:
        raise RuntimeError("SEED_DEFAULT_PASSWORD is required for production seeding")
    password_hash = None
    if seed_password:
        validate_password_strength(seed_password)
        password_hash = hash_password(seed_password)
    async with SessionLocal() as db:
        existing = await db.scalar(select(Organisation).where(Organisation.id == "org_mn_001"))
        if existing is not None:
            return

        org = Organisation(id="org_mn_001", name="Asteron Process Industries")
        north = Site(
            id="site_north",
            organisation_id=org.id,
            name="North Process Plant",
            code="NPP",
        )
        south = Site(
            id="site_south",
            organisation_id=org.id,
            name="South Utilities Plant",
            code="SUP",
        )
        users = [
            User(id="usr_admin", email="admin@mnemos.local", full_name="Mnemos Admin", password_hash=password_hash),
            User(
                id="usr_engineer_north",
                email="engineer.north@mnemos.local",
                full_name="North Engineer",
                password_hash=password_hash,
            ),
            User(
                id="usr_viewer_north",
                email="viewer.north@mnemos.local",
                full_name="North Viewer",
                password_hash=password_hash,
            ),
            User(
                id="usr_safety_north",
                email="safety.north@mnemos.local",
                full_name="North Safety",
                password_hash=password_hash,
            ),
            User(
                id="usr_engineer_south",
                email="engineer.south@mnemos.local",
                full_name="South Engineer",
                password_hash=password_hash,
            ),
        ]
        memberships = [
            Membership(
                user_id="usr_admin",
                organisation_id=org.id,
                site_id=None,
                role="organisation_admin",
            ),
            Membership(
                user_id="usr_engineer_north",
                organisation_id=org.id,
                site_id=north.id,
                role="engineer",
            ),
            Membership(
                user_id="usr_viewer_north",
                organisation_id=org.id,
                site_id=north.id,
                role="viewer",
            ),
            Membership(
                user_id="usr_safety_north",
                organisation_id=org.id,
                site_id=north.id,
                role="safety_user",
            ),
            Membership(
                user_id="usr_engineer_south",
                organisation_id=org.id,
                site_id=south.id,
                role="engineer",
            ),
        ]
        assets = [
            Asset(
                id="ast_p117_n",
                site_id=north.id,
                asset_tag="P-117",
                name="Effluent Transfer Pump",
                asset_type="pump",
            ),
            Asset(
                id="ast_m117_n",
                site_id=north.id,
                asset_tag="M-117",
                name="Pump P-117 Drive Motor",
                asset_type="motor",
            ),
            Asset(
                id="ast_p117_s",
                site_id=south.id,
                asset_tag="P-117",
                name="Product Transfer Pump",
                asset_type="pump",
            ),
        ]

        aliases = [
            AssetAlias(
                id="alias_p117_n_1",
                site_id=north.id,
                asset_id="ast_p117_n",
                alias="P117",
                normalized_alias="p117",
                source="seed",
                confidence=1.0,
            ),
            AssetAlias(
                id="alias_p117_n_2",
                site_id=north.id,
                asset_id="ast_p117_n",
                alias="Pump-117",
                normalized_alias="pump117",
                source="seed",
                confidence=0.95,
            ),
            AssetAlias(
                id="alias_m117_n_1",
                site_id=north.id,
                asset_id="ast_m117_n",
                alias="Motor-117",
                normalized_alias="motor117",
                source="seed",
                confidence=0.95,
            ),
        ]
        relationships = [
            AssetRelationship(
                id="rel_p117_driven_by_m117",
                site_id=north.id,
                source_asset_id="ast_p117_n",
                target_asset_id="ast_m117_n",
                relationship_type="DRIVEN_BY",
                confidence=1.0,
                review_status="approved",
            )
        ]

        db.add_all([
            org,
            north,
            south,
            *users,
            *memberships,
            *assets,
            *aliases,
            *relationships,
        ])
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
