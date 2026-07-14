from pathlib import Path

from legal_corpus.extractors.markdown import extract_markdown


def test_markdown_extraction_preserves_heading_path_and_line_anchors(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fictional-policy.md"
    source.write_text(
        "# Fictional Policy\n\n"
        "Opening exact text.\n\n"
        "## Section 1 - Notice\n\n"
        "1.1 A fictional notice must be posted.\n"
        "1.2 It must name the fictional fund.\n\n"
        "### Exception\n\n"
        "This phase does not parse legal exceptions yet.\n",
        encoding="utf-8",
    )

    extraction = extract_markdown(
        source,
        slug="fictional-policy",
        source_path="sources/fictional-policy.md",
        title="Fictional Policy",
    )

    assert extraction.provider == "markdown"
    body_blocks = [block for block in extraction.blocks if block.block_type == "body"]
    assert body_blocks[0].heading_path == ["Fictional Policy"]
    assert body_blocks[0].anchor.line_start == 3
    section_block = next(block for block in body_blocks if "1.1" in block.text)
    assert section_block.heading_path == [
        "Fictional Policy",
        "Section 1 - Notice",
    ]
    assert section_block.anchor.line_start == 7
    assert section_block.anchor.line_end == 8
    assert "1.1 A fictional notice must be posted." in section_block.text


def test_markdown_extraction_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "fictional-bylaw.md"
    source.write_text("# Fictional Bylaw\n\nText.\n", encoding="utf-8")

    first = extract_markdown(
        source,
        slug="fictional-bylaw",
        source_path="sources/fictional-bylaw.md",
    )
    second = extract_markdown(
        source,
        slug="fictional-bylaw",
        source_path="sources/fictional-bylaw.md",
    )

    assert [block.block_id for block in first.blocks] == [
        block.block_id for block in second.blocks
    ]
    assert first.blocks[0].text == "# Fictional Bylaw"
