import logging
import os

import httpx
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

class ResourcePool:
    """
    Manages long-lived connections for the AI Layer.
    Optimizes memory usage and reduces latency via connection pooling.
    """
    _neo4j_driver: AsyncGraphDatabase | None = None
    _http_client: httpx.AsyncClient | None = None

    @classmethod
    def get_neo4j_driver(cls) -> AsyncGraphDatabase:
        if cls._neo4j_driver is None:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")
            cls._neo4j_driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            logger.info("Neo4j driver pooled.")
        return cls._neo4j_driver

    @classmethod
    def get_http_client(cls) -> httpx.AsyncClient:
        if cls._http_client is None:
            cls._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(90.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
            logger.info("Shared HTTP client pooled.")
        return cls._http_client

    @classmethod
    async def close_all(cls):
        if cls._neo4j_driver:
            await cls._neo4j_driver.close()
            cls._neo4j_driver = None
        if cls._http_client:
            await cls._http_client.aclose()
            cls._http_client = None
