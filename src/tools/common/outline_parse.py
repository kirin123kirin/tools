from __future__ import annotations

import re
from dataclasses import dataclass

from tools.common.textfile import normalize_newlines

_HEADING_RE = re.compile(r"^#{1,6} .+")


@dataclass(frozen=True)
class OutlineItem:
    title: str
    body: str  # "\n"-joined when multi-line; "" when there's no body


def parse_outline(text: str) -> list[OutlineItem]:
    """Auto-detect one of three outline formats and extract title/body pairs.

    Tried in order: Markdown headings, tab-separated lines, blank-line-
    delimited blocks (the fallback for anything that matches neither).
    """
    normalized = normalize_newlines(text)
    lines = normalized.split("\n")

    if any(_HEADING_RE.match(line) for line in lines):
        return _parse_markdown_headings(lines)
    if "\t" in normalized:
        return _parse_tab_separated(lines)
    return _parse_blank_line_blocks(normalized)


def _parse_markdown_headings(lines: list[str]) -> list[OutlineItem]:
    items: list[OutlineItem] = []
    title: str | None = None
    body_lines: list[str] = []

    def flush() -> None:
        if title is not None:
            trimmed = list(body_lines)
            while trimmed and not trimmed[-1].strip():
                trimmed.pop()
            items.append(OutlineItem(title=title, body="\n".join(trimmed)))

    for line in lines:
        if _HEADING_RE.match(line):
            flush()
            title = line.split(" ", 1)[1].strip()
            body_lines = []
        elif title is not None:
            body_lines.append(line)
    flush()

    return items


def _parse_tab_separated(lines: list[str]) -> list[OutlineItem]:
    items: list[OutlineItem] = []
    for line in lines:
        if not line.strip():
            continue
        if "\t" in line:
            title, body = line.split("\t", 1)
            items.append(OutlineItem(title=title.strip(), body=body.strip()))
        else:
            items.append(OutlineItem(title=line.strip(), body=""))
    return items


def _parse_blank_line_blocks(normalized: str) -> list[OutlineItem]:
    blocks = re.split(r"\n\s*\n", normalized.strip())
    items: list[OutlineItem] = []
    for block in blocks:
        block = block.strip("\n")
        if not block.strip():
            continue
        block_lines = block.split("\n")
        title = block_lines[0].strip()
        body = "\n".join(block_lines[1:]).strip("\n")
        items.append(OutlineItem(title=title, body=body))
    return items
