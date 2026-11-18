"""Shared utilities for rubric-gate scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """Load and parse a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    """Write formatted UTF-8 JSON with a trailing newline."""
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def estimate_tokens(text: str) -> int:
    """Approximate token count (~3.8 chars per token for English/Markdown)."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, int(round(len(stripped) / 3.8)))


def parse_frontmatter(markdown_text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter key/value pairs and return (metadata, body).

    Supports single-line values, quoted strings, and folded/literal blocks (`>-`, `>`).
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", markdown_text, re.DOTALL)
    if not match:
        return {}, markdown_text

    raw_yaml, body = match.group(1), match.group(2)
    meta: dict[str, str] = {}
    current_key: str | None = None
    block_lines: list[str] = []

    def flush_block() -> None:
        nonlocal current_key, block_lines
        if current_key is not None:
            meta[current_key] = " ".join(line.strip() for line in block_lines if line.strip())
        current_key = None
        block_lines = []

    for line in raw_yaml.splitlines():
        if current_key is not None and (line.startswith("  ") or line.startswith("\t") or not line.strip()):
            block_lines.append(line)
            continue
        flush_block()
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val in {">-", ">", "|-", "|"}:
            current_key = key
            block_lines = []
        else:
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            meta[key] = val

    flush_block()
    return meta, body
