# MUNSU Bylaws Clause Card Repair Report

Date: 2026-07-14. Executed against `BlakeColb/munsu-bylaws-clause-card-repair-package`, branch `fix/clause-card-repair`. Source of truth: `source/munsu-bylaws-2026.pdf` (62 pages). All numbers below come from commands run in this session; the exact commands and results are in section 6.

## 1. Full set verdict after fix

**PASS_WITH_FIXES** under the re-audit's verdict vocabulary, where the only "fixes" rows are the eight accurately carried unresolved-reference warnings (P2 metadata, explicitly allowed by the acceptance criteria). Zero cards are blocked and zero cards need structural fixes. Every acceptance criterion from the fix prompt is met: P0 = 0, P1 = 0, remaining P2 rows are unresolved-reference carriage only, and the fixed cards validate locally.

## 2. Card count before and after regeneration

323 cards before (byte-identical local reproduction of `current-generated/compiled`, verified modulo `generated_at`). **346 cards after.** The delta of +23 is exactly the new structural parents: the 22 Part II numbered Section cards (Sections 1–22) plus Part I Section I. Every one of the 323 old cards maps to exactly one distinct new card (bijection asserted programmatically); no old content was orphaned.

## 3. P0 / P1 / P2 counts after fix

P0: **0**. P1: **0**. P2: **8**, all of them unresolved-reference warning carriage rows (listed in section 8), none of them content or structure findings. For contrast, the starting state was 13 P0, 264 P1, 2 P2.

## 4. Exact files changed

Compiler (parser and export path):

- `compiler/src/legal_corpus/parsers/legal_structure.py` — the core repair. Accepts two-line lettered headings with mixed-case titles (the Part I Section I "By LAWS" case); parses `Section N: Title` lines as true Part II parent units, including the wrapped title on page 23 ("…Membership" + "and Responsibilities"); reparents lettered subsections under their numbered section and allows clauses directly under a numbered section (Section 6 has no lettered subsection); replaces the break-on-roman consumption with a list-aware consumer that keeps lower-alpha and roman items as their own lines (roman indented two spaces), disambiguates single-letter markers that are both alpha and roman (c, d, i, l, m, v, x) by sequence, splits run-in markers that continue mid-line after `;`/`:`/`.`, accepts bare marker lines (marker alone, text on the next line), attaches section intro sentences and clause-less item runs to the section card instead of dropping or splicing them, and tracks the page of the last consumed line for page-spanning units.
- `compiler/src/legal_corpus/source_records.py` — adds optional `SourceAnchor.page_end` (backward compatible; older extraction JSON parses unchanged).
- `compiler/src/legal_corpus/exporters/gbrain.py` — both `source_page_end` frontmatter sites now emit `anchor.page_end or anchor.page`.

Tests:

- `compiler/tests/test_munsu_bylaws_fix_regressions.py` (new) — nine synthetic-fixture regressions covering every repaired defect class, plus two corpus-level gates that read the packaged fixed output and run the re-audit with `--fail-on-findings` (skipped automatically where the corpus or pdfplumber is absent).

Tooling:

- `tools/analyze_clause_cards.py` — the two identity-keyed predicates (which flagged every `part-ii` ID and the literal `part-i`/`section-h` IDs unconditionally, making the acceptance criteria unreachable on any repaired set) are replaced with structure-aware checks; the nested-list finding now tests whether the **card** flattens markers rather than firing on every PDF segment that contains markers (a second unreachable gate); page confirmation gains per-line verification (the text layer orders two-line headings title-first) and an adjacent-page join with printed page numbers stripped (for spanning clauses); the narrative is generated from tallies instead of baked prose; constants target `fixed-generated/` per the prompt's instruction, with `--cards-dir/--packet/--pdf/--outputs` overrides and an optional `--fail-on-findings` exit-2 gate.
- `tools/build_warning_register.py` (new) — regenerates `warning-register.json`/`.md` from a compiled corpus's `legal/unresolved-references/` pages, mirroring the original register schema.

Documentation and outputs:

- `README.md` — supersession notice: `fixed-generated/compiled/` is the corrected corpus; `current-generated/compiled/` is retained only as the review baseline and must not be imported.
- `fixed-generated/` (new) — the regenerated corpus, regenerated warning register, and the old→new ID map.
- `review/re-audit-output/` — re-audit table and narrative for the fixed corpus.

## 5. Exact output directory for regenerated cards

`fixed-generated/compiled/legal/clauses/bylaws/` (346 cards), inside the full regenerated corpus at `fixed-generated/compiled/` (610 generated files including instrument, definitions, unresolved-reference pages, `.raw` sidecars, and the import manifest). `current-generated/compiled/` is untouched and marked superseded in the README so stale cards are not imported by accident; its manifest-level `sync_eligibility: blocked` also carries into every card.

## 6. Exact commands run and their results

Environment setup and baseline (from `compiler/`, `PYTHONPATH=src` throughout):

- `python3 -m pytest -q` on the unmodified snapshot → **101 passed** (confirming the original suite could not see these defects).
- `python3 -m legal_corpus.cli compile ../build/intake ../build/repro-broken --pdf-provider local` → 323 cards, byte-identical to `current-generated/compiled` modulo `generated_at` (clean attribution baseline).

Repair loop:

- `python3 -m legal_corpus.cli compile ../build/intake ../build/fixed-v3 --pdf-provider local` → `Compiled 1 source document(s) … with 610 generated corpus file(s)`; 346 cards.
- `python3 tools/build_warning_register.py` → `warning_count: 8` at `fixed-generated/review-packet/`.
- `python3 tools/analyze_clause_cards.py` (default paths, per the prompt's verification section) → `full_verdict: PASS_WITH_FIXES, reviewed: 346, passed: 338, blocked: 0, p1_count: 0, p2_count: 8, p0: []`, outputs written to `review/re-audit-output/`.

Required verification (from `compiler/`):

- `python3 -m pytest -q` → **112 passed** (101 original + 11 new regressions, corpus gates active, zero skips in this environment).
- `python3 -m legal_corpus.cli --help`, `compile --help`, `validate --help`, `report --help` → all exit 0.
- `python3 -m legal_corpus.cli validate ../fixed-generated/compiled` → `Validation passed … with 8 warning(s)`.
- `python3 -m legal_corpus.cli report ../fixed-generated/compiled` → 1 document, 346 legal clauses, 4 definitions, 8 unresolved references, validation passed, 0 blocking errors, `Sync eligibility: not approved by this report`.

PDF verification of the thirteen P0 successors (audit primitives: segment token recall plus anchor confirmation): all thirteen reach **100% recall** with no anchor issue. Old→new recall for the worst offenders: 18%→100% (`8-a-clause-2`), 28%→100% (`8-a-clause-1`, `8-a-clause-3`), 56%→100% (`11-e-clause-1`), 65%→100% (`11-c-clause-2`), 68%→100% (`7-c-clause-4`), 69%→100% (`4-d-clause-3`), 76%→100% (`8-b-clause-1`, `8-b-clause-4`), 73%→100% (`11-e-clause-3`). The page-spanning Resource Centres clause anchors 46–47 and its text joins "…Board of / Directors." across the page break.

## 7. Mapping of old unsafe card IDs to repaired or replacement card IDs

The thirteen P0 blockers:

| old (unsafe) | new (verified) |
| --- | --- |
| munsu-bylaws-part-i-section-h-clause-1-p8 | munsu-bylaws-part-i-section-i-clause-1 |
| munsu-bylaws-part-i-section-h-clause-2-p8 | munsu-bylaws-part-i-section-i-clause-2 |
| munsu-bylaws-part-ii-section-a-p23-clause-1 | munsu-bylaws-part-ii-section-8-a-clause-1 |
| munsu-bylaws-part-ii-section-a-p23-clause-2 | munsu-bylaws-part-ii-section-8-a-clause-2 |
| munsu-bylaws-part-ii-section-a-p23-clause-3 | munsu-bylaws-part-ii-section-8-a-clause-3 |
| munsu-bylaws-part-ii-section-b-p24-clause-1 | munsu-bylaws-part-ii-section-8-b-clause-1 |
| munsu-bylaws-part-ii-section-b-p24-clause-4 | munsu-bylaws-part-ii-section-8-b-clause-4 |
| munsu-bylaws-part-ii-section-c-p21-clause-4 | munsu-bylaws-part-ii-section-7-c-clause-4 |
| munsu-bylaws-part-ii-section-c-p42-clause-2 | munsu-bylaws-part-ii-section-11-c-clause-2 |
| munsu-bylaws-part-ii-section-d-p17-clause-3 | munsu-bylaws-part-ii-section-4-d-clause-3 |
| munsu-bylaws-part-ii-section-d-p46-clause-4 | munsu-bylaws-part-ii-section-12-d-clause-4 |
| munsu-bylaws-part-ii-section-e-p43-clause-1 | munsu-bylaws-part-ii-section-11-e-clause-1 |
| munsu-bylaws-part-ii-section-e-p43-clause-3 | munsu-bylaws-part-ii-section-11-e-clause-3 |

Because the Part II hierarchy repair renames every Part II ID (page suffixes are gone; numbered sections are inserted), the complete 323-row mapping is in `fixed-generated/old-to-new-card-id-map.csv`, with the 23 `new-structural-card` rows appended. Status counts: 49 `unchanged-id` (Part I and roots), 270 `replaced` (systematic Part II renames), and 4 `replaced-resectioned` — the old `section-b-p19-clause-*` cards, which the broken parser had filed under Section 5's B subsection when they are actually Section 6's by-election clauses 1–4 (the dropped `Section 6:` heading caused the misfiling; token containment of old text in the new cards is 100% for all four).

## 8. Unresolved-reference warnings still retained

Eight warnings are retained, regenerated with remapped `affected_clause` IDs in `fixed-generated/review-packet/warning-register.{json,md}` and as pages under `fixed-generated/compiled/legal/unresolved-references/`:

seven `subject_to` warnings on `part-i-section-f-clause-2`, `part-i-section-h-clause-2`, `part-ii-section-2-a-clause-5`, `part-ii-section-4-a-clause-2`, `part-ii-section-11-e-clause-1`, `part-ii-section-14-d-clause-4`, `part-ii-section-14-d-clause-5`; and one `exception_to` warning on `part-ii-section-20-a-clause-1`.

None were resolved to card IDs: their reference texts point at conditions and instruments, not at addressable clause targets, so resolving would have required inventing links. Two membership changes versus the old register, both faithfulness corrections with PDF evidence: (a) a new `subject_to` on `11-e-clause-1` exists because the restored roman item iv ("Groups will be subject to a two (2) consecutive semester period of recognition prior to being eligible for ratification") was entirely absent from the old truncated card, so the old pipeline could not see the reference; (b) the old `exception_to` on `b-p52-clause-1` is gone because it was a splice artifact — the flattened text let the detector capture "except the following conditions shall apply: a. A censured director…" as a garbage cross-reference target; in the repaired card that line correctly ends at the colon and no reference parses. Its successor `part-ii-section-14-b-clause-1` carries the clause faithfully with no warning.

## 9. Remaining attachment / source gaps

No attachment gap prevented verification; the PDF text layer covered every card. Honest residuals, none blocking:

- The source PDF itself contains the duplicated words "MacPherson College Representative Representative" (page 23); the card reproduces the source verbatim rather than silently correcting it.
- On page 24 area (Section 8 B clause 7), the source runs the interior category label "Financial" onto the end of item f's line before item g; the card keeps it there in source order. No words are lost and the audit passes the card; splitting the label out would require a heuristic about interior subheadings that this repair deliberately does not invent.
- `sync_eligibility` remains `blocked` throughout, exactly as the manifest specifies; nothing here approves, syncs, imports, or deploys anything.
- The local branch `fix/clause-card-repair` holds one clean commit; this environment cannot push, so the code-only diff is exported as `repair-changes.patch` (7 files, 930 insertions) and the regenerated tree is fully reproducible with the compile command in section 6.

## Closing state

The regenerated cards are verified against the PDF (all thirteen former P0s at 100% segment recall with confirmed anchors), the re-audit reports zero P0 and zero P1 findings with only the eight warning-carriage rows remaining, the compiler suite passes 112 tests including the new regressions and corpus gates, and local validation passes. There is no remaining blocker.
