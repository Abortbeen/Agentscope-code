# -*- coding: utf-8 -*-
"""YAML frontmatter parser for skill and agent definition files."""
import re
from dataclasses import dataclass, field
from typing import Any

import yaml


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n?(.*)",
    re.DOTALL,
)


@dataclass
class FrontmatterDoc:
    """A document with YAML frontmatter and Markdown body."""
    metadata: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    source_path: str | None = None


def parse_frontmatter(content: str, source_path: str | None = None) -> FrontmatterDoc:
    """Parse a string with optional YAML frontmatter.

    Format:
        ---
        key: value
        ---
        Markdown body here

    Args:
        content: The raw file content.
        source_path: Optional path for error messages.

    Returns:
        FrontmatterDoc with parsed metadata and body.
    """
    match = _FRONTMATTER_RE.match(content)
    if match:
        yaml_str, body = match.group(1), match.group(2)
        try:
            metadata = yaml.safe_load(yaml_str)
            if not isinstance(metadata, dict):
                metadata = {}
        except yaml.YAMLError:
            metadata = {}
            body = content
    else:
        metadata = {}
        body = content

    return FrontmatterDoc(
        metadata=metadata,
        body=body.strip(),
        source_path=source_path,
    )


def load_frontmatter_file(path: str) -> FrontmatterDoc:
    """Load and parse a file with frontmatter."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return parse_frontmatter(content, source_path=path)
