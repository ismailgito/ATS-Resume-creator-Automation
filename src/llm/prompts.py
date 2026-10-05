"""Prompt Loader and Renderer."""

from pathlib import Path
from typing import Any, Dict
from src.config import PROJECT_ROOT


def load_prompt_template(name: str) -> str:
    """Load a prompt markdown template from prompts/ directory."""
    filename = f"{name}.md" if not name.endswith(".md") else name
    path = PROJECT_ROOT / "prompts" / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_prompt(template_str: str, variables: Dict[str, Any]) -> str:
    """Render a prompt template by replacing {{variable_name}} tokens."""
    rendered = template_str
    for key, val in variables.items():
        placeholder = f"{{{{{key}}}}}"
        str_val = str(val) if not isinstance(val, str) else val
        rendered = rendered.replace(placeholder, str_val)
    return rendered
