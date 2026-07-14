"""Parsed legal structure records for Phase 3."""

from pathlib import Path
import re
from typing import Literal

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legal_corpus.source_records import SourceAnchor


UnitType = Literal[
    "instrument",
    "part",
    "section",
    "article",
    "policy",
    "schedule",
    "appendix",
    "clause",
    "paragraph",
    "subparagraph",
    "unknown",
]
ReferenceType = Literal[
    "read_with",
    "subject_to",
    "despite",
    "exception_to",
    "amends",
    "supersedes",
    "higher_authority_than",
    "section_reference",
]
ResolutionStatus = Literal["resolved", "unresolved"]
_SAFE_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class StructureRecordError(RuntimeError):
    """Raised when legal structure records cannot be written or validated."""


class LegalUnit(BaseModel):
    """A parsed legal unit such as an instrument, section, or numbered clause."""

    model_config = ConfigDict(extra="forbid")

    clause_id: str
    slug: str
    unit_type: UnitType
    text: str
    anchor: SourceAnchor
    title: str | None = None
    number: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    parent_clause_id: str | None = None
    parent_chain: list[str] = Field(default_factory=list)
    is_top_level: bool = False
    source_block_id: str | None = None
    metadata: dict[str, str | list[str]] = Field(default_factory=dict)


class DefinitionRecord(BaseModel):
    """A parsed, instrument-scoped definition."""

    model_config = ConfigDict(extra="forbid")

    term: str
    slug: str
    instrument_slug: str
    source_unit_id: str
    definition_text: str
    anchor: SourceAnchor
    scope: str = "instrument"


class ReferenceRecord(BaseModel):
    """A parsed explicit cross-reference."""

    model_config = ConfigDict(extra="forbid")

    reference_id: str
    reference_type: ReferenceType
    source_unit_id: str
    reference_text: str
    anchor: SourceAnchor
    resolution_status: ResolutionStatus
    resolved_target_id: str | None = None
    resolved_target_slug: str | None = None


class StructureWriteResult(BaseModel):
    """Paths written for legal structure sidecars."""

    model_config = ConfigDict(extra="forbid")

    structure_path: Path


class LegalStructure(BaseModel):
    """Parsed legal structure for a source instrument."""

    model_config = ConfigDict(extra="forbid")

    instrument_slug: str
    instrument_title: str
    document_type: str
    source_path: str
    source_hash: str
    units: list[LegalUnit]
    definitions: list[DefinitionRecord] = Field(default_factory=list)
    references: list[ReferenceRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unit_identity_and_parent_links(self) -> Self:
        unit_ids = [unit.clause_id for unit in self.units]
        duplicates = sorted({unit_id for unit_id in unit_ids if unit_ids.count(unit_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate clause_id values: {duplicates}")

        known_ids = set(unit_ids)
        for unit in self.units:
            if unit.is_top_level:
                continue
            if not unit.parent_clause_id:
                raise ValueError(f"{unit.clause_id} is missing parent_clause_id")
            if unit.parent_clause_id not in known_ids:
                raise ValueError(
                    f"{unit.clause_id} references missing parent {unit.parent_clause_id}"
                )
            if not unit.parent_chain:
                raise ValueError(f"{unit.clause_id} is missing parent_chain")
            missing_chain_ids = [
                chain_id for chain_id in unit.parent_chain if chain_id not in known_ids
            ]
            if missing_chain_ids:
                raise ValueError(
                    f"{unit.clause_id} parent_chain references missing ids: {missing_chain_ids}"
                )
            if unit.parent_clause_id not in unit.parent_chain:
                raise ValueError(
                    f"{unit.clause_id} parent_chain does not include parent_clause_id"
                )
        return self

    def write_sidecar(self, output_root: Path) -> StructureWriteResult:
        """Write `.raw/extraction/{slug}.structure.json`."""
        if not _SAFE_STEM.fullmatch(self.instrument_slug):
            raise StructureRecordError(f"unsafe structure slug: {self.instrument_slug}")

        extraction_root = output_root / ".raw" / "extraction"
        extraction_root.mkdir(parents=True, exist_ok=True)

        structure_path = _safe_child(
            extraction_root,
            f"{self.instrument_slug}.structure.json",
        )
        structure_path.write_text(
            self.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        return StructureWriteResult(structure_path=structure_path)


def _safe_child(root: Path, filename: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root / filename).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise StructureRecordError(
            f"structure sidecar path escapes output root: {filename}"
        ) from error
    return candidate
