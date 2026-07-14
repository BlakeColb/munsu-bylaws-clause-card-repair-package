"""Local PDF text extraction with page anchors."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
    SourceWarning,
)


class LocalPdfExtractionError(RuntimeError):
    """Raised when no local PDF extractor can read a source file."""


class LocalPdfExtractor:
    """Extract text locally using PyMuPDF when available, then PyPDF2 fallback."""

    provider_name = "local_pdf"

    def extract_pdf(
        self,
        path: Path,
        *,
        slug: str,
        source_path: str,
        title: str | None = None,
    ) -> SourceExtraction:
        try:
            blocks, page_count = _extract_with_pymupdf(path, slug)
            engine = "pymupdf"
        except ImportError:
            blocks, page_count = _extract_with_pypdf2(path, slug)
            engine = "pypdf2"
        except Exception as first_error:
            try:
                blocks, page_count = _extract_with_pypdf2(path, slug)
                engine = "pypdf2"
            except Exception as second_error:
                raise LocalPdfExtractionError(
                    f"local PDF extraction failed: {first_error.__class__.__name__}/{second_error.__class__.__name__}"
                ) from second_error

        warnings: list[SourceWarning] = []
        if not any(block.text.strip() for block in blocks):
            warnings.append(
                SourceWarning(
                    category="partial_extraction",
                    severity="error",
                    message="Local PDF extraction produced no text; OCR provider may be required.",
                )
            )
        return SourceExtraction(
            slug=slug,
            title=title,
            source_path=source_path,
            source_hash=_file_hash(path),
            provider=self.provider_name,
            status="failed" if warnings else "ok",
            blocks=blocks,
            warnings=warnings,
            provider_metadata=ProviderMetadata(
                provider=self.provider_name,
                page_count=page_count,
                settings={"engine": engine, "network": "disabled"},
                warnings=[warning.category for warning in warnings],
            ),
        )


def _extract_with_pymupdf(path: Path, slug: str) -> tuple[list[SourceBlock], int]:
    import fitz  # type: ignore

    blocks: list[SourceBlock] = []
    doc = fitz.open(str(path))
    try:
        for page_index in range(doc.page_count):
            page_number = page_index + 1
            text = doc.load_page(page_index).get_text("text")
            blocks.append(
                SourceBlock(
                    block_id=f"{slug}-p{page_number}-text",
                    block_type="body",
                    text=text,
                    anchor=SourceAnchor(page=page_number, original_page=page_number),
                    confidence=1.0 if text.strip() else None,
                )
            )
        return blocks, doc.page_count
    finally:
        doc.close()


def _extract_with_pypdf2(path: Path, slug: str) -> tuple[list[SourceBlock], int]:
    from PyPDF2 import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    blocks = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        blocks.append(
            SourceBlock(
                block_id=f"{slug}-p{page_index}-text",
                block_type="body",
                text=text,
                anchor=SourceAnchor(page=page_index, original_page=page_index),
                confidence=1.0 if text.strip() else None,
            )
        )
    return blocks, len(reader.pages)


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()
