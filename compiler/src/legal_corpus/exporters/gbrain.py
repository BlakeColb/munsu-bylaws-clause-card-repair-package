"""Deterministic GBrain Markdown exporter."""

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Sequence

import yaml

from legal_corpus.export_records import (
    ExportWriteResult,
    ImportManifest,
    safe_output_path,
    write_text_with_hash,
)
from legal_corpus.manifest import ManifestDocument
from legal_corpus.production_docs import (
    render_production_documents,
    render_schema_pack_suggestion,
)
from legal_corpus.source_records import SourceExtraction
from legal_corpus.structure_records import (
    DefinitionRecord,
    LegalStructure,
    LegalUnit,
    ReferenceRecord,
)


DOCUMENT_FOLDERS = {
    "bylaw": "bylaws",
    "policy": "policies",
    "collective_agreement": "collective-agreements",
    "legislation": "legislation",
}

DERIVED_UNKNOWN_FIELDS = [
    "duty_holder",
    "beneficiary",
    "obligation",
    "permission",
    "prohibition",
    "trigger",
    "deadline",
    "remedy",
    "evidence_requirement",
]


def export_gbrain_corpus(
    output_root: Path,
    *,
    documents: Sequence[ManifestDocument],
    extractions: Sequence[SourceExtraction],
    structures: Sequence[LegalStructure],
    source_manifest_path: str = "sources/manifest.yaml",
    source_manifest_hash: str | None = None,
    generated_at: str | None = None,
) -> ExportWriteResult:
    """Write a GBrain-ready corpus to output_root."""
    generated_at = generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    source_manifest_hash = source_manifest_hash or "0" * 64
    document_by_slug = {document.slug: document for document in documents}
    extraction_by_slug = {extraction.slug: extraction for extraction in extractions}
    corpus_id = _single_document_value(documents, "corpus_id") or "legal-corpus"
    corpus_version = _single_document_value(documents, "corpus_version") or "fixture-v1"
    target_namespace = _single_document_value(documents, "target_namespace")
    sync_eligibility = _single_document_value(documents, "sync_eligibility") or "blocked"
    classification = _single_document_value(documents, "classification")

    markdown_paths: list[Path] = []
    provenance_paths: list[Path] = []
    exported_files = []

    for structure in sorted(structures, key=lambda item: item.instrument_slug):
        document = document_by_slug[structure.instrument_slug]
        extraction = extraction_by_slug[structure.instrument_slug]

        instrument_path = _instrument_path(document)
        instrument_export = write_text_with_hash(
            output_root,
            instrument_path,
            _render_instrument(document, structure, extraction, generated_at),
            file_type="legal_instrument",
            sync_eligible=True,
            source_document_slug=document.slug,
        )
        markdown_paths.append(Path(instrument_path))
        exported_files.append(instrument_export)

        for unit in _context_units(structure):
            context_path = _clause_path(document, unit)
            context_export = write_text_with_hash(
                output_root,
                context_path,
                _render_context_unit(document, structure, unit, generated_at),
                file_type="legal_clause",
                sync_eligible=True,
                source_document_slug=document.slug,
                clause_id=unit.clause_id,
            )
            markdown_paths.append(Path(context_path))
            exported_files.append(context_export)

        for unit in _clause_units(structure):
            clause_path = _clause_path(document, unit)
            clause_export = write_text_with_hash(
                output_root,
                clause_path,
                _render_clause(document, structure, unit, generated_at),
                file_type="legal_clause",
                sync_eligible=True,
                source_document_slug=document.slug,
                clause_id=unit.clause_id,
            )
            markdown_paths.append(Path(clause_path))
            exported_files.append(clause_export)

            provenance_relative = f".raw/provenance/{unit.clause_id}.json"
            provenance_export = write_text_with_hash(
                output_root,
                provenance_relative,
                _provenance_json(
                    document=document,
                    structure=structure,
                    extraction=extraction,
                    generated_page_path=clause_path,
                    source_unit_id=unit.clause_id,
                    source_anchor=unit.anchor.model_dump(mode="json"),
                ),
                file_type="raw_provenance",
                sync_eligible=False,
                source_document_slug=document.slug,
                clause_id=unit.clause_id,
            )
            exported_files.append(provenance_export)
            provenance_paths.append(safe_output_path(output_root, provenance_relative))

        for definition in sorted(structure.definitions, key=lambda item: item.slug):
            definition_path = _definition_path(definition)
            definition_export = write_text_with_hash(
                output_root,
                definition_path,
                _render_definition(document, definition, generated_at),
                file_type="legal_definition",
                sync_eligible=True,
                source_document_slug=document.slug,
                clause_id=definition.source_unit_id,
            )
            markdown_paths.append(Path(definition_path))
            exported_files.append(definition_export)

        unresolved = [
            reference
            for reference in structure.references
            if reference.resolution_status == "unresolved"
        ]
        for reference in sorted(unresolved, key=lambda item: item.reference_id):
            unresolved_path = _unresolved_reference_path(reference)
            unresolved_export = write_text_with_hash(
                output_root,
                unresolved_path,
                _render_unresolved_reference(document, reference, generated_at),
                file_type="unresolved_reference",
                sync_eligible=True,
                source_document_slug=document.slug,
                clause_id=reference.source_unit_id,
            )
            markdown_paths.append(Path(unresolved_path))
            exported_files.append(unresolved_export)

    for production_path, production_content in render_production_documents(
        documents,
        generated_at=generated_at,
        source_manifest_hash=source_manifest_hash,
    ):
        production_export = write_text_with_hash(
            output_root,
            production_path,
            production_content,
            file_type="generated_file",
            sync_eligible=True,
        )
        markdown_paths.append(Path(production_path))
        exported_files.append(production_export)

    schema_pack_path = ".raw/schema-pack/legal-corpus-pack.yaml"
    schema_pack_export = write_text_with_hash(
        output_root,
        schema_pack_path,
        render_schema_pack_suggestion(),
        file_type="generated_file",
        sync_eligible=False,
    )
    exported_files.append(schema_pack_export)

    manifest = ImportManifest(
        corpus_id=corpus_id,
        corpus_version=corpus_version,
        compiler_version="0.1.0",
        schema_version="legal-corpus/v1",
        generated_at=generated_at,
        source_manifest_path=source_manifest_path,
        source_manifest_hash=source_manifest_hash,
        generated_corpus_root=".",
        validation_status="pending",
        sync_eligible=sync_eligibility in {"production_pilot", "production_batch"},
        sync_eligibility=sync_eligibility,
        target_namespace=target_namespace,
        operator_approval_required=True,
        classification=classification,
        minimum_gbrain_schema_pack_version="0.1.0",
        confidentiality_scope=sorted({document.confidentiality for document in documents}),
        access_scope="compiler_generated_read_only",
        rollback_target=None,
        previous_corpus_version=None,
        compiler_owned_read_only=True,
        files=exported_files,
    )
    manifest_path = safe_output_path(output_root, "import-manifest.yaml")
    manifest_path.write_text(
        yaml.safe_dump(
            manifest.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )

    return ExportWriteResult(
        markdown_paths=markdown_paths,
        provenance_paths=provenance_paths,
        import_manifest_path=manifest_path,
        files=exported_files,
        manifest=manifest,
    )


def _render_instrument(
    document: ManifestDocument,
    structure: LegalStructure,
    extraction: SourceExtraction,
    generated_at: str | None,
) -> str:
    child_clause_ids = [unit.clause_id for unit in _clause_units(structure)]
    context_ids = [unit.clause_id for unit in _context_units(structure)]
    frontmatter = {
        "title": document.title,
        "type": "legal_instrument",
        "instrument_slug": document.slug,
        "document_type": document.document_type,
        "jurisdiction": document.jurisdiction,
        "authority_rank": document.authority_rank,
        "status": document.status,
        "effective_date": document.effective_date,
        "confidentiality": document.confidentiality,
        "owner": document.owner,
        "version": document.version,
        "reviewed_by": document.reviewed_by,
        "source_path": document.source_path,
        "source_uri_or_path": document.source_path,
        "source_hash": extraction.source_hash,
        "generated_at": generated_at,
        "generated_by": "legal-corpus-compiler",
        "classification": document.classification,
        "validation_status": "pending",
        "sync_eligibility": document.sync_eligibility,
        "target_namespace": document.target_namespace,
        "read_only": True,
        "review_date": document.review_date,
        "child_clauses": child_clause_ids,
        "wikilinks": _ordered_unique([*context_ids, *child_clause_ids]),
    }
    body = [
        f"# {document.title}",
        "",
        "## Compiled Truth",
        "",
        "This generated instrument page groups legal units parsed from the source document.",
        "",
        "## Source Text",
        "",
        f"See `.raw/sources/{document.slug}{Path(document.source_path).suffix.lower()}`.",
        "",
        "## Legal Context",
        "",
        f"- Document type: `{document.document_type}`.",
        f"- Child clauses: {', '.join(child_clause_ids) if child_clause_ids else 'none'}.",
    ]
    return _markdown(frontmatter, body)


def _render_context_unit(
    document: ManifestDocument,
    structure: LegalStructure,
    unit: LegalUnit,
    generated_at: str | None,
) -> str:
    children = [
        child.clause_id
        for child in structure.units
        if child.parent_clause_id == unit.clause_id and child.unit_type != "instrument"
    ]
    wikilinks = _ordered_unique([document.slug, *unit.parent_chain, *children])
    frontmatter = {
        "title": _clause_title(document, unit),
        "type": "legal_clause",
        "unit_type": unit.unit_type,
        "clause_id": unit.clause_id,
        "slug": unit.slug,
        "instrument_slug": document.slug,
        "instrument_title": document.title,
        "document_type": document.document_type,
        "jurisdiction": document.jurisdiction,
        "authority_rank": document.authority_rank,
        "status": document.status,
        "effective_date": document.effective_date,
        "confidentiality": document.confidentiality,
        "source_path": document.source_path,
        "source_uri_or_path": document.source_path,
        "source_hash": structure.source_hash,
        "source_page_start": unit.anchor.page,
        "source_page_end": unit.anchor.page,
        "source_line_start": unit.anchor.line_start,
        "source_line_end": unit.anchor.line_end,
        "source_block_id": unit.source_block_id,
        "generated_at": generated_at,
        "generated_by": "legal-corpus-compiler",
        "classification": document.classification,
        "validation_status": "pending",
        "sync_eligibility": document.sync_eligibility,
        "target_namespace": document.target_namespace,
        "read_only": True,
        "review_date": document.review_date,
        "parent_clause": unit.parent_clause_id,
        "parent_chain": unit.parent_chain,
        "child_clauses": children,
        "definitions": [],
        "read_with": [],
        "subject_to": [],
        "despite": [],
        "exceptions": [],
        "amends": [],
        "supersedes": [],
        "higher_authority_than": [],
        "unresolved_references": [],
        "wikilinks": wikilinks,
    }
    frontmatter.update({field: "unknown" for field in DERIVED_UNKNOWN_FIELDS})
    frontmatter.update(unit.metadata)
    body = [
        f"# {_clause_title(document, unit)}",
        "",
        "## Compiled Truth",
        "",
        "Generated aid: this page preserves parent context for child legal clauses. Exact source text remains authoritative.",
        "",
        "## Source Text",
        "",
        unit.text,
        "",
        "## Legal Context",
        "",
        f"- Instrument: {_wikilink(document.slug)}.",
        f"- Parent chain: {_wikilink_list(unit.parent_chain) if unit.parent_chain else 'top level'}.",
        f"- Child clauses: {_wikilink_list(children)}.",
        "",
        "## Retrieval Hints",
        "",
        f"- Query by parent context `{unit.clause_id}` and instrument `{document.slug}`.",
    ]
    return _markdown(frontmatter, body)


def _render_clause(
    document: ManifestDocument,
    structure: LegalStructure,
    unit: LegalUnit,
    generated_at: str | None,
) -> str:
    references = [ref for ref in structure.references if ref.source_unit_id == unit.clause_id]
    children = [
        child.clause_id
        for child in structure.units
        if child.parent_clause_id == unit.clause_id
    ]
    definitions = [
        definition.slug
        for definition in structure.definitions
        if definition.source_unit_id == unit.clause_id
    ]
    read_with = _resolved_reference_slugs(references, "read_with")
    subject_to = _resolved_reference_slugs(references, "subject_to")
    despite = _resolved_reference_slugs(references, "despite")
    exceptions = _resolved_reference_slugs(references, "exception_to")
    amends = _resolved_reference_slugs(references, "amends")
    supersedes = _resolved_reference_slugs(references, "supersedes")
    higher_authority_than = _resolved_reference_slugs(
        references,
        "higher_authority_than",
    )
    unresolved = [
        _reference_page_slug(reference)
        for reference in references
        if reference.resolution_status == "unresolved"
    ]
    wikilinks = _ordered_unique(
        [
            document.slug,
            *unit.parent_chain,
            *children,
            *definitions,
            *read_with,
            *subject_to,
            *despite,
            *exceptions,
            *amends,
            *supersedes,
            *higher_authority_than,
            *unresolved,
        ]
    )
    frontmatter = {
        "title": _clause_title(document, unit),
        "type": "legal_clause",
        "unit_type": unit.unit_type,
        "clause_id": unit.clause_id,
        "slug": unit.slug,
        "instrument_slug": document.slug,
        "instrument_title": document.title,
        "document_type": document.document_type,
        "jurisdiction": document.jurisdiction,
        "authority_rank": document.authority_rank,
        "status": document.status,
        "effective_date": document.effective_date,
        "confidentiality": document.confidentiality,
        "source_path": document.source_path,
        "source_uri_or_path": document.source_path,
        "source_hash": structure.source_hash,
        "source_page_start": unit.anchor.page,
        "source_page_end": unit.anchor.page,
        "source_line_start": unit.anchor.line_start,
        "source_line_end": unit.anchor.line_end,
        "source_block_id": unit.source_block_id,
        "generated_at": generated_at,
        "generated_by": "legal-corpus-compiler",
        "classification": document.classification,
        "validation_status": "pending",
        "sync_eligibility": document.sync_eligibility,
        "target_namespace": document.target_namespace,
        "read_only": True,
        "review_date": document.review_date,
        "parent_clause": unit.parent_clause_id,
        "parent_chain": unit.parent_chain,
        "child_clauses": children,
        "definitions": definitions,
        "read_with": read_with,
        "subject_to": subject_to,
        "despite": despite,
        "exceptions": exceptions,
        "amends": amends,
        "supersedes": supersedes,
        "higher_authority_than": higher_authority_than,
        "unresolved_references": unresolved,
        "wikilinks": wikilinks,
    }
    frontmatter.update({field: "unknown" for field in DERIVED_UNKNOWN_FIELDS})
    frontmatter.update(unit.metadata)
    body = [
        f"# {_clause_title(document, unit)}",
        "",
        "## Compiled Truth",
        "",
        "Generated aid: this page represents one parsed legal unit. Exact source text remains authoritative.",
        "",
        "## Source Text",
        "",
        unit.text,
        "",
        "## Legal Context",
        "",
        f"- Instrument: {_wikilink(document.slug)}.",
        f"- Parent chain: {_wikilink_list(unit.parent_chain) if unit.parent_chain else 'top level'}.",
        f"- Child clauses: {_wikilink_list(children)}.",
        f"- Definitions defined here: {_wikilink_list(definitions)}.",
        f"- Resolved read-with references: {_wikilink_list(read_with)}.",
        f"- Unresolved references: {_wikilink_list(unresolved)}.",
        "",
        "## Retrieval Hints",
        "",
        f"- Query by clause ID `{unit.clause_id}` and instrument `{document.slug}`.",
    ]
    return _markdown(frontmatter, body)


def _render_definition(
    document: ManifestDocument,
    definition: DefinitionRecord,
    generated_at: str | None,
) -> str:
    frontmatter = {
        "title": definition.term,
        "type": "legal_definition",
        "term": definition.term,
        "slug": definition.slug,
        "instrument_slug": definition.instrument_slug,
        "source_clause": definition.source_unit_id,
        "status": document.status,
        "confidentiality": document.confidentiality,
        "source_line_start": definition.anchor.line_start,
        "source_line_end": definition.anchor.line_end,
        "generated_at": generated_at,
        "generated_by": "legal-corpus-compiler",
        "classification": document.classification,
        "validation_status": "pending",
        "sync_eligibility": document.sync_eligibility,
        "target_namespace": document.target_namespace,
        "read_only": True,
        "review_date": document.review_date,
        "wikilinks": [definition.instrument_slug, definition.source_unit_id],
    }
    body = [
        f"# {definition.term}",
        "",
        "## Source Text",
        "",
        definition.definition_text,
        "",
        "## Legal Context",
        "",
        f"- Instrument: {_wikilink(definition.instrument_slug)}.",
        f"- Defined in {_wikilink(definition.source_unit_id)}.",
    ]
    return _markdown(frontmatter, body)


def _render_unresolved_reference(
    document: ManifestDocument,
    reference: ReferenceRecord,
    generated_at: str | None,
) -> str:
    slug = _reference_page_slug(reference)
    frontmatter = {
        "title": f"Unresolved Reference - {reference.reference_text}",
        "type": "unresolved_reference",
        "slug": slug,
        "source_clause": reference.source_unit_id,
        "reference_type": reference.reference_type,
        "reference_text": reference.reference_text,
        "resolution_status": "unresolved",
        "instrument_slug": document.slug,
        "confidentiality": document.confidentiality,
        "source_line_start": reference.anchor.line_start,
        "source_line_end": reference.anchor.line_end,
        "generated_at": generated_at,
        "generated_by": "legal-corpus-compiler",
        "classification": document.classification,
        "validation_status": "pending",
        "sync_eligibility": document.sync_eligibility,
        "target_namespace": document.target_namespace,
        "read_only": True,
        "review_date": document.review_date,
        "wikilinks": [document.slug, reference.source_unit_id],
    }
    body = [
        f"# Unresolved Reference - {reference.reference_text}",
        "",
        "This generated page keeps an unresolved cross-reference explicit for Phase 5 validation.",
        "",
        "## Source Text",
        "",
        reference.reference_text,
        "",
        "## Legal Context",
        "",
        f"- Instrument: {_wikilink(document.slug)}.",
        f"- Source clause: {_wikilink(reference.source_unit_id)}.",
    ]
    return _markdown(frontmatter, body)


def _markdown(frontmatter: dict, body_lines: list[str]) -> str:
    dumped = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    return "---\n" + dumped + "\n---\n" + "\n".join(body_lines).rstrip() + "\n"


def _instrument_path(document: ManifestDocument) -> str:
    return f"legal/instruments/{_document_folder(document)}/{document.slug}.md"


def _clause_path(document: ManifestDocument, unit: LegalUnit) -> str:
    return f"legal/clauses/{_document_folder(document)}/{unit.slug}.md"


def _definition_path(definition: DefinitionRecord) -> str:
    return f"legal/definitions/{definition.slug}.md"


def _unresolved_reference_path(reference: ReferenceRecord) -> str:
    return f"legal/unresolved-references/{_reference_page_slug(reference)}.md"


def _document_folder(document: ManifestDocument) -> str:
    return DOCUMENT_FOLDERS[document.document_type]


def _single_document_value(
    documents: Sequence[ManifestDocument],
    field_name: str,
) -> str | None:
    values = {
        value
        for document in documents
        for value in [getattr(document, field_name)]
        if value is not None
    }
    if len(values) == 1:
        return str(next(iter(values)))
    return None


def _clause_units(structure: LegalStructure) -> list[LegalUnit]:
    return sorted(
        [unit for unit in structure.units if unit.unit_type == "clause"],
        key=lambda unit: unit.clause_id,
    )


def _context_units(structure: LegalStructure) -> list[LegalUnit]:
    return sorted(
        [
            unit
            for unit in structure.units
            if unit.unit_type not in ("instrument", "clause")
        ],
        key=lambda unit: unit.clause_id,
    )


def _clause_title(document: ManifestDocument, unit: LegalUnit) -> str:
    if unit.title:
        return unit.title
    if unit.number:
        return f"{document.title} {unit.number}"
    return unit.clause_id


def _resolved_reference_slugs(
    references: Sequence[ReferenceRecord],
    reference_type: str,
) -> list[str]:
    values = []
    for reference in references:
        if reference.reference_type != reference_type:
            continue
        if reference.resolution_status != "resolved":
            continue
        values.append(reference.resolved_target_slug or reference.resolved_target_id or reference.reference_text)
    return values


def _reference_page_slug(reference: ReferenceRecord) -> str:
    kind = reference.reference_type.replace("_", "-")
    suffix = reference.reference_id.rsplit("-", 1)[-1]
    if not suffix.isdigit():
        suffix = "1"
    return f"{reference.source_unit_id}-{kind}-{suffix}"


def _wikilink(target: str) -> str:
    return f"[[{target}]]"


def _wikilink_list(targets: Sequence[str]) -> str:
    if not targets:
        return "none"
    return ", ".join(_wikilink(target) for target in targets)


def _ordered_unique(values: Sequence[str | None]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _provenance_json(
    *,
    document: ManifestDocument,
    structure: LegalStructure,
    extraction: SourceExtraction,
    generated_page_path: str,
    source_unit_id: str,
    source_anchor: dict,
) -> str:
    data = {
        "source_document_slug": document.slug,
        "source_path": document.source_path,
        "source_hash": structure.source_hash,
        "source_anchor": source_anchor,
        "generated_page_path": generated_page_path,
        "source_unit_id": source_unit_id,
        "extraction_status": extraction.status,
        "extraction_warnings": [
            warning.model_dump(mode="json") for warning in extraction.warnings
        ],
        "compiler_owned_read_only": True,
    }
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
