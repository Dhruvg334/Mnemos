"""Prompt Manager for the Mnemos agentic runtime.

Enhanced with:
- Prompt registry: catalog of available prompts with metadata
- Versioning: track prompt versions and changes
- Caching: avoid re-rendering identical prompts
- Validation: ensure required variables are provided

Backward compatible: existing get_prompt() and list_templates() still work.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    select_autoescape,
)

from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("prompts.manager")


class PromptMetadata:
    """Metadata for a registered prompt template."""

    def __init__(
        self,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        required_vars: list[str] | None = None,
        tags: list[str] | None = None,
        agent: str | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.required_vars = required_vars or []
        self.tags = tags or []
        self.agent = agent
        self.created_at = time.time()
        self.render_count = 0
        self.last_rendered_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "required_vars": self.required_vars,
            "tags": self.tags,
            "agent": self.agent,
            "created_at": self.created_at,
            "render_count": self.render_count,
            "last_rendered_at": self.last_rendered_at,
        }


class PromptManager:
    """Load and render version-controlled agent prompt templates.

    Enhanced with:
    - Registry: catalog of available prompts with metadata
    - Caching: avoid re-rendering identical prompts
    - Validation: ensure required variables are provided
    """

    def __init__(self, enable_cache: bool = True, cache_ttl_seconds: float = 300.0) -> None:
        self.template_path = Path(__file__).resolve().parent / "templates"
        if not self.template_path.is_dir():
            raise RuntimeError(
                f"Prompt template directory is missing: {self.template_path}"
            )

        self.env = Environment(
            loader=FileSystemLoader(self.template_path),
            autoescape=select_autoescape(),
            undefined=StrictUndefined,
        )

        self._registry: dict[str, PromptMetadata] = {}
        self._cache: dict[str, tuple[str, float]] = {}
        self._enable_cache = enable_cache
        self._cache_ttl = cache_ttl_seconds
        self._total_renders = 0
        self._cache_hits = 0

    # ------------------------------------------------------------------
    # Core rendering (backward compatible)
    # ------------------------------------------------------------------

    def get_prompt(self, template_name: str, **kwargs: Any) -> str:
        """Render a prompt template with the given variables.

        Backward compatible: works exactly as before.
        If caching is enabled and the same template+vars were rendered
        recently, returns the cached result.
        """
        if not template_name or "/" in template_name or "\\" in template_name:
            raise ValueError("Invalid prompt template name")

        cache_key = self._make_cache_key(template_name, kwargs)

        if self._enable_cache and cache_key in self._cache:
            cached_result, cached_at = self._cache[cache_key]
            if (time.time() - cached_at) < self._cache_ttl:
                self._cache_hits += 1
                self._update_registry_stats(template_name)
                return cached_result

        template = self.env.get_template(f"{template_name}.j2")
        result = template.render(**kwargs)

        self._total_renders += 1
        self._update_registry_stats(template_name)

        if self._enable_cache:
            self._cache[cache_key] = (result, time.time())
            self._prune_cache()

        return result

    def list_templates(self) -> list[str]:
        return sorted(self.env.list_templates())

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        required_vars: list[str] | None = None,
        tags: list[str] | None = None,
        agent: str | None = None,
    ) -> PromptMetadata:
        """Register a prompt template with metadata."""
        meta = PromptMetadata(
            name=name,
            description=description,
            version=version,
            required_vars=required_vars or [],
            tags=tags or [],
            agent=agent,
        )
        self._registry[name] = meta
        return meta

    def get_metadata(self, name: str) -> PromptMetadata | None:
        """Get metadata for a registered prompt."""
        return self._registry.get(name)

    def list_registered(self) -> list[dict[str, Any]]:
        """List all registered prompts with their metadata."""
        return [m.to_dict() for m in self._registry.values()]

    def list_by_agent(self, agent: str) -> list[str]:
        """List prompt names registered for a specific agent."""
        return [
            m.name for m in self._registry.values()
            if m.agent == agent
        ]

    def list_by_tag(self, tag: str) -> list[str]:
        """List prompt names with a specific tag."""
        return [
            m.name for m in self._registry.values()
            if tag in m.tags
        ]

    def get_version(self, name: str) -> str | None:
        """Get the version of a registered prompt."""
        meta = self._registry.get(name)
        return meta.version if meta else None

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def clear_cache(self) -> int:
        """Clear the prompt cache. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "enabled": self._enable_cache,
            "entries": len(self._cache),
            "total_renders": self._total_renders,
            "cache_hits": self._cache_hits,
            "hit_rate": (
                self._cache_hits / self._total_renders
                if self._total_renders > 0
                else 0.0
            ),
            "ttl_seconds": self._cache_ttl,
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_template_vars(
        self, template_name: str, provided_vars: dict[str, Any]
    ) -> list[str]:
        """Validate that all required variables are provided.

        Returns list of missing variable names (empty if all provided).
        """
        meta = self._registry.get(template_name)
        if meta is None:
            return []

        missing = [v for v in meta.required_vars if v not in provided_vars]
        return missing

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Summary of prompt manager state."""
        return {
            "template_path": str(self.template_path),
            "available_templates": self.list_templates(),
            "registered_count": len(self._registry),
            "cache": self.cache_stats(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _make_cache_key(self, template_name: str, kwargs: dict[str, Any]) -> str:
        """Create a cache key from template name and variables."""
        import json
        content = f"{template_name}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _update_registry_stats(self, template_name: str) -> None:
        """Update render stats for a registered prompt."""
        meta = self._registry.get(template_name)
        if meta:
            meta.render_count += 1
            meta.last_rendered_at = time.time()

    def _prune_cache(self) -> None:
        """Remove expired cache entries."""
        now = time.time()
        expired = [
            k for k, (_, t) in self._cache.items()
            if (now - t) >= self._cache_ttl
        ]
        for k in expired:
            del self._cache[k]
