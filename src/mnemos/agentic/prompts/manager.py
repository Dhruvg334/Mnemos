from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class PromptManager:
    """Load and render version-controlled agent prompt templates."""

    def __init__(self) -> None:
        self.template_path = Path(__file__).resolve().parent / "templates"
        if not self.template_path.is_dir():
            raise RuntimeError(
                f"Prompt template directory is missing: {self.template_path}"
            )

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_path)),
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"),
                default_for_string=False,
                default=False,
            ),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def get_prompt(self, template_name: str, **kwargs: Any) -> str:
        if not template_name or "/" in template_name or "\\" in template_name:
            raise ValueError("Invalid prompt template name")
        template = self.env.get_template(f"{template_name}.j2")
        return template.render(**kwargs)

    def list_templates(self) -> list[str]:
        return sorted(self.env.list_templates())
