"""Tests for the enhanced Prompt Manager.

Covers registry, versioning, caching, validation, and backward compatibility.
"""

from __future__ import annotations

import time

import pytest
from jinja2 import TemplateNotFound

from mnemos.agentic.prompts.manager import PromptManager, PromptMetadata

# =====================================================================
# Test: PromptMetadata
# =====================================================================


class TestPromptMetadata:
    def test_creation(self):
        meta = PromptMetadata(
            name="asset_qa",
            description="Answer asset questions",
            version="1.2.0",
            required_vars=["query", "evidence"],
            tags=["retrieval", "qa"],
            agent="asset_intelligence",
        )
        assert meta.name == "asset_qa"
        assert meta.version == "1.2.0"
        assert meta.required_vars == ["query", "evidence"]
        assert meta.render_count == 0

    def test_defaults(self):
        meta = PromptMetadata(name="test")
        assert meta.description == ""
        assert meta.version == "1.0.0"
        assert meta.required_vars == []
        assert meta.tags == []
        assert meta.agent is None

    def test_to_dict(self):
        meta = PromptMetadata(
            name="test",
            version="2.0.0",
            required_vars=["q"],
            tags=["tag1"],
            agent="agent1",
        )
        d = meta.to_dict()
        assert d["name"] == "test"
        assert d["version"] == "2.0.0"
        assert d["required_vars"] == ["q"]
        assert d["tags"] == ["tag1"]
        assert d["agent"] == "agent1"
        assert d["render_count"] == 0


# =====================================================================
# Test: PromptManager (backward compatible)
# =====================================================================


class TestPromptManagerBackwardCompatible:
    def setup_method(self):
        self.pm = PromptManager(enable_cache=False)

    def test_list_templates(self):
        templates = self.pm.list_templates()
        assert isinstance(templates, list)
        assert len(templates) == 8
        assert "rca_analysis.j2" in templates
        assert "asset_qa.j2" in templates
        assert "verifier.j2" in templates

    def test_get_prompt_asset_qa(self):
        result = self.pm.get_prompt(
            "asset_qa",
            query="Why did pump P-101 fail?",
            evidence=[],
        )
        assert isinstance(result, str)
        assert "pump P-101" in result

    def test_get_prompt_planner(self):
        result = self.pm.get_prompt(
            "planner",
            query="Pump failure analysis",
            context_assets=["P-101", "P-102"],
        )
        assert isinstance(result, str)
        assert "P-101" in result

    def test_get_prompt_verifier(self):
        result = self.pm.get_prompt(
            "verifier",
            context="Temperature data shows spike at bearing",
            claims=[{"text": "Bearing failure"}, {"text": "Pump cavitation"}],
        )
        assert isinstance(result, str)
        assert "Bearing failure" in result

    def test_get_prompt_rca_analysis(self):
        result = self.pm.get_prompt(
            "rca_analysis",
            query="Pump failure",
            evidence=[],
            structured_data={},
            graph_context={"nodes": [], "relationships": []},
        )
        assert isinstance(result, str)

    def test_get_prompt_compliance_intelligence(self):
        result = self.pm.get_prompt(
            "compliance_intelligence",
            query="Check ISO compliance",
            evidence=[],
            requirements=[],
        )
        assert isinstance(result, str)

    def test_get_prompt_report_composer(self):
        result = self.pm.get_prompt(
            "report_composer",
            query="Pump failure",
            intent="failure_analysis",
            asset_intelligence={},
            rca_analysis={},
            compliance_package={},
            lessons_learned={},
        )
        assert isinstance(result, str)

    def test_get_prompt_asset_intelligence(self):
        result = self.pm.get_prompt(
            "asset_intelligence",
            query="Asset health assessment",
            evidence=[],
            structured_data={},
            graph_context={"nodes": [], "relationships": []},
        )
        assert isinstance(result, str)

    def test_get_prompt_lessons_learned(self):
        result = self.pm.get_prompt(
            "lessons_learned",
            query="Similar past failures",
            evidence=[],
            graph_context={"nodes": [], "relationships": []},
        )
        assert isinstance(result, str)

    def test_invalid_template_name_empty(self):
        with pytest.raises(ValueError, match="Invalid prompt template name"):
            self.pm.get_prompt("")

    def test_invalid_template_name_slash(self):
        with pytest.raises(ValueError, match="Invalid prompt template name"):
            self.pm.get_prompt("../etc/passwd")

    def test_invalid_template_name_backslash(self):
        with pytest.raises(ValueError, match="Invalid prompt template name"):
            self.pm.get_prompt("..\\etc\\passwd")

    def test_nonexistent_template(self):
        with pytest.raises(TemplateNotFound):
            self.pm.get_prompt("nonexistent_template_xyz")


# =====================================================================
# Test: Registry
# =====================================================================


class TestPromptRegistry:
    def setup_method(self):
        self.pm = PromptManager(enable_cache=False)

    def test_register_prompt(self):
        meta = self.pm.register(
            name="asset_qa",
            description="Answer asset questions",
            version="1.2.0",
            required_vars=["query", "evidence"],
            tags=["retrieval"],
            agent="asset_intelligence",
        )
        assert meta.name == "asset_qa"
        assert meta.version == "1.2.0"

    def test_get_metadata(self):
        self.pm.register(name="test_prompt", version="2.0.0")
        meta = self.pm.get_metadata("test_prompt")
        assert meta is not None
        assert meta.version == "2.0.0"

    def test_get_metadata_not_found(self):
        meta = self.pm.get_metadata("nonexistent")
        assert meta is None

    def test_list_registered(self):
        self.pm.register(name="p1", agent="agent1")
        self.pm.register(name="p2", agent="agent2")
        registered = self.pm.list_registered()
        assert len(registered) == 2

    def test_list_by_agent(self):
        self.pm.register(name="p1", agent="rca")
        self.pm.register(name="p2", agent="rca")
        self.pm.register(name="p3", agent="compliance")
        rca_prompts = self.pm.list_by_agent("rca")
        assert len(rca_prompts) == 2
        assert "p1" in rca_prompts
        assert "p2" in rca_prompts

    def test_list_by_tag(self):
        self.pm.register(name="p1", tags=["retrieval", "fast"])
        self.pm.register(name="p2", tags=["reasoning"])
        self.pm.register(name="p3", tags=["retrieval", "slow"])
        retrieval_prompts = self.pm.list_by_tag("retrieval")
        assert len(retrieval_prompts) == 2

    def test_get_version(self):
        self.pm.register(name="test", version="3.1.0")
        assert self.pm.get_version("test") == "3.1.0"

    def test_get_version_not_found(self):
        assert self.pm.get_version("nonexistent") is None

    def test_render_updates_stats(self):
        self.pm.register(name="asset_qa")
        self.pm.get_prompt("asset_qa", query="test", evidence=[])
        meta = self.pm.get_metadata("asset_qa")
        assert meta.render_count == 1
        assert meta.last_rendered_at is not None


# =====================================================================
# Test: Caching
# =====================================================================


class TestPromptCaching:
    def setup_method(self):
        self.pm = PromptManager(enable_cache=True, cache_ttl_seconds=60.0)

    def test_cache_hit(self):
        result1 = self.pm.get_prompt("asset_qa", query="test", evidence=[])
        result2 = self.pm.get_prompt("asset_qa", query="test", evidence=[])
        assert result1 == result2
        stats = self.pm.cache_stats()
        assert stats["cache_hits"] == 1
        assert stats["total_renders"] == 1

    def test_cache_miss_different_args(self):
        self.pm.get_prompt("asset_qa", query="test1", evidence=[])
        self.pm.get_prompt("asset_qa", query="test2", evidence=[])
        stats = self.pm.cache_stats()
        assert stats["total_renders"] == 2
        assert stats["cache_hits"] == 0

    def test_cache_expiry(self):
        pm = PromptManager(enable_cache=True, cache_ttl_seconds=0.1)
        pm.get_prompt("asset_qa", query="test", evidence=[])
        time.sleep(0.2)
        pm.get_prompt("asset_qa", query="test", evidence=[])
        stats = pm.cache_stats()
        assert stats["total_renders"] == 2

    def test_clear_cache(self):
        self.pm.get_prompt("asset_qa", query="test", evidence=[])
        cleared = self.pm.clear_cache()
        assert cleared == 1
        stats = self.pm.cache_stats()
        assert stats["entries"] == 0

    def test_cache_disabled(self):
        pm = PromptManager(enable_cache=False)
        pm.get_prompt("asset_qa", query="test", evidence=[])
        pm.get_prompt("asset_qa", query="test", evidence=[])
        stats = pm.cache_stats()
        assert stats["enabled"] is False
        assert stats["cache_hits"] == 0

    def test_cache_stats(self):
        self.pm.get_prompt("asset_qa", query="test", evidence=[])
        stats = self.pm.cache_stats()
        assert stats["enabled"] is True
        assert stats["entries"] == 1
        assert stats["total_renders"] == 1
        assert stats["hit_rate"] == 0.0

    def test_cache_hit_rate(self):
        self.pm.get_prompt("asset_qa", query="test", evidence=[])
        self.pm.get_prompt("asset_qa", query="test", evidence=[])
        self.pm.get_prompt("asset_qa", query="test", evidence=[])
        stats = self.pm.cache_stats()
        # First call renders (total_renders=1), 2nd+3rd hit cache (cache_hits=2)
        assert stats["total_renders"] == 1
        assert stats["cache_hits"] == 2


# =====================================================================
# Test: Validation
# =====================================================================


class TestPromptValidation:
    def setup_method(self):
        self.pm = PromptManager(enable_cache=False)
        self.pm.register(
            name="asset_qa",
            required_vars=["query", "evidence"],
        )

    def test_all_vars_provided(self):
        missing = self.pm.validate_template_vars(
            "asset_qa",
            {"query": "test", "evidence": []},
        )
        assert missing == []

    def test_missing_vars(self):
        missing = self.pm.validate_template_vars(
            "asset_qa",
            {"query": "test"},
        )
        assert missing == ["evidence"]

    def test_unregistered_prompt(self):
        missing = self.pm.validate_template_vars(
            "unregistered",
            {"query": "test"},
        )
        assert missing == []


# =====================================================================
# Test: Summary
# =====================================================================


class TestPromptManagerSummary:
    def test_summary(self):
        pm = PromptManager(enable_cache=True)
        pm.register(name="test", agent="agent1")
        s = pm.summary()
        assert "template_path" in s
        assert "available_templates" in s
        assert s["registered_count"] == 1
        assert "cache" in s
