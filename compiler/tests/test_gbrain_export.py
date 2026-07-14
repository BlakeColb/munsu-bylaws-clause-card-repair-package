from pathlib import Path

import yaml

from legal_corpus.exporters.gbrain import export_gbrain_corpus
from legal_corpus.extractors.markdown import extract_markdown
from legal_corpus.frontmatter import parse_frontmatter
from legal_corpus.manifest import ManifestDocument
from legal_corpus.parsers.legal_structure import parse_legal_structure
from legal_corpus.structure_records import LegalStructure


FIXTURE_ROOT = Path("tests/fixtures/sources")


def manifest_document(
    *,
    slug: str,
    document_type: str,
    title: str,
    source_path: str,
    authority_rank: int,
    confidentiality: str = "internal",
) -> ManifestDocument:
    return ManifestDocument.model_validate(
        {
            "source_path": source_path,
            "document_type": document_type,
            "title": title,
            "slug": slug,
            "jurisdiction": "fictional",
            "authority_rank": authority_rank,
            "status": "active",
            "confidentiality": confidentiality,
            "effective_date": None,
            "owner": "Legal Corpus Compiler fixtures",
            "version": "fixture-v1",
            "reviewed_by": None,
            "metadata_notes": [
                "effective_date is null because this is an invented contract fixture.",
                "reviewed_by is null because no legal review applies to fictional fixtures.",
            ],
        }
    )


def example_documents() -> list[ManifestDocument]:
    return [
        manifest_document(
            slug="example-bylaw",
            document_type="bylaw",
            title="Example Student Association Bylaw",
            source_path="tests/fixtures/sources/example-bylaw.md",
            authority_rank=40,
        ),
        manifest_document(
            slug="example-policy",
            document_type="policy",
            title="Example Budget Notice Policy",
            source_path="tests/fixtures/sources/example-policy.md",
            authority_rank=30,
        ),
        manifest_document(
            slug="example-collective-agreement",
            document_type="collective_agreement",
            title="Example Staff Collective Agreement",
            source_path="tests/fixtures/sources/example-collective-agreement.md",
            authority_rank=50,
            confidentiality="restricted",
        ),
        manifest_document(
            slug="example-legislation",
            document_type="legislation",
            title="Example Campus Safety Act",
            source_path="tests/fixtures/sources/example-legislation.md",
            authority_rank=90,
            confidentiality="public",
        ),
    ]


def build_export_records() -> tuple[list[ManifestDocument], list, list[LegalStructure]]:
    documents = example_documents()
    extractions = []
    structures = []
    for document in documents:
        extraction = extract_markdown(
            FIXTURE_ROOT / Path(document.source_path).name,
            slug=document.slug,
            source_path=document.source_path,
            title=document.title,
        )
        extractions.append(extraction)
        structures.append(
            parse_legal_structure(
                extraction,
                document,
                known_documents=documents,
            )
        )
    return documents, extractions, structures


def run_export(tmp_path: Path):
    documents, extractions, structures = build_export_records()
    result = export_gbrain_corpus(
        tmp_path,
        documents=documents,
        extractions=extractions,
        structures=structures,
        source_manifest_hash="f" * 64,
        generated_at="2026-07-10T00:00:00Z",
    )
    return result


def test_export_renders_instrument_and_clause_pages_with_parseable_frontmatter(
    tmp_path: Path,
) -> None:
    result = run_export(tmp_path)

    instrument = tmp_path / "legal" / "instruments" / "bylaws" / "example-bylaw.md"
    clause = tmp_path / "legal" / "clauses" / "bylaws" / "example-bylaw-1.1.md"

    assert instrument.is_file()
    assert clause.is_file()
    assert "legal/instruments/bylaws/example-bylaw.md" in [
        path.as_posix() for path in result.markdown_paths
    ]

    instrument_frontmatter = parse_frontmatter(instrument)
    clause_frontmatter = parse_frontmatter(clause)
    assert instrument_frontmatter["type"] == "legal_instrument"
    assert clause_frontmatter["type"] == "legal_clause"
    assert clause_frontmatter["clause_id"] == "example-bylaw-1.1"
    assert clause_frontmatter["instrument_slug"] == "example-bylaw"
    assert clause_frontmatter["parent_chain"] == [
        "example-bylaw",
        "example-bylaw-section-1",
    ]


def test_clause_page_separates_exact_source_text_from_generated_aids(
    tmp_path: Path,
) -> None:
    run_export(tmp_path)

    clause = tmp_path / "legal" / "clauses" / "bylaws" / "example-bylaw-1.1.md"
    body = clause.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(clause)

    assert "## Compiled Truth" in body
    assert "## Source Text" in body
    assert "## Retrieval Hints" in body
    assert "1.1 The Association must keep a list of recognized members." in body
    assert body.index("## Compiled Truth") < body.index("## Source Text")
    assert body.index("## Source Text") < body.index("## Legal Context")
    assert frontmatter["duty_holder"] in ("unknown", None)
    assert frontmatter["deadline"] in ("unknown", None)
    assert frontmatter["remedy"] in ("unknown", None)
    assert "example-bylaw-section-1" in frontmatter["wikilinks"]
    assert "[[example-bylaw-section-1]]" in body


def test_export_renders_definition_and_reference_metadata(tmp_path: Path) -> None:
    run_export(tmp_path)

    definition = tmp_path / "legal" / "definitions" / "recognized-member.md"
    bylaw_reference_clause = (
        tmp_path / "legal" / "clauses" / "bylaws" / "example-bylaw-1.3.md"
    )
    unresolved = (
        tmp_path
        / "legal"
        / "unresolved-references"
        / "example-legislation-7.2-higher-authority-than-1.md"
    )

    assert definition.is_file()
    assert bylaw_reference_clause.is_file()
    assert unresolved.is_file()

    definition_frontmatter = parse_frontmatter(definition)
    clause_frontmatter = parse_frontmatter(bylaw_reference_clause)
    unresolved_frontmatter = parse_frontmatter(unresolved)

    assert definition_frontmatter["term"] == "Recognized member"
    assert definition_frontmatter["instrument_slug"] == "example-bylaw"
    assert definition_frontmatter["source_clause"] == "example-bylaw-1.2"
    assert clause_frontmatter["read_with"] == ["example-policy"]
    assert "example-policy" in clause_frontmatter["wikilinks"]
    assert "[[example-policy]]" in bylaw_reference_clause.read_text(encoding="utf-8")
    assert unresolved_frontmatter["resolution_status"] == "unresolved"
    assert "example-legislation-7.2" in unresolved_frontmatter["wikilinks"]
    assert "[[example-legislation-7.2]]" in unresolved.read_text(encoding="utf-8")


def test_export_writes_provenance_sidecars_and_import_manifest(tmp_path: Path) -> None:
    result = run_export(tmp_path)

    provenance = tmp_path / ".raw" / "provenance" / "example-bylaw-1.1.json"
    manifest_path = tmp_path / "import-manifest.yaml"

    assert provenance.is_file()
    assert manifest_path.is_file()
    assert provenance in result.provenance_paths
    assert result.import_manifest_path == manifest_path

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest["validation_status"] == "pending"
    assert manifest["compiler_owned_read_only"] is True
    assert "RESOLVER.md" in [path.as_posix() for path in result.markdown_paths]
    assert "schema.md" in [path.as_posix() for path in result.markdown_paths]
    assert "index.md" in [path.as_posix() for path in result.markdown_paths]
    clause_entry = next(
        file
        for file in manifest["files"]
        if file["path"] == "legal/clauses/bylaws/example-bylaw-1.1.md"
    )
    raw_entry = next(
        file
        for file in manifest["files"]
        if file["path"] == ".raw/provenance/example-bylaw-1.1.json"
    )
    schema_pack_entry = next(
        file
        for file in manifest["files"]
        if file["path"] == ".raw/schema-pack/legal-corpus-pack.yaml"
    )
    assert len(clause_entry["sha256"]) == 64
    assert raw_entry["sync_eligible"] is False
    assert schema_pack_entry["sync_eligible"] is False
    assert manifest["minimum_gbrain_schema_pack_version"]
