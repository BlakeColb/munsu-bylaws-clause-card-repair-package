from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


DocumentType = Literal["bylaw", "policy", "collective_agreement", "legislation"]
DocumentStatus = Literal["active", "draft", "superseded", "archived"]
Confidentiality = Literal["public", "internal", "restricted", "confidential"]
DocumentProfile = Literal["generic", "munsu_bylaws_v1", "munsu_policy_v1"]
SyncEligibility = Literal["blocked", "staging_only", "production_pilot", "production_batch"]


class ManifestDocument(BaseModel):
    """A source document entry in sources/manifest.yaml."""

    model_config = ConfigDict(extra="forbid")

    source_path: str
    document_type: DocumentType
    title: str
    slug: str
    jurisdiction: str
    authority_rank: int = Field(strict=True)
    status: DocumentStatus
    confidentiality: Confidentiality
    effective_date: str | None
    owner: str
    version: str
    reviewed_by: str | None
    metadata_notes: list[str]
    profile: DocumentProfile = "generic"
    corpus_id: str = "legal-corpus"
    corpus_version: str = "fixture-v1"
    target_namespace: str | None = None
    classification: str | None = None
    sync_eligibility: SyncEligibility = "blocked"
    review_date: str | None = None

    @model_validator(mode="after")
    def explain_nullable_required_fields(self) -> Self:
        note_text = "\n".join(self.metadata_notes).lower()
        for field_name in ("effective_date", "reviewed_by"):
            if getattr(self, field_name) is None and field_name.lower() not in note_text:
                raise ValueError(
                    f"{field_name} is null and must be explained in metadata_notes"
                )
        return self


class Manifest(BaseModel):
    """Top-level source manifest."""

    model_config = ConfigDict(extra="forbid")

    documents: list[ManifestDocument]


def load_manifest(path: Path) -> Manifest:
    """Load and validate a source manifest."""
    with path.open("r", encoding="utf-8") as manifest_file:
        data = yaml.safe_load(manifest_file)

    return Manifest.model_validate(data)
