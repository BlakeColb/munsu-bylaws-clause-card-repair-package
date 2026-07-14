from __future__ import annotations

from pathlib import Path

import yaml

from legal_corpus.compiler import compile_sources
from legal_corpus.export_records import ImportManifest
from legal_corpus.frontmatter import parse_frontmatter
from legal_corpus.scaffold import create_scaffold


def compiled_output(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled"
    create_scaffold(workspace)
    compile_sources(workspace, output)
    return output


def test_compile_generates_production_readiness_docs(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    expected_types = {
        "RESOLVER.md": "corpus_resolver",
        "schema.md": "corpus_schema",
        "index.md": "corpus_index",
    }

    for relative_path, page_type in expected_types.items():
        path = output / relative_path
        assert path.is_file(), relative_path
        frontmatter = parse_frontmatter(path)
        assert frontmatter["type"] == page_type
        assert frontmatter["status"] == "production_readiness"
        assert frontmatter["confidentiality"] == "internal"
        assert isinstance(frontmatter["wikilinks"], list)

    schema_pack = output / ".raw" / "schema-pack" / "legal-corpus-pack.yaml"
    assert schema_pack.is_file()
    parsed = yaml.safe_load(schema_pack.read_text(encoding="utf-8"))
    assert parsed["api_version"] == "gbrain-schema-pack-v1"
    assert parsed["name"] == "legal-corpus"
    assert parsed["version"] == "0.1.0"
    assert parsed["gbrain_min_version"] == "0.39.0"


def test_schema_docs_name_legal_types_links_and_embedding_targets(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    schema_text = (output / "schema.md").read_text(encoding="utf-8")
    all_docs = "\n".join(
        (output / name).read_text(encoding="utf-8")
        for name in ("RESOLVER.md", "schema.md", "index.md")
    )

    for value in (
        "legal_instrument",
        "legal_clause",
        "legal_definition",
        "unresolved_reference",
        "child_of",
        "parent_of",
        "defines",
        "uses_definition",
        "read_with",
        "exception_to",
        "supersedes",
        "higher_authority_than",
    ):
        assert value in schema_text

    for value in (
        "## Source Text",
        "## Compiled Truth",
        "## Retrieval Hints",
        "document_type",
        "jurisdiction",
        "authority_rank",
        "status",
        "effective_date",
        "confidentiality",
    ):
        assert value in all_docs


def test_production_notes_keep_sync_blocked_and_manifest_tracked(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    docs_text = "\n".join(
        (output / name).read_text(encoding="utf-8")
        for name in ("RESOLVER.md", "schema.md", "index.md")
    )
    manifest = ImportManifest.model_validate(
        yaml.safe_load((output / "import-manifest.yaml").read_text(encoding="utf-8"))
    )
    files_by_path = {file.path: file for file in manifest.files}

    assert "gbrain sync --repo <compiled-corpus>" in docs_text
    assert "gbrain embed --stale" in docs_text
    assert "production sync is blocked until external Mycroft/GBrain gates pass" in docs_text
    assert "gbrain schema validate" in docs_text
    assert "schema-pack suggestion requires human review before activation" in docs_text
    assert manifest.sync_eligible is False

    for relative_path in (
        "RESOLVER.md",
        "schema.md",
        "index.md",
        ".raw/schema-pack/legal-corpus-pack.yaml",
    ):
        assert relative_path in files_by_path
        assert len(files_by_path[relative_path].sha256) == 64

    assert files_by_path["RESOLVER.md"].sync_eligible is True
    assert files_by_path["schema.md"].sync_eligible is True
    assert files_by_path["index.md"].sync_eligible is True
    assert files_by_path[".raw/schema-pack/legal-corpus-pack.yaml"].sync_eligible is False
