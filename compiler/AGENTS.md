# AGENTS.md

## Project

Legal Corpus Compiler builds a CLI pipeline that turns PDF and Markdown legal documents into a ready-to-sync GBrain corpus of enriched Markdown files.

## Source of Truth

Before planning or editing, read:

1. `.planning/PROJECT.md`
2. `.planning/REQUIREMENTS.md`
3. `.planning/ROADMAP.md`
4. `.planning/STATE.md`
5. `.planning/research/SUMMARY.md`

## Working Rules

- Preserve legal hierarchy before optimizing for retrieval.
- Chunk by legal unit, not arbitrary token windows.
- Keep exact source text separate from generated summaries.
- Treat source provenance as mandatory.
- Prefer deterministic parsing before LLM enrichment.
- Make keyword-first output work, but keep the corpus embedding-ready.
- Do not broaden scope into general Student Union memory ingestion unless the roadmap is updated.

## GSD Workflow

- Use `$gsd-discuss-phase 1` before implementation.
- Use `$gsd-plan-phase N` before executing a phase.
- Use `$gsd-verify-work` or the phase verifier before marking work complete.
- Update `.planning/STATE.md` as phase status changes.

## Verification Priorities

- YAML frontmatter parses.
- Clause IDs and slugs are unique.
- Parent/child links resolve.
- Cross-references are either resolved or explicitly unresolved.
- Gold legal questions retrieve expected clauses, parent context, and definitions.
