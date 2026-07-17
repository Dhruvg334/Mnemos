import pytest
from jinja2 import UndefinedError

from mnemos.agentic.prompts.manager import PromptManager


def test_prompt_templates_are_available():
    manager = PromptManager()
    templates = manager.list_templates()

    assert "planner.j2" in templates
    assert "report_composer.j2" in templates


def test_prompt_manager_rejects_path_traversal():
    manager = PromptManager()

    with pytest.raises(ValueError):
        manager.get_prompt("../planner")


def test_prompt_manager_rejects_missing_required_variables():
    manager = PromptManager()

    with pytest.raises(UndefinedError):
        manager.get_prompt("planner")
