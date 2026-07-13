import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_mnemos.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["APP_ENV"] = "test"
os.environ["DEV_LOGIN_ENABLED"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mnemos.core.db import Base, get_db
from mnemos.main import app
from mnemos.models import Asset, Membership, Organisation, Site, User

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_mnemos.db"
test_engine = create_async_engine(TEST_DATABASE_URL)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def reset_database() -> AsyncIterator[None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as db:
        org = Organisation(id="org_test", name="Test Organisation")
        north = Site(
            id="site_north",
            organisation_id=org.id,
            name="North Plant",
            code="NORTH",
        )
        south = Site(
            id="site_south",
            organisation_id=org.id,
            name="South Plant",
            code="SOUTH",
        )
        north_user = User(
            id="usr_north",
            email="north@example.com",
            full_name="North Engineer",
        )
        south_user = User(
            id="usr_south",
            email="south@example.com",
            full_name="South Engineer",
        )
        admin = User(id="usr_admin", email="admin@example.com", full_name="Admin")
        db.add_all(
            [
                org,
                north,
                south,
                north_user,
                south_user,
                admin,
                Membership(
                    user_id=north_user.id,
                    organisation_id=org.id,
                    site_id=north.id,
                    role="engineer",
                ),
                Membership(
                    user_id=south_user.id,
                    organisation_id=org.id,
                    site_id=south.id,
                    role="engineer",
                ),
                Membership(
                    user_id=admin.id,
                    organisation_id=org.id,
                    site_id=None,
                    role="organisation_admin",
                ),
                Asset(
                    id="ast_p117_n",
                    site_id=north.id,
                    asset_tag="P-117",
                    name="Effluent Transfer Pump",
                    asset_type="pump",
                ),
                Asset(
                    id="ast_p117_s",
                    site_id=south.id,
                    asset_tag="P-117",
                    name="Product Transfer Pump",
                    asset_type="pump",
                ),
            ]
        )
        await db.commit()

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/dev-login", json={"email": email})
    return response.json()["data"]["access_token"]


@pytest.fixture
async def north_token(client: AsyncClient) -> str:
    return await token_for(client, "north@example.com")


@pytest.fixture
async def south_token(client: AsyncClient) -> str:
    return await token_for(client, "south@example.com")


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    return await token_for(client, "admin@example.com")
