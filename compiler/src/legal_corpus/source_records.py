"""Normalized source extraction records for Phase 2."""

from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ExtractionStatus = Literal["ok", "review_required", "partial", "failed"]
WarningSeverity = Literal["info", "warning", "error"]
ProviderName = Literal["markdown", "reducto", "local_pdf"]

WARNING_CATEGORIES = {
    "missing_provider_key",
    "provider_auth",
    "provider_rate_limit",
    "provider_timeout",
    "provider_connection",
    "provider_api_error",
    "provider_validation",
    "pdf_password_protected",
    "pdf_corrupt_or_unsupported",
    "ocr_empty",
    "ocr_low_confidence",
    "partial_extraction",
    "unknown_provider_error",
}

_SAFE_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class SourceRecordError(RuntimeError):
    """Raised when source extraction records cannot be written or validated."""


class SourceAnchor(BaseModel):
    """Location evidence for extracted text."""

    model_config = ConfigDict(extra="forbid")

    page: int | None = None
    original_page: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    bbox: list[float] | None = None


class SourceWarning(BaseModel):
    """Reviewable warning from local extraction or a provider."""

    model_config = ConfigDict(extra="forbid")

    category: str
    severity: WarningSeverity
    message: str
    anchor: SourceAnchor | None = None
    confidence: float | None = None
    provider_code: str | int | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in WARNING_CATEGORIES:
            raise ValueError(f"unknown warning category: {value}")
        return value

    @classmethod
    def categories(cls) -> set[str]:
        return set(WARNING_CATEGORIES)


class ProviderMetadata(BaseModel):
    """Provider job details needed to debug extraction later."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    job_id: str | None = None
    page_count: int | None = None
    duration: float | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    result_type: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error_category: str | None = None


class SourceBlock(BaseModel):
    """A normalized block of exact extracted source text."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    block_type: str
    text: str
    anchor: SourceAnchor
    confidence: float | None = None
    heading_path: list[str] = Field(default_factory=list)
    bbox: list[float] | None = None
    ocr: dict[str, Any] = Field(default_factory=dict)


class SidecarWriteResult(BaseModel):
    """Paths written for an extraction sidecar pair."""

    model_config = ConfigDict(extra="forbid")

    metadata_path: Path
    text_path: Path


class SourceExtraction(BaseModel):
    """Project-owned normalized extraction output."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    source_path: str
    source_hash: str
    provider: ProviderName
    status: ExtractionStatus
    blocks: list[SourceBlock]
    warnings: list[SourceWarning]
    provider_metadata: ProviderMetadata
    title: str | None = None

    def exact_text(self) -> str:
        text = "\n\n".join(block.text for block in self.blocks if block.text)
        return text + "\n" if text else ""

    def write_sidecars(
        self,
        output_root: Path,
        *,
        text_extension: str = ".txt",
    ) -> SidecarWriteResult:
        """Write JSON metadata and exact extracted text under `.raw/extraction`."""
        if not _SAFE_STEM.fullmatch(self.slug):
            raise SourceRecordError(f"unsafe extraction slug: {self.slug}")
        if not text_extension.startswith(".") or "/" in text_extension or "\\" in text_extension:
            raise SourceRecordError(f"unsafe text extension: {text_extension}")

        extraction_root = output_root / ".raw" / "extraction"
        extraction_root.mkdir(parents=True, exist_ok=True)

        metadata_path = _safe_child(extraction_root, f"{self.slug}.json")
        text_path = _safe_child(extraction_root, f"{self.slug}{text_extension}")

        metadata_path.write_text(
            self.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        text_path.write_text(self.exact_text(), encoding="utf-8")
        return SidecarWriteResult(metadata_path=metadata_path, text_path=text_path)


def _safe_child(root: Path, filename: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root / filename).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise SourceRecordError(f"sidecar path escapes output root: {filename}") from error
    return candidate
