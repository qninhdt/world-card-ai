"""Load and render Jinja2 prompt templates from the prompts/ directory."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **kwargs) -> str:
    """Render a prompt template with the given variables."""
    tpl = _env.get_template(template_name)
    return tpl.render(**kwargs).strip()
