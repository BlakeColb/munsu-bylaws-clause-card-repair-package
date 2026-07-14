"""Validation and retrieval record models for compiled corpus checks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ValidationSeverity = Literal["error", "warning"]


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: ValidationSeverity
    category: str
    message: str
    path: str | None = None
    target: str | None = None
    clause_id: str | None = None


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    markdown_count: int = 0
    document_count: int = 0
    legal_clause_count: int = 0
    definition_count: int = 0
    unresolved_reference_count: int = 0
    provenance_count: int = 0
    extraction_warning_count: int = 0
    validation_status: str | None = None

    @property
    def blocking_error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def passed(self) -> bool:
        return self.blocking_error_count == 0


class CorpusReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    markdown_count: int = 0
    document_count: int = 0
    legal_clause_count: int = 0
    definition_count: int = 0
    unresolved_reference_count: int = 0
    provenance_count: int = 0
    extraction_warning_count: int = 0
    validation_status: str | None = None
    warning_count: int = 0
    blocking_error_count: int = 0


class GoldQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    expected_clause_ids: list[str] = Field(default_factory=list)
    expected_parent_ids: list[str] = Field(default_factory=list)
    expected_definition_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    path: str
    score: float


class GoldRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    passed: bool
    hits: list[RetrievalHit] = Field(default_factory=list)
    missing_clause_ids: list[str] = Field(default_factory=list)
    missing_parent_ids: list[str] = Field(default_factory=list)
    missing_definition_ids: list[str] = Field(default_factory=list)

    @property
    def missing_targets(self) -> list[str]:
        return [
            *self.missing_clause_ids,
            *self.missing_parent_ids,
            *self.missing_definition_ids,
        ]
