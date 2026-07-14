from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a Markdown file."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} does not start with YAML frontmatter")

    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        raise ValueError(f"{path} does not close YAML frontmatter")

    parsed = yaml.safe_load("\n".join(lines[1:closing_index])) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} frontmatter must parse to a mapping")

    return parsed
