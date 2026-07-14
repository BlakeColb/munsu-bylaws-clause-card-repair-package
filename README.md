# MUNSU Bylaws Clause Card Repair Package

This repository is a self-contained context package for repairing generated Clause Cards for a public MUNSU Bylaws corpus.

It exists so an external coding agent can work without access to Blake's local machine.

## Repair Status (2026-07-14)

The repair described in `CLAUDE_FABLE_5_FIX_PROMPT.md` has been executed.

- **`fixed-generated/compiled/` is the corrected corpus** (346 Clause Cards). Its re-audit reports zero P0 and zero P1 findings; the only remaining rows are the eight accurately carried unresolved-reference warnings (P2 metadata).
- **`current-generated/compiled/` is superseded and unsafe to import.** It is retained only as the review baseline that the original findings refer to. Do not import cards from it.
- `fixed-generated/old-to-new-card-id-map.csv` maps every old card ID to its repaired or replacement ID and lists the 23 new structural cards (Part I Section I plus Part II Sections 1-22).
- `fixed-generated/review-packet/` holds the regenerated warning register derived from the fixed corpus (`tools/build_warning_register.py`).
- `review/re-audit-output/` holds the re-audit table and narrative for the fixed corpus (`tools/analyze_clause_cards.py`, which now targets `fixed-generated/` by default).
- `compiler/tests/test_munsu_bylaws_fix_regressions.py` adds focused regressions for every repaired defect class.

## Contents

- `source/` - approved public MUNSU Bylaws PDF and source manifest.
- `fixed-generated/compiled/` - repaired generated corpus artifacts (use these).
- `current-generated/compiled/` - superseded pre-repair artifacts (review baseline only; do not import).
- `review/` - independent review findings, P0/P1 targets, warning register, release inventory, and release summary, plus `re-audit-output/` for the fixed corpus.
- `compiler/` - snapshot of the relevant Legal Corpus Compiler source and tests, including the parser fixes.
- `tools/analyze_clause_cards.py` - re-audit helper that checks the generated cards against the packaged PDF and review metadata.
- `tools/build_warning_register.py` - regenerates the warning register from a compiled corpus.
- `CLAUDE_FABLE_5_FIX_PROMPT.md` - the repair prompt this work executed.
- `GBRAIN_UPLOAD_GUIDE.md` - concrete next steps for turning the repaired corpus into approval-bound GBrain production bundles.

## Main Task

Fix the P0 and P1 Clause Card defects. The expected fix is generator/parser repair plus regeneration, not cosmetic hand-editing of Markdown.

Start by reading:

1. `CLAUDE_FABLE_5_FIX_PROMPT.md`
2. `review/munsu-bylaws-clause-card-review.md`
3. `review/p0-p1-fix-targets.csv`
4. `compiler/src/legal_corpus/parsers/legal_structure.py`

## Boundary

This is not legal advice and not a live import task. Do not sync, import, deploy, or claim production readiness. The PDF is the source of truth.


