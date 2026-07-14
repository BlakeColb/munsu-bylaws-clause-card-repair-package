from __future__ import annotations

from pathlib import Path

import yaml

from legal_corpus.compiler import compile_sources
from legal_corpus.export_records import ImportManifest
from legal_corpus.scaffold import create_scaffold
from legal_corpus.validators.gbrain import validate_gbrain_corpus


def compiled_output(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled"
    create_scaffold(workspace)
    compile_sources(workspace, output)
    return output


def issue_categories(output: Path) -> set[str]:
    return {issue.category for issue in validate_gbrain_corpus(output).issues}


def clause_path(output: Path, slug: str = "example-bylaw-1.1") -> Path:
    return output / "legal" / "clauses" / "bylaws" / f"{slug}.md"


def test_valid_compiled_corpus_passes_with_unresolved_warning(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)

    result = validate_gbrain_corpus(output)

    assert result.passed is True
    assert result.document_count == 4
    assert result.legal_clause_count >= 10
    assert result.definition_count >= 1
    assert result.unresolved_reference_count >= 1
    assert "unresolved_reference" in {issue.category for issue in result.issues}
    assert all(issue.severity == "warning" for issue in result.issues)


def test_malformed_frontmatter_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    clause_path(output).write_text("---\ntitle: [broken\n---\n# Broken\n", encoding="utf-8")

    assert "frontmatter" in issue_categories(output)


def test_duplicate_slug_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = clause_path(output, "example-bylaw-1.2")
    target.write_text(
        target.read_text(encoding="utf-8").replace("slug: example-bylaw-1.2", "slug: example-bylaw-1.1"),
        encoding="utf-8",
    )

    assert "duplicate_slug" in issue_categories(output)


def test_duplicate_clause_id_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = clause_path(output, "example-bylaw-1.2")
    target.write_text(
        target.read_text(encoding="utf-8").replace("clause_id: example-bylaw-1.2", "clause_id: example-bylaw-1.1"),
        encoding="utf-8",
    )

    assert "duplicate_clause_id" in issue_categories(output)


def test_missing_required_frontmatter_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = clause_path(output)
    lines = [
        line
        for line in target.read_text(encoding="utf-8").splitlines()
        if not line.startswith("source_hash:")
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert "missing_required_field" in issue_categories(output)


def test_body_wikilink_to_missing_page_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = clause_path(output)
    target.write_text(target.read_text(encoding="utf-8") + "\n[[missing-target]]\n", encoding="utf-8")

    assert "broken_wikilink" in issue_categories(output)


def test_frontmatter_wikilink_to_missing_page_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = clause_path(output)
    target.write_text(
        target.read_text(encoding="utf-8").replace("- example-bylaw-section-1", "- missing-parent-target"),
        encoding="utf-8",
    )

    assert "broken_wikilink" in issue_categories(output)


def test_missing_parent_context_page_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    (output / "legal" / "clauses" / "bylaws" / "example-bylaw-section-1.md").unlink()

    assert "missing_parent" in issue_categories(output)


def test_manifest_hash_drift_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = clause_path(output)
    target.write_text(target.read_text(encoding="utf-8") + "\nEdited after manifest.\n", encoding="utf-8")

    assert "manifest_hash" in issue_categories(output)


def test_generated_schema_doc_hash_drift_is_blocking_error(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = output / "schema.md"
    assert target.is_file()
    target.write_text(target.read_text(encoding="utf-8") + "\nEdited after manifest.\n", encoding="utf-8")

    assert "manifest_hash" in issue_categories(output)


def test_update_manifest_writes_validation_status_without_sync_eligibility(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)

    result = validate_gbrain_corpus(output, update_manifest=True)
    manifest = ImportManifest.model_validate(yaml.safe_load((output / "import-manifest.yaml").read_text(encoding="utf-8")))

    assert result.passed is True
    assert manifest.validation_status == "passed"
    assert manifest.sync_eligible is False
