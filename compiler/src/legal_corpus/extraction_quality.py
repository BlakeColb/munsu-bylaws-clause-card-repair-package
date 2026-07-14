"""Metadata-only extraction quality comparison helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionQualitySummary:
    provider: str
    success: bool
    page_count: int
    page_anchor_coverage: int
    part_headings: int
    lettered_sections: int
    numbered_clauses: int
    definitions: int
    duplicate_heading_ids: int
    missing_heading_ids: int
    hierarchy_transition_errors: int
    unresolved_reference_warnings: int
    material_warnings: int
    source_hash: str
    deterministic_id_fingerprint: str
    duration_ms: int


@dataclass(frozen=True)
class ExtractionQualityDecision:
    selected_provider: str
    decision: str
    reasons: tuple[str, ...]
    local: ExtractionQualitySummary
    candidate: ExtractionQualitySummary
    metadata_only: bool = True


def compare_extraction_quality(
    *,
    local: ExtractionQualitySummary,
    candidate: ExtractionQualitySummary,
) -> ExtractionQualityDecision:
    """Select the candidate only when it preserves legal structure quality."""

    reasons: list[str] = []
    if not candidate.success:
        reasons.append("candidate_failed")
    if candidate.source_hash != local.source_hash:
        reasons.append("source_hash_changed")
    if candidate.deterministic_id_fingerprint != local.deterministic_id_fingerprint:
        reasons.append("deterministic_id_fingerprint_changed")
    if candidate.page_count < local.page_count:
        reasons.append("page_count_reduced")
    if candidate.page_anchor_coverage < local.page_anchor_coverage:
        reasons.append("page_anchor_coverage_reduced")
    if candidate.part_headings < local.part_headings:
        reasons.append("part_headings_lost")
    if candidate.lettered_sections < local.lettered_sections:
        reasons.append("lettered_sections_lost")
    if candidate.numbered_clauses < local.numbered_clauses:
        reasons.append("numbered_clauses_lost")
    if candidate.definitions < local.definitions:
        reasons.append("definitions_lost")
    if candidate.duplicate_heading_ids > local.duplicate_heading_ids:
        reasons.append("duplicate_heading_ids_increased")
    if candidate.missing_heading_ids > local.missing_heading_ids:
        reasons.append("missing_heading_ids_increased")
    if candidate.hierarchy_transition_errors > local.hierarchy_transition_errors:
        reasons.append("hierarchy_transition_errors_increased")
    if candidate.material_warnings > local.material_warnings:
        reasons.append("material_warnings_increased")

    if reasons:
        return ExtractionQualityDecision(
            selected_provider=local.provider,
            decision="local_retained",
            reasons=tuple(reasons),
            local=local,
            candidate=candidate,
        )

    positive_reasons = []
    if candidate.material_warnings < local.material_warnings:
        positive_reasons.append("material_warnings_reduced")
    if candidate.unresolved_reference_warnings < local.unresolved_reference_warnings:
        positive_reasons.append("unresolved_reference_warnings_reduced")
    if not positive_reasons:
        positive_reasons.append("candidate_structurally_equivalent")

    return ExtractionQualityDecision(
        selected_provider=candidate.provider,
        decision="candidate_selected",
        reasons=tuple(positive_reasons),
        local=local,
        candidate=candidate,
    )
