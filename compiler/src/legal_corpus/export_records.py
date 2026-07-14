"""Generated GBrain export records for Phase 4."""

from hashlib import sha256
from pathlib import Path
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ValidationStatus = Literal["pending", "passed", "failed"]
SyncEligibility = Literal["blocked", "staging_only", "production_pilot", "production_batch"]
ExportFileType = Literal[
    "generated_file",
    "legal_instrument",
    "legal_clause",
    "legal_definition",
    "unresolved_reference",
    "raw_provenance",
    "import_manifest",
]


class ExportRecordError(RuntimeError):
    """Raised when export records or generated paths are invalid."""


class ExportedFile(BaseModel):
    """Metadata for a generated export file."""

    model_config = ConfigDict(extra="forbid")

    path: str
    file_type: ExportFileType = "generated_file"
    sha256: str
    sync_eligible: bool
    source_document_slug: str | None = None
    clause_id: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        _parse_safe_relative_path(value)
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must be a 64-character lowercase hex digest")
        return value


class ImportManifest(BaseModel):
    """Root import manifest for a generated corpus."""

    model_config = ConfigDict(extra="forbid")

    corpus_id: str
    corpus_version: str
    compiler_version: str
    schema_version: str
    generated_at: str
    source_manifest_path: str
    source_manifest_hash: str
    generated_corpus_root: str
    validation_status: ValidationStatus
    sync_eligible: bool
    sync_eligibility: SyncEligibility = "blocked"
    target_namespace: str | None = None
    operator_approval_required: bool = True
    classification: str | None = None
    minimum_gbrain_schema_pack_version: str
    confidentiality_scope: list[str] = Field(default_factory=list)
    access_scope: str
    rollback_target: str | None = None
    previous_corpus_version: str | None = None
    compiler_owned_read_only: bool
    files: list[ExportedFile] = Field(default_factory=list)

    @field_validator("source_manifest_path")
    @classmethod
    def validate_source_manifest_path(cls, value: str) -> str:
        _parse_safe_relative_path(value)
        return value

    @field_validator("source_manifest_hash")
    @classmethod
    def validate_source_manifest_hash(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("source_manifest_hash must be a 64-character lowercase hex digest")
        return value


class ExportWriteResult(BaseModel):
    """Paths written by the GBrain exporter."""

    model_config = ConfigDict(extra="forbid")

    markdown_paths: list[Path] = Field(default_factory=list)
    provenance_paths: list[Path] = Field(default_factory=list)
    import_manifest_path: Path | None = None
    files: list[ExportedFile] = Field(default_factory=list)
    manifest: ImportManifest | None = None


def safe_output_path(output_root: Path, relative_path: str) -> Path:
    """Return a safe child path under the output root."""
    parsed = _parse_safe_relative_path(relative_path)
    root = output_root.resolve()
    candidate = root.joinpath(*parsed.parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ExportRecordError(f"export path escapes output root: {relative_path}") from error
    return candidate


def sha256_file(path: Path) -> str:
    """Return a SHA-256 hex digest for a file."""
    return sha256(path.read_bytes()).hexdigest()


def write_text_with_hash(
    output_root: Path,
    relative_path: str,
    content: str,
    *,
    file_type: ExportFileType = "generated_file",
    sync_eligible: bool = True,
    source_document_slug: str | None = None,
    clause_id: str | None = None,
) -> ExportedFile:
    """Write text under output_root and return file metadata."""
    destination = safe_output_path(output_root, relative_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return ExportedFile(
        path=relative_path,
        file_type=file_type,
        sha256=sha256_file(destination),
        sync_eligible=sync_eligible,
        source_document_slug=source_document_slug,
        clause_id=clause_id,
    )


def _parse_safe_relative_path(relative_path: str) -> PurePosixPath:
    if not relative_path or "\\" in relative_path:
        raise ExportRecordError(f"unsafe export path: {relative_path}")
    parsed = PurePosixPath(relative_path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise ExportRecordError(f"unsafe export path: {relative_path}")
    return parsed
