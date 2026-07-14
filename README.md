# MUNSU Bylaws Clause Card Repair Package

This repository is a self-contained context package for repairing generated Clause Cards for a public MUNSU Bylaws corpus.

It exists so an external coding agent can work without access to Blake's local machine.

## Contents

- `source/` - approved public MUNSU Bylaws PDF and source manifest.
- `current-generated/compiled/` - current generated corpus artifacts, including Clause Cards.
- `review/` - independent review findings, P0/P1 targets, warning register, release inventory, and release summary.
- `compiler/` - snapshot of the relevant Legal Corpus Compiler source and tests.
- `tools/analyze_clause_cards.py` - re-audit helper that checks the generated cards against the packaged PDF and review metadata.
- `CLAUDE_FABLE_5_FIX_PROMPT.md` - paste-ready repair prompt for Claude Fable 5.

## Main Task

Fix the P0 and P1 Clause Card defects. The expected fix is generator/parser repair plus regeneration, not cosmetic hand-editing of Markdown.

Start by reading:

1. `CLAUDE_FABLE_5_FIX_PROMPT.md`
2. `review/munsu-bylaws-clause-card-review.md`
3. `review/p0-p1-fix-targets.csv`
4. `compiler/src/legal_corpus/parsers/legal_structure.py`

## Boundary

This is not legal advice and not a live import task. Do not sync, import, deploy, or claim production readiness. The PDF is the source of truth.

