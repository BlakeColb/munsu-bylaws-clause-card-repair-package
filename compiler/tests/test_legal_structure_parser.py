from pathlib import Path

from legal_corpus.extractors.markdown import extract_markdown
from legal_corpus.manifest import ManifestDocument
from legal_corpus.parsers.legal_structure import parse_legal_structure
from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
)


FIXTURE_ROOT = Path("tests/fixtures/sources")


def manifest_document(
    *,
    slug: str,
    document_type: str,
    title: str,
    source_path: str,
    authority_rank: int,
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
            "confidentiality": "internal",
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
        ),
        manifest_document(
            slug="example-legislation",
            document_type="legislation",
            title="Example Campus Safety Act",
            source_path="tests/fixtures/sources/example-legislation.md",
            authority_rank=90,
        ),
    ]


def parse_fixture(
    filename: str,
    document: ManifestDocument,
    *,
    known_documents: list[ManifestDocument] | None = None,
):
    path = FIXTURE_ROOT / filename
    extraction = extract_markdown(
        path,
        slug=document.slug,
        source_path=document.source_path,
        title=document.title,
    )
    return parse_legal_structure(
        extraction,
        document,
        known_documents=known_documents,
    )


def test_bylaw_hierarchy_and_stable_clause_ids_are_deterministic() -> None:
    document = example_documents()[0]

    first = parse_fixture("example-bylaw.md", document)
    second = parse_fixture("example-bylaw.md", document)

    first_ids = [unit.clause_id for unit in first.units]
    assert first_ids == [unit.clause_id for unit in second.units]
    assert "example-bylaw" in first_ids
    assert "example-bylaw-section-1" in first_ids
    assert "example-bylaw-1.1" in first_ids
    assert "example-bylaw-1.2" in first_ids
    assert "example-bylaw-1.3" in first_ids

    clause = next(unit for unit in first.units if unit.clause_id == "example-bylaw-1.1")
    assert clause.parent_clause_id == "example-bylaw-section-1"
    assert clause.parent_chain == ["example-bylaw", "example-bylaw-section-1"]
    assert clause.anchor.line_start == 5
    assert clause.anchor.line_end == 5
    assert "Compiled Truth" not in clause.text
    assert "Retrieval Hints" not in clause.text


def test_fixture_document_types_each_produce_numbered_legal_units() -> None:
    documents = example_documents()
    fixture_names = [
        "example-bylaw.md",
        "example-policy.md",
        "example-collective-agreement.md",
        "example-legislation.md",
    ]

    for filename, document in zip(fixture_names, documents, strict=True):
        structure = parse_fixture(filename, document)
        numbered_units = [unit for unit in structure.units if unit.unit_type == "clause"]
        assert numbered_units, f"{document.slug} produced no numbered legal units"


def test_quoted_definition_is_scoped_to_source_instrument() -> None:
    document = example_documents()[0]
    structure = parse_fixture("example-bylaw.md", document)

    definition = structure.definitions[0]
    assert definition.term == "Recognized member"
    assert definition.slug == "recognized-member"
    assert definition.instrument_slug == "example-bylaw"
    assert definition.source_unit_id == "example-bylaw-1.2"
    assert definition.definition_text == (
        '"Recognized member" means a student listed in the current member register.'
    )


def test_read_with_reference_resolves_with_known_document_metadata() -> None:
    documents = example_documents()
    structure = parse_fixture(
        "example-bylaw.md",
        documents[0],
        known_documents=documents,
    )

    reference = next(ref for ref in structure.references if ref.reference_type == "read_with")
    assert reference.source_unit_id == "example-bylaw-1.3"
    assert reference.reference_text == "Example Budget Notice Policy"
    assert reference.resolution_status == "resolved"
    assert reference.resolved_target_slug == "example-policy"


def test_read_with_reference_stays_explicitly_unresolved_without_metadata() -> None:
    document = example_documents()[0]
    structure = parse_fixture("example-bylaw.md", document)

    reference = next(ref for ref in structure.references if ref.reference_type == "read_with")
    assert reference.reference_text == "Example Budget Notice Policy"
    assert reference.resolution_status == "unresolved"
    assert reference.resolved_target_slug is None


def test_legislation_prevails_over_language_creates_unresolved_authority_reference() -> None:
    document = example_documents()[3]
    structure = parse_fixture("example-legislation.md", document)

    reference = next(
        ref for ref in structure.references if ref.reference_type == "higher_authority_than"
    )
    assert reference.source_unit_id == "example-legislation-7.2"
    assert reference.reference_text == "inconsistent internal room policy"
    assert reference.resolution_status == "unresolved"


def test_subject_to_section_reference_resolves_current_clause_id() -> None:
    document = manifest_document(
        slug="example-resolution",
        document_type="policy",
        title="Example Resolution Procedure",
        source_path="tests/fixtures/sources/example-resolution.md",
        authority_rank=25,
    )
    extraction = SourceExtraction(
        slug=document.slug,
        source_path=document.source_path,
        source_hash="fixture-hash",
        provider="markdown",
        status="ok",
        title=document.title,
        provider_metadata=ProviderMetadata(provider="markdown"),
        warnings=[],
        blocks=[
            SourceBlock(
                block_id="example-resolution-L1-L1",
                block_type="heading",
                text="## Section 1 - Procedure",
                anchor=SourceAnchor(line_start=1, line_end=1),
                heading_path=["Section 1 - Procedure"],
            ),
            SourceBlock(
                block_id="example-resolution-L3-L3",
                block_type="body",
                text="1.1 A notice must identify the affected committee.",
                anchor=SourceAnchor(line_start=3, line_end=3),
                heading_path=["Section 1 - Procedure"],
            ),
            SourceBlock(
                block_id="example-resolution-L5-L5",
                block_type="body",
                text="1.2 The chair may revise a notice subject to section 1.1.",
                anchor=SourceAnchor(line_start=5, line_end=5),
                heading_path=["Section 1 - Procedure"],
            ),
        ],
    )

    structure = parse_legal_structure(extraction, document)

    reference = next(ref for ref in structure.references if ref.reference_type == "subject_to")
    assert reference.source_unit_id == "example-resolution-1.2"
    assert reference.reference_text == "1.1"
    assert reference.resolution_status == "resolved"
    assert reference.resolved_target_id == "example-resolution-1.1"
    assert reference.resolved_target_slug is None
