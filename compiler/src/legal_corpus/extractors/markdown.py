"""Markdown source extraction."""

from hashlib import sha256
from pathlib import Path
import re

from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def extract_markdown(
    path: Path,
    *,
    slug: str,
    source_path: str,
    title: str | None = None,
) -> SourceExtraction:
    """Extract a Markdown source file into normalized source records."""
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    heading_stack: list[str] = []
    blocks: list[SourceBlock] = []
    body_lines: list[str] = []
    body_start: int | None = None

    def flush_body(end_line: int) -> None:
        nonlocal body_lines, body_start
        if body_start is None or not body_lines:
            body_lines = []
            body_start = None
            return
        block_text = "\n".join(body_lines)
        blocks.append(
            SourceBlock(
                block_id=f"{slug}-L{body_start}-L{end_line}",
                block_type="body",
                text=block_text,
                anchor=SourceAnchor(line_start=body_start, line_end=end_line),
                heading_path=list(heading_stack),
            )
        )
        body_lines = []
        body_start = None

    for index, line in enumerate(lines, start=1):
        heading = _HEADING_RE.match(line)
        if heading:
            flush_body(index - 1)
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading_text)
            blocks.append(
                SourceBlock(
                    block_id=f"{slug}-L{index}-L{index}",
                    block_type="heading",
                    text=line,
                    anchor=SourceAnchor(line_start=index, line_end=index),
                    heading_path=list(heading_stack),
                )
            )
            continue

        if line.strip():
            if body_start is None:
                body_start = index
            body_lines.append(line)
        else:
            flush_body(index - 1)

    flush_body(len(lines))

    return SourceExtraction(
        slug=slug,
        title=title,
        source_path=source_path,
        source_hash=sha256(raw).hexdigest(),
        provider="markdown",
        status="ok",
        blocks=blocks,
        warnings=[],
        provider_metadata=ProviderMetadata(provider="markdown"),
    )
