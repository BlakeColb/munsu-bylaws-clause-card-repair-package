---
title: Legal Corpus Schema
type: corpus_schema
status: production_readiness
generated_at: '2026-07-14T00:07:10+00:00'
confidentiality: internal
wikilinks:
- RESOLVER
- index
---
# Legal Corpus Schema

## Compiled Truth

This schema guide documents the generated legal page types and link verbs for local validation and future GBrain schema-pack review.

## Source Text

`legal_clause` pages keep exact clause language under `## Source Text`; `## Compiled Truth` and `## Retrieval Hints` are generated aids and must not be treated as source law.

## Page Types

- `legal_instrument`
- `legal_clause`
- `legal_definition`
- `unresolved_reference`

## Link Types

- `child_of`
- `parent_of`
- `defines`
- `uses_definition`
- `read_with`
- `exception_to`
- `supersedes`
- `higher_authority_than`

## Embedding Targets

- Embed `## Source Text` for exact legal language.
- Embed `## Compiled Truth` only as a retrieval aid that points back to source text.
- Embed `## Retrieval Hints` for keyword expansion, clause IDs, and instrument names.
- Use frontmatter filters for `document_type`, `jurisdiction`, `authority_rank`, `status`, `effective_date`, and `confidentiality` before reranking.

## Schema-Pack Suggestion

The reviewable suggestion is `.raw/schema-pack/legal-corpus-pack.yaml`. Run `gbrain schema validate` before use; the schema-pack suggestion requires human review before activation.

The future production path is `gbrain sync --repo <compiled-corpus>` followed by `gbrain embed --stale`, but production sync is blocked until external Mycroft/GBrain gates pass.
