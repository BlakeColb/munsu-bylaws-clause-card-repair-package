"""Human-readable reporting for compiled legal corpora."""

from __future__ import annotations

from pathlib import Path

from legal_corpus.validation_records import CorpusReport
from legal_corpus.validators.gbrain import validate_gbrain_corpus


def build_corpus_report(output_root: Path) -> CorpusReport:
    result = validate_gbrain_corpus(output_root)
    return CorpusReport(
        root=result.root,
        markdown_count=result.markdown_count,
        document_count=result.document_count,
        legal_clause_count=result.legal_clause_count,
        definition_count=result.definition_count,
        unresolved_reference_count=result.unresolved_reference_count,
        provenance_count=result.provenance_count,
        extraction_warning_count=result.extraction_warning_count,
        validation_status=result.validation_status or ("passed" if result.passed else "failed"),
        warning_count=result.warning_count,
        blocking_error_count=result.blocking_error_count,
    )


def render_corpus_report(report: CorpusReport) -> str:
    return "\n".join(
        [
            "Legal Corpus Report",
            f"Root: {report.root}",
            f"Documents: {report.document_count}",
            f"Legal clauses: {report.legal_clause_count}",
            f"Definitions: {report.definition_count}",
            f"Unresolved references: {report.unresolved_reference_count}",
            f"Validation status: {report.validation_status or 'unknown'}",
            f"Warnings: {report.warning_count}",
            f"Blocking errors: {report.blocking_error_count}",
            f"Provenance sidecars: {report.provenance_count}",
            f"Extraction warnings: {report.extraction_warning_count}",
            "Sync eligibility: not approved by this report",
        ]
    ) + "\n"
