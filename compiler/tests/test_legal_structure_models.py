from pathlib import Path

import pytest
from pydantic import ValidationError

from legal_corpus.source_records import SourceAnchor
from legal_corpus.structure_records import (
    DefinitionRecord,
    LegalStructure,
    LegalUnit,
    ReferenceRecord,
    StructureRecordError,
)


def instrument_unit() -> LegalUnit:
    return LegalUnit(
        clause_id="example-bylaw",
        slug="example-bylaw",
        unit_type="instrument",
        title="Example Student Association Bylaw",
        text="Example Student Association Bylaw",
        anchor=SourceAnchor(line_start=1, line_end=1),
        is_top_level=True,
    )


def clause_unit() -> LegalUnit:
    return LegalUnit(
        clause_id="example-bylaw-1.1",
        slug="example-bylaw-1.1",
        unit_type="clause",
        number="1.1",
        text="1.1 The Association must keep a list of recognized members.",
        anchor=SourceAnchor(line_start=5, line_end=5),
        parent_clause_id="example-bylaw",
        parent_chain=["example-bylaw"],
        source_block_id="example-bylaw-L5-L9",
    )


def structure_with(units: list[LegalUnit]) -> LegalStructure:
    return LegalStructure(
        instrument_slug="example-bylaw",
        instrument_title="Example Student Association Bylaw",
        document_type="bylaw",
        source_path="tests/fixtures/sources/example-bylaw.md",
        source_hash="fakehash",
        units=units,
        definitions=[
            DefinitionRecord(
                term="Recognized member",
                slug="recognized-member",
                instrument_slug="example-bylaw",
                source_unit_id="example-bylaw-1.2",
                definition_text='"Recognized member" means a student listed in the current member register.',
                anchor=SourceAnchor(line_start=7, line_end=7),
            )
        ],
        references=[
            ReferenceRecord(
                reference_id="example-bylaw-1.3-read_with-1",
                reference_type="read_with",
                source_unit_id="example-bylaw-1.3",
                reference_text="Example Budget Notice Policy",
                anchor=SourceAnchor(line_start=9, line_end=9),
                resolution_status="resolved",
                resolved_target_slug="example-policy",
            )
        ],
    )


def test_legal_structure_serializes_units_definitions_references_and_source_hash() -> None:
    structure = structure_with([instrument_unit(), clause_unit()])

    dumped = structure.model_dump(mode="json")

    assert dumped["instrument_slug"] == "example-bylaw"
    assert dumped["source_hash"] == "fakehash"
    assert dumped["units"][1]["clause_id"] == "example-bylaw-1.1"
    assert dumped["definitions"][0]["slug"] == "recognized-member"
    assert dumped["references"][0]["reference_type"] == "read_with"


def test_legal_structure_rejects_duplicate_clause_ids() -> None:
    duplicate = clause_unit().model_copy()

    with pytest.raises(ValidationError):
        structure_with([instrument_unit(), clause_unit(), duplicate])


def test_legal_structure_rejects_child_without_parent() -> None:
    orphan = clause_unit().model_copy(update={"parent_clause_id": None, "parent_chain": []})

    with pytest.raises(ValidationError):
        structure_with([instrument_unit(), orphan])


def test_legal_structure_rejects_parent_id_that_does_not_exist() -> None:
    orphan = clause_unit().model_copy(
        update={"parent_clause_id": "example-bylaw-missing", "parent_chain": ["example-bylaw-missing"]}
    )

    with pytest.raises(ValidationError):
        structure_with([instrument_unit(), orphan])


def test_structure_sidecar_writes_under_raw_extraction(tmp_path: Path) -> None:
    structure = structure_with([instrument_unit(), clause_unit()])

    written = structure.write_sidecar(tmp_path)

    expected = tmp_path / ".raw" / "extraction" / "example-bylaw.structure.json"
    assert written.structure_path == expected
    assert expected.is_file()


def test_structure_sidecar_rejects_unsafe_slug(tmp_path: Path) -> None:
    structure = structure_with([instrument_unit()]).model_copy(
        update={"instrument_slug": "../outside"}
    )

    with pytest.raises(StructureRecordError):
        structure.write_sidecar(tmp_path)
