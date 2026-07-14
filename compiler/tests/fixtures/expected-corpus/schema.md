---
title: "Legal Corpus Schema"
type: corpus_schema
status: "phase_1_contract"
---
# Legal Corpus Schema

## Page Types

- legal_instrument
- legal_clause
- legal_definition
- unresolved_reference

## Link Verbs

- child_of
- parent_of
- defines
- uses_definition
- read_with
- exception_to
- supersedes
- higher_authority_than

## Manifest Fields

Every source manifest document requires source_path, document_type, title, slug,
jurisdiction, authority_rank, status, confidentiality, effective_date, owner,
version, reviewed_by, and metadata_notes.

Nullable legal metadata uses YAML null and must be explained in metadata_notes.
Unresolved references are explicit corpus pages, not silent parser failures.

