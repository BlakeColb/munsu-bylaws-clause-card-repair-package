from pathlib import Path

import pytest

from legal_corpus.export_records import (
    ExportedFile,
    ExportRecordError,
    ImportManifest,
    safe_output_path,
    sha256_file,
    write_text_with_hash,
)


def test_import_manifest_serializes_required_deployment_fields() -> None:
    manifest = ImportManifest(
        corpus_id="legal-corpus-fixture",
        corpus_version="fixture-v1",
        compiler_version="0.1.0",
        schema_version="legal-corpus/v1",
        generated_at="2026-07-10T00:00:00Z",
        source_manifest_path="sources/manifest.yaml",
        source_manifest_hash="a" * 64,
        generated_corpus_root=".",
        validation_status="pending",
        sync_eligible=False,
        minimum_gbrain_schema_pack_version="0.1.0",
        confidentiality_scope=["internal"],
        access_scope="compiler_generated_read_only",
        rollback_target=None,
        previous_corpus_version=None,
        compiler_owned_read_only=True,
        files=[
            ExportedFile(
                path="legal/clauses/bylaws/example-bylaw-1.1.md",
                file_type="legal_clause",
                sha256="b" * 64,
                sync_eligible=True,
                source_document_slug="example-bylaw",
                clause_id="example-bylaw-1.1",
            )
        ],
    )

    dumped = manifest.model_dump(mode="json")

    assert dumped["corpus_id"] == "legal-corpus-fixture"
    assert dumped["corpus_version"] == "fixture-v1"
    assert dumped["compiler_version"] == "0.1.0"
    assert dumped["schema_version"] == "legal-corpus/v1"
    assert dumped["generated_at"] == "2026-07-10T00:00:00Z"
    assert dumped["source_manifest_hash"] == "a" * 64
    assert dumped["validation_status"] == "pending"
    assert dumped["sync_eligible"] is False
    assert dumped["compiler_owned_read_only"] is True
    assert dumped["files"][0]["sha256"] == "b" * 64


def test_import_manifest_rejects_invalid_validation_status() -> None:
    with pytest.raises(ValueError):
        ImportManifest(
            corpus_id="legal-corpus-fixture",
            corpus_version="fixture-v1",
            compiler_version="0.1.0",
            schema_version="legal-corpus/v1",
            generated_at="2026-07-10T00:00:00Z",
            source_manifest_path="sources/manifest.yaml",
            source_manifest_hash="a" * 64,
            generated_corpus_root=".",
            validation_status="complete",
            sync_eligible=False,
            minimum_gbrain_schema_pack_version="0.1.0",
            confidentiality_scope=["internal"],
            access_scope="compiler_generated_read_only",
            rollback_target=None,
            previous_corpus_version=None,
            compiler_owned_read_only=True,
            files=[],
        )


def test_safe_output_path_accepts_canonical_relative_paths(tmp_path: Path) -> None:
    safe = safe_output_path(
        tmp_path,
        "legal/clauses/bylaws/example-bylaw-1.1.md",
    )

    assert safe == tmp_path / "legal" / "clauses" / "bylaws" / "example-bylaw-1.1.md"


@pytest.mark.parametrize(
    "relative_path",
    ["../outside.md", "/absolute.md", "legal/../outside.md", "legal\\outside.md"],
)
def test_safe_output_path_rejects_escape_attempts(
    tmp_path: Path,
    relative_path: str,
) -> None:
    with pytest.raises(ExportRecordError):
        safe_output_path(tmp_path, relative_path)


def test_write_text_with_hash_returns_exported_file_metadata(tmp_path: Path) -> None:
    exported = write_text_with_hash(
        tmp_path,
        "legal/clauses/bylaws/example-bylaw-1.1.md",
        "fixture text\n",
    )

    expected_path = tmp_path / "legal" / "clauses" / "bylaws" / "example-bylaw-1.1.md"
    assert expected_path.is_file()
    assert exported.path == "legal/clauses/bylaws/example-bylaw-1.1.md"
    assert exported.sha256 == sha256_file(expected_path)
    assert len(exported.sha256) == 64
