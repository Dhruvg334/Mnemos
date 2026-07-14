import os
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptManager:
    """
    Manages loading and formatting of prompts using Jinja2 templates.
    Centralizes all LLM instructions.
    """
    def __init__(self, template_dir: str = "prompts/templates"):
        # In a real app, template_dir would be an absolute path
        # For now, we assume it's relative to this module or provided
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.template_path = os.path.join(base_path, "templates")

        if not os.path.exists(self.template_path):
            os.makedirs(self.template_path)

        self.env = Environment(
            loader=FileSystemLoader(self.template_path),
            autoescape=select_autoescape()
        )

    def get_prompt(self, template_name: str, **kwargs: Any) -> str:
        """Load and format a template."""
        template = self.env.get_template(f"{template_name}.j2")
        return template.render(**kwargs)

    def list_templates(self) -> list[str]:
        return self.env.list_templates()
