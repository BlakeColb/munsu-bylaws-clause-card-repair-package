from pathlib import Path

import pytest

from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
    SourceRecordError,
    SourceWarning,
)


def test_source_extraction_serializes_blocks_warnings_and_provider_metadata() -> None:
    extraction = SourceExtraction(
        slug="fictional-bylaw",
        source_path="sources/fictional-bylaw.pdf",
        source_hash="abc123",
        provider="reducto",
        status="review_required",
        blocks=[
            SourceBlock(
                block_id="fictional-bylaw-p1-b1",
                block_type="paragraph",
                text="Fictional OCR text.",
                anchor=SourceAnchor(page=1, original_page=1),
                confidence=0.55,
            )
        ],
        warnings=[
            SourceWarning(
                category="ocr_low_confidence",
                severity="warning",
                message="Low confidence OCR text needs review.",
                anchor=SourceAnchor(page=1, original_page=1),
                confidence=0.55,
            )
        ],
        provider_metadata=ProviderMetadata(
            provider="reducto",
            job_id="job-fictional-001",
            page_count=1,
            settings={"extraction_mode": "ocr"},
        ),
    )

    dumped = extraction.model_dump(mode="json")

    assert dumped["status"] == "review_required"
    assert dumped["blocks"][0]["anchor"]["page"] == 1
    assert dumped["warnings"][0]["category"] == "ocr_low_confidence"
    assert dumped["provider_metadata"]["job_id"] == "job-fictional-001"


def test_source_extraction_writes_json_and_exact_text_sidecars(tmp_path: Path) -> None:
    extraction = SourceExtraction(
        slug="fictional-policy",
        source_path="sources/fictional-policy.md",
        source_hash="def456",
        provider="markdown",
        status="ok",
        blocks=[
            SourceBlock(
                block_id="fictional-policy-L1-L3",
                block_type="body",
                text="Exact fictional source text.",
                anchor=SourceAnchor(line_start=1, line_end=3),
                confidence=None,
            )
        ],
        warnings=[],
        provider_metadata=ProviderMetadata(provider="markdown"),
    )

    written = extraction.write_sidecars(tmp_path, text_extension=".md")

    metadata_path = tmp_path / ".raw" / "extraction" / "fictional-policy.json"
    text_path = tmp_path / ".raw" / "extraction" / "fictional-policy.md"
    assert written.metadata_path == metadata_path
    assert written.text_path == text_path
    assert metadata_path.is_file()
    assert text_path.read_text(encoding="utf-8") == "Exact fictional source text.\n"


def test_sidecar_writing_rejects_slug_path_traversal(tmp_path: Path) -> None:
    extraction = SourceExtraction(
        slug="../outside",
        source_path="sources/outside.md",
        source_hash="bad",
        provider="markdown",
        status="ok",
        blocks=[],
        warnings=[],
        provider_metadata=ProviderMetadata(provider="markdown"),
    )

    with pytest.raises(SourceRecordError):
        extraction.write_sidecars(tmp_path)


def test_warning_categories_include_scanned_pdf_failure_modes() -> None:
    categories = SourceWarning.categories()

    assert "ocr_low_confidence" in categories
    assert "provider_timeout" in categories
    assert "provider_rate_limit" in categories
    assert "pdf_password_protected" in categories
    assert "pdf_corrupt_or_unsupported" in categories
