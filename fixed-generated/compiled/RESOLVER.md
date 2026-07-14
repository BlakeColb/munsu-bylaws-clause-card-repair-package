---
title: Legal Corpus Resolver
type: corpus_resolver
status: production_readiness
generated_at: '2026-07-14T13:16:34+00:00'
confidentiality: internal
wikilinks:
- schema
- index
---
# Legal Corpus Resolver

## Compiled Truth

This corpus contains compiler-generated legal and governance pages. Exact source text remains authoritative, and generated summaries or hints are retrieval aids only.

## Source Text

Exact source text lives inside each legal clause page under `## Source Text` and in `.raw/provenance/` sidecars. Do not substitute resolver guidance for source clauses.

## Retrieval Hints

- Prefer keyword-first retrieval by clause ID, defined term, instrument title, and parent legal unit.
- Filter by `document_type`, `jurisdiction`, `authority_rank`, `status`, `effective_date`, and `confidentiality` before ranking answer candidates.
- Retrieve `legal_clause` pages with their parent chain, definitions, exceptions, cross-references, and authority relationships.

## Mycroft Legal Retrieval Contract

For legal or governance queries, Mycroft must search only the approved legal corpus by `jurisdiction`, `document_type`, `authority_rank`, `status`, and `effective_date` before answering.

Mycroft must retrieve the exact clause plus parent context, then retrieve definitions, exceptions, cross-references, and higher-authority relationships before composing an answer.

Mycroft must verify `validation_status: passed` and the current corpus version before presenting the result as usable. If either check fails, answer with the validation problem and do not provide a legal conclusion.

Every answer must be source-grounded and informational. It must include citation/clause ID, source version and effective date, key exception or uncertainty, and an escalation boundary for interpretation or legal advice.

Hindsight may retain only operational follow-up such as verifying policy version, preparing a draft, or seeking professional advice. Hindsight must store no durable legal conclusions.

## Production Gate

The future production path is `gbrain sync --repo <compiled-corpus>` followed by `gbrain embed --stale`, but production sync is blocked until external Mycroft/GBrain gates pass for reliability, read-only permissions, backup/restore, and traceability.

- Source manifest hash: `ea54114c5be3112241167f5e24aa1b6fba9482070560eff96acc4e7fefd23017`.
- Documents covered: 1.
