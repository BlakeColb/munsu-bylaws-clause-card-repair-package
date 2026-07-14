# Claude Fable 5 Fix Prompt

You are repairing generated Clause Cards for a public MUNSU Bylaws corpus.

Your job is not to give legal advice, not to reinterpret the Bylaws, and not to redesign the overall ingestion product. Your job is to fix the generated artifacts and/or the generator so the Clause Cards are source-faithful, structurally correct, and safe to import/use as source-aware ordinary-chat context.

Treat `source/munsu-bylaws-2026.pdf` as the source of truth. Treat `current-generated/compiled/` as derived artifacts that may be wrong.

## Hard Boundaries

- Do not give legal advice.
- Do not invent missing Bylaw content.
- Do not paraphrase source text unless a generated note clearly marks it as non-source explanatory metadata.
- Do not sync, import, deploy, modify GBrain, modify Mycroft runtime, or claim production readiness.
- Do not mark a card fixed unless you can verify it against the PDF and metadata.
- Keep quoted PDF excerpts short in any human-facing report.
- Preserve page/source/clause attribution.
- Carry unresolved-reference warnings unless you can safely resolve them to stable generated card IDs.

## Repository Layout

```text
source/munsu-bylaws-2026.pdf
source/manifest.yaml
current-generated/compiled/legal/clauses/bylaws/
current-generated/compiled/.raw/extraction/
review/munsu-bylaws-clause-card-review.md
review/munsu-bylaws-clause-card-review-table.csv
review/p0-p1-fix-targets.csv
review/full-production-review-packet/
compiler/src/legal_corpus/
compiler/tests/
tools/analyze_clause_cards.py
```

## Starting Evidence

The independent review found:

- Full set verdict: FAIL
- Reviewed card count: 323
- Cards passed: 44
- Cards needing fixes: 266
- Cards blocked: 13
- P0 rows: 13
- P1 rows: 264
- P2 warning-only rows: 2

The existing compiler validator passed structurally, but that was not enough: this repair must satisfy PDF-source faithfulness, true legal hierarchy, nested list preservation, page anchors, and safe retrieval context.

## P0 Blockers To Fix

These cards must not remain unsafe. Either repair them in place or replace them with correctly structured cards and document old ID to new ID mappings.

```text
munsu-bylaws-part-i-section-h-clause-1-p8
munsu-bylaws-part-i-section-h-clause-2-p8
munsu-bylaws-part-ii-section-a-p23-clause-1
munsu-bylaws-part-ii-section-a-p23-clause-2
munsu-bylaws-part-ii-section-a-p23-clause-3
munsu-bylaws-part-ii-section-b-p24-clause-1
munsu-bylaws-part-ii-section-b-p24-clause-4
munsu-bylaws-part-ii-section-c-p21-clause-4
munsu-bylaws-part-ii-section-c-p42-clause-2
munsu-bylaws-part-ii-section-d-p17-clause-3
munsu-bylaws-part-ii-section-d-p46-clause-4
munsu-bylaws-part-ii-section-e-p43-clause-1
munsu-bylaws-part-ii-section-e-p43-clause-3
```

Required P0 repairs:

1. Part I Section I on PDF page 8 must be represented as its own section, not as Section H / Council Seal.
2. The two clauses under Part I Section I must not be children of Part I Section H.
3. Page-spanning clauses must include the full source segment, including continuation on the next page where applicable.
4. Clauses with lower-alpha or roman-numeral nested lists must not omit list items.
5. Generated text must not splice disconnected fragments together in a way that changes meaning.
6. Source page anchors must cover the actual page or page range containing the source text.

## P1 Structural Fixes To Apply Across The Set

Read `review/p0-p1-fix-targets.csv` for every P1 row. The dominant P1 patterns are:

1. Part II numeric section hierarchy is flattened.
   - The PDF organizes Part II under numbered sections: Section 1 through Section 22.
   - Generated cards currently parent many headings directly under Part II using page-suffixed letter sections such as `section-a-p23`.
   - Fix this by adding true numbered Section parent cards and reparenting lettered subsections and clauses under their actual numbered section.

2. Part I Section I is missing.
   - The PDF has Section H as Council Seal, then Section I as By LAWS, then Section J as Effective By Laws.
   - Generated hierarchy incorrectly places Section I clauses under Section H.

3. Nested source structure is flattened.
   - Lower-alpha lists and roman-numeral lists must be represented faithfully.
   - Acceptable approaches: preserve nested Markdown list structure inside a clause card, or split nested items into child cards if the local schema supports it.
   - Unacceptable: one paragraph that drops markers, drops items, or concatenates fragments out of order.

4. Unresolved references must be handled honestly.
   - Existing unresolved-reference warnings are not automatically blocking.
   - Resolve only where a stable target card exists after hierarchy repair.
   - Otherwise keep the warning metadata visible and accurate.

## Suggested Implementation Strategy

Work from the packaged compiler snapshot under `compiler/`.

Likely areas:

```text
compiler/src/legal_corpus/parsers/legal_structure.py
compiler/src/legal_corpus/exporters/gbrain.py
compiler/src/legal_corpus/compiler.py
compiler/src/legal_corpus/validators/gbrain.py
compiler/tests/
```

Then:

1. Reproduce the current artifact generation locally if possible.
2. Find where the MUNSU Bylaws profile/parser identifies parts, sections, headings, clauses, and page anchors.
3. Fix the parser/profile to detect:
   - Part I lettered headings including `I.`
   - Part II `Section N: Title` headings as true parent units
   - lettered headings under each numbered section
   - numbered clauses under each lettered heading
   - lower-alpha and roman-numeral nested lists as structure, not disposable inline text
   - page-spanning clauses and continuations
4. Regenerate the Clause Cards from the packaged PDF into a fixed output directory.
5. Remove or supersede bad old generated cards so stale unsafe cards are not imported accidentally.
6. Update or regenerate review packet metadata, warning registers, inventories, and import manifests as needed.
7. Add focused tests for:
   - Part I Section I not being swallowed by Section H
   - Part II Section 8 / Representation page 23 preserving nested lists
   - Part II Duties and Responsibilities page 24-25 preserving nested lists
   - Section 7 Referendum Voting clause 4 preserving subitems a-d
   - Resource Centres Section 12 page 46-47 page-spanning clause anchor
   - No generated card has P0/P1 review status after re-audit

## Verification Requirements

Run the repo's normal local verification commands from `compiler/`. If the package or repo uses local module imports, use `PYTHONPATH=src`.

At minimum:

```powershell
cd compiler
$env:PYTHONPATH='src'
python -m pytest -q
python -m legal_corpus.cli --help
python -m legal_corpus.cli compile --help
python -m legal_corpus.cli validate --help
python -m legal_corpus.cli report --help
```

Then run the actual compile/validate/report commands appropriate for this compiler after inspecting the CLI. Do not guess CLI flags if help/code shows a different interface.

Also run:

```powershell
cd ..
python tools/analyze_clause_cards.py
```

If your regenerated output path differs from `current-generated/compiled/legal/clauses/bylaws`, update the constants at the top of `tools/analyze_clause_cards.py` in your branch:

```text
PDF_PATH
CARDS_DIR
PACKET
OUTPUTS
```

Acceptance criteria for the re-audit:

- P0 count: 0
- P1 count: 0
- No current generated card is unsafe to import due to wrong parent, wrong slug, wrong title, wrong page anchor, omitted source text, spliced source text, or flattened legal hierarchy.
- Remaining warning-only P2 rows are allowed only if they are unresolved-reference metadata warnings and are accurately carried.
- The fixed cards validate locally.

## Output Required From You

When done, report:

1. Full set verdict after fix.
2. Card count before and after regeneration.
3. P0/P1/P2 counts after fix.
4. Exact files changed.
5. Exact output directory for regenerated cards.
6. Exact commands run and their results.
7. Mapping of old unsafe card IDs to repaired or replacement card IDs.
8. Any unresolved-reference warnings still retained.
9. Any remaining attachment/source gaps.

Do not end with "should be fixed." End only when the regenerated cards are verified against the PDF and the re-audit has zero P0/P1 findings, or clearly state the remaining blocker.

