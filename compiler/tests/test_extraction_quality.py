from __future__ import annotations

from legal_corpus.extraction_quality import (
    ExtractionQualitySummary,
    compare_extraction_quality,
)


def baseline(**overrides):
    data = {
        "provider": "local",
        "success": True,
        "page_count": 62,
        "page_anchor_coverage": 62,
        "part_headings": 6,
        "lettered_sections": 24,
        "numbered_clauses": 323,
        "definitions": 4,
        "duplicate_heading_ids": 0,
        "missing_heading_ids": 0,
        "hierarchy_transition_errors": 0,
        "unresolved_reference_warnings": 8,
        "material_warnings": 8,
        "source_hash": "8" * 64,
        "deterministic_id_fingerprint": "a" * 64,
        "duration_ms": 1000,
    }
    data.update(overrides)
    return ExtractionQualitySummary(**data)


def test_reducto_is_selected_when_structurally_equivalent_with_fewer_warnings() -> None:
    local = baseline()
    reducto = baseline(provider="reducto", material_warnings=6, duration_ms=2500)

    decision = compare_extraction_quality(local=local, candidate=reducto)

    assert decision.selected_provider == "reducto"
    assert decision.decision == "candidate_selected"
    assert decision.metadata_only


def test_local_is_retained_when_candidate_reduces_page_anchor_coverage() -> None:
    local = baseline()
    reducto = baseline(provider="reducto", page_anchor_coverage=61, material_warnings=2)

    decision = compare_extraction_quality(local=local, candidate=reducto)

    assert decision.selected_provider == "local"
    assert decision.decision == "local_retained"
    assert "page_anchor_coverage_reduced" in decision.reasons


def test_local_is_retained_when_candidate_adds_hierarchy_ambiguity() -> None:
    local = baseline()
    reducto = baseline(provider="reducto", hierarchy_transition_errors=1, material_warnings=2)

    decision = compare_extraction_quality(local=local, candidate=reducto)

    assert decision.selected_provider == "local"
    assert "hierarchy_transition_errors_increased" in decision.reasons


def test_local_is_retained_when_source_hash_or_id_stability_changes() -> None:
    local = baseline()
    reducto = baseline(provider="reducto", deterministic_id_fingerprint="b" * 64)

    decision = compare_extraction_quality(local=local, candidate=reducto)

    assert decision.selected_provider == "local"
    assert "deterministic_id_fingerprint_changed" in decision.reasons


def test_failed_candidate_is_never_selected() -> None:
    local = baseline()
    reducto = baseline(provider="reducto", success=False, page_count=0)

    decision = compare_extraction_quality(local=local, candidate=reducto)

    assert decision.selected_provider == "local"
    assert "candidate_failed" in decision.reasons
