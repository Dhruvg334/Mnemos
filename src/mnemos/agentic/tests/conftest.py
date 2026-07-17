"""Shared test fixtures for the Mnemos agentic test suite.

Ensures a fresh event loop is available for every test, preventing
cross-test contamination when mixing pytest.mark.asyncio and manual
asyncio.get_event_loop().run_until_complete() patterns.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _ensure_event_loop():
    """Guarantee a running event loop exists for each test."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield
    # Do NOT close the loop here -- other fixtures or teardown may need it.
