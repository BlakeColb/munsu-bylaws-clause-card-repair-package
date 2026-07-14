from pathlib import Path

import yaml

from legal_corpus.compiler import compile_sources
from legal_corpus.frontmatter import parse_frontmatter
from legal_corpus.scaffold import create_scaffold


def test_compile_sources_writes_gbrain_export_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled-corpus"
    create_scaffold(workspace)

    result = compile_sources(workspace, output)

    instrument = output / "legal" / "instruments" / "bylaws" / "example-bylaw.md"
    parent_context = output / "legal" / "clauses" / "bylaws" / "example-bylaw-section-1.md"
    clause = output / "legal" / "clauses" / "bylaws" / "example-bylaw-1.1.md"
    definition = output / "legal" / "definitions" / "recognized-member.md"
    unresolved = (
        output
        / "legal"
        / "unresolved-references"
        / "example-legislation-7.2-higher-authority-than-1.md"
    )
    resolver = output / "RESOLVER.md"
    schema = output / "schema.md"
    index = output / "index.md"
    schema_pack = output / ".raw" / "schema-pack" / "legal-corpus-pack.yaml"
    provenance = output / ".raw" / "provenance" / "example-bylaw-1.1.json"
    import_manifest = output / "import-manifest.yaml"

    for path in [
        instrument,
        parent_context,
        clause,
        definition,
        unresolved,
        resolver,
        schema,
        index,
        schema_pack,
        provenance,
        import_manifest,
    ]:
        assert path.is_file(), path

    parent_frontmatter = parse_frontmatter(parent_context)
    clause_frontmatter = parse_frontmatter(clause)
    assert parent_frontmatter["type"] == "legal_clause"
    assert parent_frontmatter["unit_type"] == "section"
    assert "example-bylaw-1.1" in parent_frontmatter["child_clauses"]
    assert clause_frontmatter["type"] == "legal_clause"
    assert clause_frontmatter["clause_id"] == "example-bylaw-1.1"

    assert output / ".raw" / "extraction" / "example-bylaw.json" in result.extraction_paths
    assert (output / ".raw" / "extraction" / "example-bylaw.md").is_file()
    assert (output / ".raw" / "extraction" / "example-bylaw.structure.json").is_file()
    assert (output / ".raw" / "sources" / "example-bylaw.md").is_file()

    assert clause in result.export_paths
    assert resolver in result.export_paths
    assert schema in result.export_paths
    assert index in result.export_paths
    assert provenance in result.provenance_paths
    assert result.import_manifest_path == import_manifest
    assert result.generated_file_count >= 6


def test_compile_sources_writes_hash_indexed_import_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled-corpus"
    create_scaffold(workspace)

    compile_sources(workspace, output)

    manifest = yaml.safe_load((output / "import-manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["source_manifest_path"] == "sources/manifest.yaml"
    assert len(manifest["source_manifest_hash"]) == 64
    assert manifest["validation_status"] == "pending"
    assert manifest["sync_eligible"] is False
    assert manifest["compiler_owned_read_only"] is True
    assert any(
        file["path"] == "legal/clauses/bylaws/example-bylaw-1.1.md"
        and len(file["sha256"]) == 64
        for file in manifest["files"]
    )
    assert any(
        file["path"] == ".raw/schema-pack/legal-corpus-pack.yaml"
        and file["sync_eligible"] is False
        and len(file["sha256"]) == 64
        for file in manifest["files"]
    )
