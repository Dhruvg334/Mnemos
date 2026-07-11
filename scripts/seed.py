import asyncio

from sqlalchemy import select

from mnemos.core.db import SessionLocal
from mnemos.models import Asset, Membership, Organisation, Site, User


async def seed() -> None:
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
            User(id="usr_admin", email="admin@mnemos.local", full_name="Mnemos Admin"),
            User(
                id="usr_engineer_north",
                email="engineer.north@mnemos.local",
                full_name="North Engineer",
            ),
            User(
                id="usr_viewer_north",
                email="viewer.north@mnemos.local",
                full_name="North Viewer",
            ),
            User(
                id="usr_safety_north",
                email="safety.north@mnemos.local",
                full_name="North Safety",
            ),
            User(
                id="usr_engineer_south",
                email="engineer.south@mnemos.local",
                full_name="South Engineer",
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

        db.add_all([org, north, south, *users, *memberships, *assets])
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
