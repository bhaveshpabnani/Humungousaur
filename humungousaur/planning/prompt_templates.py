from __future__ import annotations

from functools import lru_cache
from importlib import resources


PROMPT_RESOURCE = "resources/prompts/planning.yaml"


class PromptTemplateError(ValueError):
    """Raised when a bundled prompt template is missing or malformed."""


def render_prompt_template(name: str, *, resource: str = PROMPT_RESOURCE, **values: object) -> str:
    template = load_prompt_template(name, resource=resource)
    try:
        return template.format(**values)
    except KeyError as exc:
        raise PromptTemplateError(f"Prompt template {name!r} is missing value {exc.args[0]!r}.") from exc


@lru_cache(maxsize=None)
def load_prompt_templates(resource: str = PROMPT_RESOURCE) -> dict[str, str]:
    text = resources.files("humungousaur").joinpath(resource).read_text(encoding="utf-8")
    templates = _parse_literal_block_yaml(text)
    if not templates:
        raise PromptTemplateError(f"No prompt templates were loaded from {resource}.")
    return templates


def load_prompt_template(name: str, *, resource: str = PROMPT_RESOURCE) -> str:
    templates = load_prompt_templates(resource)
    try:
        return templates[name]
    except KeyError as exc:
        raise PromptTemplateError(f"Unknown prompt template {name!r} in {resource}.") from exc


def _parse_literal_block_yaml(text: str) -> dict[str, str]:
    templates: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_lines
        if current_key is not None:
            templates[current_key] = "\n".join(current_lines).rstrip() + "\n"
        current_key = None
        current_lines = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() and current_key is None:
            continue
        if current_key is None and raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and raw_line.strip().endswith(": |"):
            flush()
            current_key = raw_line.strip()[:-3].strip()
            if not current_key:
                raise PromptTemplateError(f"Empty prompt template key at line {line_number}.")
            continue
        if current_key is None:
            raise PromptTemplateError(f"Unsupported prompt template syntax at line {line_number}: {raw_line}")
        if raw_line.startswith("  "):
            current_lines.append(raw_line[2:])
        elif not raw_line.strip():
            current_lines.append("")
        else:
            raise PromptTemplateError(f"Expected indented literal block line at line {line_number}: {raw_line}")

    flush()
    return templates
