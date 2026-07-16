from collections.abc import AsyncIterator

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, TransientError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from mnemos.core.config import settings
from mnemos.core.logging import get_logger

logger = get_logger("neo4j")

# Global driver instance
_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}")
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=settings.neo4j_max_connection_pool_size,
            connection_timeout=10.0,
            keep_alive=True,
        )
    return _driver


async def init_neo4j() -> None:
    driver = get_driver()
    try:
        await driver.verify_connectivity()
        logger.info("Neo4j connectivity verified.")
    except Exception as exc:
        logger.error(f"Failed to connect to Neo4j: {exc}")
        raise


async def close_neo4j() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j connection closed.")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ServiceUnavailable, TransientError)),
)
async def check_neo4j_health() -> str:
    driver = get_driver()
    try:
        await driver.verify_connectivity()
        return "healthy"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        return "unhealthy"


async def get_neo4j_session() -> AsyncIterator:
    """FastAPI dependency for yielding Neo4j sessions."""
    driver = get_driver()
    async with driver.session() as session:
        yield session
