---
title: Legal Corpus Index
type: corpus_index
status: production_readiness
generated_at: '2026-07-14T00:07:10+00:00'
confidentiality: internal
wikilinks:
- RESOLVER
- schema
---
# Legal Corpus Index

## Compiled Truth

This index summarizes the generated corpus for operators and retrieval systems. It is not legal advice and does not replace exact source text.

## Source Text

Open each clause page and inspect `## Source Text` plus `.raw/provenance/` before relying on a legal answer.

## Retrieval Hints

- Start with instrument and clause filters, then inspect parent context and definitions.
- Use `document_type`, `jurisdiction`, `authority_rank`, `status`, `effective_date`, and `confidentiality` as filter metadata.

## Documents

- `munsu-bylaws`: MUNSU Bylaws (`bylaw`, authority rank `40`, status `active`).

## Mycroft Legal Retrieval Contract

Mycroft must use the resolver contract before answering legal/governance questions and must include citation/clause ID, source version and effective date, key exception or uncertainty, and an escalation boundary.

Hindsight may retain only operational follow-up and no durable legal conclusions.

## Production Path

Keyword-first local use is allowed after local validation passes. Future publication should run `gbrain sync --repo <compiled-corpus>` and then `gbrain embed --stale` only after external gates pass.

Production sync is blocked until external Mycroft/GBrain gates pass for reliability, read-only permissions, backup/restore, and traceability.

- Source manifest hash: `ea54114c5be3112241167f5e24aa1b6fba9482070560eff96acc4e7fefd23017`.
- Schema-pack suggestion: `.raw/schema-pack/legal-corpus-pack.yaml`.
