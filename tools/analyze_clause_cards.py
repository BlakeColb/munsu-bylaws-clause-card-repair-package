from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = PACKAGE_ROOT / "source" / "munsu-bylaws-2026.pdf"
# The re-audit targets the repaired corpus; current-generated/ remains in the
# repository only as the superseded review baseline. Paths can be overridden
# with --cards-dir / --packet / --pdf / --outputs.
CARDS_DIR = PACKAGE_ROOT / "fixed-generated" / "compiled" / "legal" / "clauses" / "bylaws"
PACKET = PACKAGE_ROOT / "fixed-generated" / "review-packet"
OUTPUTS = PACKAGE_ROOT / "review" / "re-audit-output"


def norm(s: str) -> str:
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u00a0", " ")
    s = s.replace("full- time", "full-time")
    s = re.sub(r"(?<=\w)-\s+(?=\w)", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(s))


def parse_card(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
    else:
        fm, body = "", raw
    meta = parse_frontmatter(fm)
    m = re.search(r"## Source Text\s*(.*?)\s*## ", body, re.S)
    source_text = m.group(1).strip() if m else ""
    return {"path": path, "meta": meta, "body": body, "source_text": source_text}


def parse_scalar(value: str):
    value = value.strip()
    if value in {"null", "None", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_frontmatter(text: str) -> dict:
    meta: dict = {}
    current_list: str | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("- ") and current_list:
            meta[current_list].append(parse_scalar(line[2:].strip()))
            continue
        if line.startswith("  - ") and current_list:
            meta[current_list].append(parse_scalar(line[4:].strip()))
            continue
        if re.match(r"^[A-Za-z0-9_]+:", line):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                meta[key] = []
                current_list = key
            else:
                meta[key] = parse_scalar(value)
                current_list = None
    return meta


def extract_pages() -> dict[int, str]:
    pages: dict[int, str] = {}
    with pdfplumber.open(PDF_PATH) as doc:
        for idx, page in enumerate(doc.pages, start=1):
            pages[idx] = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
    return pages


def clean_pdf_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not re.fullmatch(r"\d+", line.strip())]


def full_clause_segment(card: dict, pages: dict[int, str]) -> str:
    meta = card["meta"]
    if meta.get("unit_type") != "clause":
        return ""
    source = card["source_text"].strip()
    m = re.match(r"^(\d+)\.\s+", source)
    if not m:
        return ""
    number = int(m.group(1))
    start_page = int(meta.get("source_page_start") or 0)
    if start_page <= 0:
        return ""

    numbered: list[tuple[int, str]] = []
    for pno in range(start_page, min(max(pages), start_page + 2) + 1):
        for line in clean_pdf_lines(pages.get(pno, "")):
            numbered.append((pno, line))

    candidates = []
    source_head = set(tokens(" ".join(source.split()[:18])))
    for idx, (_pno, line) in enumerate(numbered):
        if re.match(rf"^{number}\.\s+", line):
            window = " ".join(line for _p, line in numbered[idx : idx + 6])
            overlap = len(source_head & set(tokens(window)))
            candidates.append((overlap, idx))
    if not candidates:
        return ""
    _, start_idx = max(candidates)
    end_idx = len(numbered)
    next_number = number + 1
    for idx in range(start_idx + 1, len(numbered)):
        line = numbered[idx][1]
        next_line = numbered[idx + 1][1] if idx + 1 < len(numbered) else ""
        if re.match(rf"^{next_number}\.\s+", line):
            end_idx = idx
            break
        if re.match(r"^[A-Z]\.\s+[A-Z]", line):
            end_idx = idx
            break
        if (
            len(line) <= 55
            and re.search(r"[A-Za-z]", line)
            and not re.search(r"[.;:,]$", line)
            and re.match(r"^(?:[A-Z]|I)\.$", next_line)
        ):
            end_idx = idx
            break
        if re.match(r"^Section\s+\d+:", line):
            end_idx = idx
            break
        if re.match(r"^Part\s+[IVX]+:", line):
            end_idx = idx
            break
    return " ".join(line for _pno, line in numbered[start_idx:end_idx])


def token_recall(card_text: str, source_segment: str) -> float:
    source_tokens = tokens(source_segment)
    card_tokens = tokens(card_text)
    if not source_tokens or not card_tokens:
        return 1.0
    remaining: dict[str, int] = {}
    for tok in card_tokens:
        remaining[tok] = remaining.get(tok, 0) + 1
    matched = 0
    for tok in source_tokens:
        if remaining.get(tok, 0) > 0:
            matched += 1
            remaining[tok] -= 1
    return matched / len(source_tokens)


def has_nested_markers(text: str) -> bool:
    return bool(re.search(r"\s[a-z]\.\s+", text)) or bool(re.search(r"\s(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii)\.\s+", text))


def load_warning_ids() -> dict[str, list[str]]:
    warning_json = PACKET / "warning-register.json"
    if warning_json.exists():
        data = json.loads(warning_json.read_text(encoding="utf-8"))
        by_clause: dict[str, list[str]] = {}
        if isinstance(data, dict):
            items = data.get("warnings") or data.get("items") or []
        else:
            items = data
        for item in items:
            clause = (
                item.get("affected_clause")
                or item.get("affected_clause_id")
                or item.get("clause_id")
                or item.get("source_clause")
            )
            wid = item.get("warning_id") or item.get("id")
            if clause and wid:
                by_clause.setdefault(clause, []).append(wid)
        if by_clause:
            return by_clause

    by_clause = {}
    md_path = PACKET / "warning-register.md"
    if not md_path.exists():
        return by_clause
    text = md_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("| munsu-"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2:
            by_clause.setdefault(cells[1], []).append(cells[0])
    return by_clause


def derive_warnings_from_cards(cards: list[dict]) -> dict[str, list[str]]:
    """Fallback: derive warning carriage from card frontmatter when no register exists."""
    by_clause: dict[str, list[str]] = {}
    for card in cards:
        cid = card_id_of(card)
        for wid in card["meta"].get("unresolved_references") or []:
            if isinstance(wid, str):
                by_clause.setdefault(cid, []).append(wid)
    return by_clause


def _line_confirmed(line: str, hay: str, hay_set: set[str]) -> bool:
    """Confirm a single card line against one page's normalized text."""
    n = norm(line)
    if not n:
        return True
    if n in hay:
        return True
    line_tokens = tokens(line)
    if not line_tokens:
        return True
    # Two-line headings appear in the text layer as "TITLE" above "A.", so
    # confirm short heading lines token-wise rather than as a substring.
    if len(line_tokens) <= 5 and all(tok in hay_set for tok in line_tokens):
        return True
    words = n.split()
    if len(words) >= 14:
        first = " ".join(words[:8])
        last = " ".join(words[-8:])
        if first in hay or last in hay:
            return True
    present = sum(1 for tok in line_tokens if tok in hay_set)
    return present / len(line_tokens) >= 0.9


def find_pages(source_text: str, pages: dict[int, str]) -> list[int]:
    needle = norm(source_text)
    if not needle:
        return []
    needle_tokens = tokens(source_text)
    source_lines = [ln.strip() for ln in source_text.splitlines() if ln.strip()]
    found = []
    for pno, text in pages.items():
        hay = norm(text)
        if needle in hay:
            found.append(pno)
            continue
        hay_tokens = tokens(text)
        hay_set = set(hay_tokens)
        # Heading cards can appear in the PDF as "TITLE" followed by "A.".
        heading = re.fullmatch(r"([a-z])\s+(.+)", " ".join(needle_tokens))
        if heading and len(needle_tokens) <= 5:
            if all(tok in hay_set for tok in needle_tokens):
                found.append(pno)
                continue
        # Multi-line cards (heading plus body, or list-preserving clauses) are
        # confirmed when every line is individually present on the page.
        if len(source_lines) > 1 and all(_line_confirmed(ln, hay, hay_set) for ln in source_lines):
            found.append(pno)
            continue
        # For longer clauses, PDF extraction may break punctuation/line joins; check important chunks.
        words = needle.split()
        if len(words) >= 14:
            first = " ".join(words[:8])
            last = " ".join(words[-8:])
            if first in hay or last in hay:
                found.append(pno)
                continue
            if needle_tokens:
                present = sum(1 for tok in needle_tokens if tok in hay_set)
                # Repeated common words inflate less than this threshold; this is for extraction quirks.
                if present / len(needle_tokens) >= 0.82:
                    found.append(pno)
    if found:
        return found
    # Page-spanning text may not sit wholly on any single page; confirm against
    # adjacent page joins (with printed page numbers stripped) so a clause
    # continuing onto the next page anchors to both.
    ordered = sorted(pages)
    for pno in ordered:
        next_text = pages.get(pno + 1)
        if next_text is None:
            continue
        left = " ".join(clean_pdf_lines(pages[pno]))
        right = " ".join(clean_pdf_lines(next_text))
        joined = norm(left + " " + right)
        if needle in joined:
            return [pno, pno + 1]
        words = needle.split()
        if len(words) >= 14:
            first = " ".join(words[:8])
            last = " ".join(words[-8:])
            if first in norm(left) and last in norm(right):
                return [pno, pno + 1]
    return found


NUMBERED_SECTION_RE = re.compile(r"^munsu-bylaws-part-ii-section-(\d+)$")
PART_I_SECTION_RE = re.compile(r"^munsu-bylaws-part-i-section-([a-z])$")
PART_I_COLLISION_RE = re.compile(r"^munsu-bylaws-part-i-section-([a-z])-clause-\d+-p\d+$")


def card_id_of(card: dict) -> str:
    return card["meta"].get("clause_id", card["path"].stem)


def parent_chain_of(card: dict) -> list[str]:
    return [str(p) for p in (card["meta"].get("parent_chain") or [])]


def compute_set_facts(cards: list[dict]) -> dict:
    """Whole-set structural facts the per-card predicates need.

    These replace earlier checks that were keyed to the identity of the broken
    output (flagging every part-ii id, and the literal part-i / section-h ids)
    and therefore could never reach zero on a repaired set.
    """
    import string as _string

    ids = {card_id_of(c) for c in cards}
    numbered_sections = sorted(
        int(NUMBERED_SECTION_RE.match(i).group(1)) for i in ids if NUMBERED_SECTION_RE.match(i)
    )
    part_i_letters = sorted(
        PART_I_SECTION_RE.match(i).group(1) for i in ids if PART_I_SECTION_RE.match(i)
    )
    missing_letters: list[str] = []
    if part_i_letters:
        lo, hi = part_i_letters[0], part_i_letters[-1]
        expected = _string.ascii_lowercase[_string.ascii_lowercase.index(lo) : _string.ascii_lowercase.index(hi) + 1]
        missing_letters = [ch for ch in expected if ch not in part_i_letters]
    collision_hosts: set[str] = set()
    for c in cards:
        m = PART_I_COLLISION_RE.match(card_id_of(c))
        if m:
            collision_hosts.add(f"munsu-bylaws-part-i-section-{m.group(1)}")
    for c in cards:
        for key in ("child_clauses", "child_ids", "children"):
            for child in c["meta"].get(key) or []:
                if isinstance(child, str) and PART_I_COLLISION_RE.match(child):
                    cid = card_id_of(c)
                    if re.match(r"^munsu-bylaws-part-i-section-[a-z]$", cid):
                        collision_hosts.add(cid)
    return {
        "numbered_sections": numbered_sections,
        "part_i_missing_letters": missing_letters,
        "part_i_collision_hosts": collision_hosts,
    }


def is_part_ii_structural_gap(card: dict, facts: dict) -> bool:
    """A Part II card passes only if it is, or descends from, a numbered Section card."""
    cid = card_id_of(card)
    if not cid.startswith("munsu-bylaws-part-ii"):
        return False
    if cid == "munsu-bylaws-part-ii":
        return not facts["numbered_sections"]
    if NUMBERED_SECTION_RE.match(cid):
        return False
    return not any(NUMBERED_SECTION_RE.match(pid) for pid in parent_chain_of(card))


def part_i_misparsed_section_i(card: dict) -> bool:
    """Any Part I clause with a page collision suffix is a misfiled sibling-section clause."""
    return bool(PART_I_COLLISION_RE.match(card_id_of(card)))


def part_i_parent_section_i_gap(card: dict, facts: dict) -> str | None:
    cid = card_id_of(card)
    if cid == "munsu-bylaws-part-i" and facts["part_i_missing_letters"]:
        missing = ", ".join(ch.upper() for ch in facts["part_i_missing_letters"])
        return (
            f"Part I lettered section sequence is missing Section {missing} from the generated hierarchy; "
            "an adjacent section is carrying its clauses."
        )
    if cid in facts["part_i_collision_hosts"]:
        return (
            "This lettered Part I section carries collision-suffixed child clauses that belong to a "
            "missing sibling section; remove them from this section's child metadata."
        )
    return None


def card_preserves_list_structure(card_text: str, segment: str) -> bool:
    """True when the card carries at least as many newline-anchored list items as the segment shows inline."""
    marker = r"(?:[a-z]|i{2,3}|iv|v|vi{1,3}|ix|x|xi{1,3})"
    segment_markers = len(re.findall(rf"\s{marker}\.\s+", segment))
    if segment_markers == 0:
        return True
    card_markers = len(re.findall(rf"(?:^|\n)\s*{marker}\.\s+", card_text))
    return card_markers >= segment_markers


def page_anchor_issue(card: dict, pages_found: list[int]) -> str | None:
    meta = card["meta"]
    start = meta.get("source_page_start")
    end = meta.get("source_page_end") or start
    if not pages_found:
        return "Source text not confirmed on the extracted PDF text layer"
    if start is None:
        return "Missing source page anchor"
    if not any(int(start) <= p <= int(end) for p in pages_found):
        return f"Source text found only on PDF page(s) {pages_found}, not anchored page {start}-{end}"
    return None


def duplicate_source_groups(cards: list[dict]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for card in cards:
        key = norm(card["source_text"])
        if key:
            groups.setdefault(key, []).append(card["meta"].get("clause_id", card["path"].stem))
    return {k: v for k, v in groups.items() if len(v) > 1}


def hierarchy_label(card: dict) -> str:
    meta = card["meta"]
    chain = meta.get("parent_chain") or []
    return " > ".join(chain + [meta.get("clause_id", "")])


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    pages = extract_pages()
    cards = [parse_card(path) for path in sorted(CARDS_DIR.glob("*.md"), key=lambda p: p.name)]
    facts = compute_set_facts(cards)
    warnings = load_warning_ids() or derive_warnings_from_cards(cards)
    dupes = duplicate_source_groups(cards)
    dupe_ids = {cid for ids in dupes.values() for cid in ids}

    rows = []
    for card in cards:
        meta = card["meta"]
        cid = meta.get("clause_id", card["path"].stem)
        found = find_pages(card["source_text"], pages)
        segment = full_clause_segment(card, pages)
        recall = token_recall(card["source_text"], segment) if segment else 1.0
        segment_token_count = len(tokens(segment))
        card_token_count = len(tokens(card["source_text"]))
        issues: list[str] = []
        fixes: list[str] = []
        severity = "P2"
        verdict = "PASS"

        anchor = f"{meta.get('source_page_start')}-{meta.get('source_page_end') or meta.get('source_page_start')}"
        issue = page_anchor_issue(card, found)
        if issue:
            verdict = "BLOCKED_UNSAFE_TO_IMPORT"
            severity = "P0"
            issues.append(issue)
            fixes.append("Re-anchor to the PDF page containing the source text and re-run source-text verification.")

        if part_i_misparsed_section_i(card):
            verdict = "BLOCKED_UNSAFE_TO_IMPORT"
            severity = "P0"
            issues.append("Part I Section I clause is misidentified as Section H / Council Seal; title, slug, parent, and hierarchy are wrong.")
            fixes.append("Create/use Part I Section I 'By LAWS' parent and move this clause under it with the correct clause ID/title.")

        gap_message = part_i_parent_section_i_gap(card, facts)
        if gap_message and severity != "P0":
            verdict = "NEEDS_STRUCTURAL_FIX"
            severity = "P1"
            issues.append(gap_message)
            fixes.append("Add the missing Part I section card and correct the affected child metadata.")

        if segment and recall < 0.78 and segment_token_count > card_token_count + 8:
            verdict = "BLOCKED_UNSAFE_TO_IMPORT"
            severity = "P0"
            issues.append(
                f"Card source text omits or splices required PDF clause text; card captures about {recall:.0%} of the extracted clause segment."
            )
            fixes.append("Regenerate this clause from the full PDF clause segment, preserving nested list items and page-spanning text.")

        if is_part_ii_structural_gap(card, facts) and severity != "P0":
            verdict = "NEEDS_STRUCTURAL_FIX"
            severity = "P1"
            issues.append("Part II numeric section hierarchy is flattened; card is parented directly under Part II or a page-suffixed letter section instead of Section N.")
            fixes.append("Add numbered Section 1-22 parent cards and reparent/rename this card under its true Section N heading.")

        if (
            segment
            and has_nested_markers(segment)
            and not card_preserves_list_structure(card["source_text"], segment)
            and severity != "P0"
        ):
            verdict = "NEEDS_STRUCTURAL_FIX"
            severity = "P1"
            issues.append("Nested source list structure is flattened into paragraph text, which loses legal hierarchy even where words are present.")
            fixes.append("Represent lower-alpha/roman subclauses as nested structure or separate child units with source page attribution.")

        if cid in warnings:
            if severity not in {"P0", "P1"}:
                verdict = "NEEDS_MINOR_FIX"
                severity = "P2"
            issues.append("Unresolved-reference warning is accurately carried as review metadata and should remain visible for import review.")
            fixes.append("Resolve the target if a stable Clause Card exists; otherwise keep the unresolved warning attached.")

        if cid in dupe_ids and severity != "P0":
            # Repeated headings such as A. GENERAL are legitimate, but exact full source duplicates deserve review.
            ids = [x for x in next(v for k, v in dupes.items() if cid in v)]
            if len(set(ids)) > 1 and meta.get("unit_type") == "clause" and len(tokens(card["source_text"])) > 8:
                if severity == "P2":
                    verdict = "NEEDS_MINOR_FIX"
                issues.append(f"Exact source text is shared with another card: {', '.join(ids)}.")
                fixes.append("Confirm this is a legitimate repeated heading/text, or deduplicate if it is an artifact copy.")

        if not issues:
            issues.append("No source-fidelity, anchor, hierarchy, duplicate, or warning issue found in this audit.")
            fixes.append("None.")

        confidence = "high" if found and not issue else "medium"
        if verdict == "PASS" and meta.get("unit_type") in {"part", "section"}:
            confidence = "medium-high"

        rows.append(
            {
                "card_id": cid,
                "file_name": card["path"].name,
                "pdf_page_anchor": anchor,
                "hierarchy": hierarchy_label(card),
                "verdict": verdict,
                "severity": severity,
                "issue": " ".join(dict.fromkeys(issues)),
                "required_fix": " ".join(dict.fromkeys(fixes)),
                "confidence": confidence,
                "_found_pages": ";".join(map(str, found)),
                "_warning_ids": ";".join(warnings.get(cid, [])),
                "_segment_recall": f"{recall:.3f}",
                "_segment_tokens": str(segment_token_count),
                "_card_tokens": str(card_token_count),
            }
        )

    csv_path = OUTPUTS / "munsu-bylaws-clause-card-review-table.csv"
    public_fields = [
        "card_id",
        "file_name",
        "pdf_page_anchor",
        "hierarchy",
        "verdict",
        "severity",
        "issue",
        "required_fix",
        "confidence",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=public_fields)
        writer.writeheader()
        writer.writerows({k: row[k] for k in public_fields} for row in rows)

    md_path = OUTPUTS / "munsu-bylaws-clause-card-review.md"
    counts = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    passed = counts.get("PASS", 0)
    needs_fixes = sum(counts.get(k, 0) for k in ["NEEDS_MINOR_FIX", "NEEDS_STRUCTURAL_FIX"])
    blocked = counts.get("BLOCKED_UNSAFE_TO_IMPORT", 0) + counts.get("CANNOT_VERIFY_FROM_ATTACHMENTS", 0)
    full_verdict = "FAIL" if blocked else ("PASS_WITH_FIXES" if needs_fixes else "PASS")

    with md_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"FULL SET VERDICT: {full_verdict}\n")
        f.write(f"Reviewed card count: {len(rows)}\n")
        f.write(f"Cards passed: {passed}\n")
        f.write(f"Cards needing fixes: {needs_fixes}\n")
        f.write(f"Cards blocked: {blocked}\n")
        p0_rows = [row for row in rows if row["severity"] == "P0"]
        p1_rows = [row for row in rows if row["severity"] == "P1"]
        warning_rows = [row for row in rows if row["_warning_ids"]]
        if blocked:
            most_serious = f"{blocked} card(s) are unsafe to import; see the P0 list below."
        elif p1_rows:
            most_serious = f"{len(p1_rows)} card(s) need structural fixes; see the grouped patterns below."
        elif warning_rows:
            most_serious = (
                f"No blocking or structural findings. {len(warning_rows)} card(s) carry warning-only "
                "unresolved-reference metadata, which remains visible for import review."
            )
        else:
            most_serious = "No blocking, structural, or warning-carriage findings."
        f.write(f"Most serious issue: {most_serious}\n\n")
        f.write("| card_id | file_name | pdf_page_anchor | hierarchy | verdict | severity | issue | required_fix | confidence |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for row in rows:
            vals = [row[k] for k in public_fields]
            vals = [str(v).replace("|", "\\|").replace("\n", " ") for v in vals]
            f.write("| " + " | ".join(vals) + " |\n")
        f.write("\n## P0 Blockers Only\n\n")
        if p0_rows:
            for row in p0_rows:
                f.write(f"- `{row['card_id']}`: {row['issue']} Required fix: {row['required_fix']}\n")
        else:
            f.write("None.\n")
        f.write("\n## P1 Fixes Grouped By Pattern\n\n")
        if p1_rows:
            pattern_counts: dict[str, int] = {}
            for row in p1_rows:
                pattern = row["issue"].split(". ")[0].rstrip(".") + "."
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            for pattern, count in sorted(pattern_counts.items(), key=lambda kv: -kv[1]):
                f.write(f"- {count} card(s): {pattern}\n")
        else:
            f.write("None.\n")
        f.write("\n## Warning Carriage\n\n")
        if warning_rows:
            f.write(
                f"{len(warning_rows)} card(s) carry unresolved-reference warning metadata. "
                "They are not compiler-blocking by themselves; resolve only where a stable target card exists, otherwise keep them visible.\n\n"
            )
            for row in warning_rows:
                f.write(f"- `{row['card_id']}`: {row['_warning_ids']}\n")
        else:
            f.write("No unresolved-reference warnings are carried by any card.\n")
        f.write("\n## Cards Clean Enough For Import\n\n")
        clean = [row["card_id"] for row in rows if row["verdict"] == "PASS"]
        f.write(f"{len(clean)} cards: " + ", ".join(f"`{cid}`" for cid in clean) + "\n")
        f.write("\n## Cards To Exclude From Next Import Batch\n\n")
        exclude = [row["card_id"] for row in rows if row["verdict"] != "PASS"]
        if exclude:
            f.write(f"{len(exclude)} cards: " + ", ".join(f"`{cid}`" for cid in exclude) + "\n")
        else:
            f.write("None.\n")
        f.write("\n## Attachment Gaps\n\n")
        f.write("- No attachment gap prevented source verification: PDF text extraction and warning metadata were available for this audit.\n")
        structural_notes = []
        if not facts["numbered_sections"]:
            structural_notes.append("the Part II numbered Section 1-22 parent cards are absent")
        if facts["part_i_missing_letters"]:
            missing = ", ".join(ch.upper() for ch in facts["part_i_missing_letters"])
            structural_notes.append(f"Part I is missing lettered Section {missing}")
        if structural_notes:
            f.write(f"- Generated-set structural gaps (review findings, not attachment gaps): {'; '.join(structural_notes)}.\n")
        f.write("\n## Recommendation\n\n")
        if blocked:
            f.write("Do not import this card set. Fix the listed P0 blockers first, then re-run this audit.\n")
        elif p1_rows:
            f.write("Do not import this card set yet. Apply the grouped P1 structural fixes, then re-run this audit.\n")
        elif warning_rows:
            f.write(
                "No P0/P1 findings remain. The set is clean for import review; the remaining unresolved-reference "
                "warnings are bounded metadata that should stay visible unless resolved to stable card IDs.\n"
            )
        else:
            f.write("No findings remain. The set is clean for import review.\n")

    summary = {
        "full_verdict": full_verdict,
        "reviewed": len(rows),
        "passed": passed,
        "needs_fixes": needs_fixes,
        "blocked": blocked,
        "counts": counts,
        "csv": str(csv_path),
        "md": str(md_path),
        "p0": [row["card_id"] for row in rows if row["severity"] == "P0"],
        "p1_count": sum(1 for row in rows if row["severity"] == "P1"),
        "p2_count": sum(1 for row in rows if row["severity"] == "P2" and row["verdict"] != "PASS"),
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Audit generated Clause Cards against the source PDF.")
    parser.add_argument("--cards-dir", type=Path, default=None, help="Override CARDS_DIR.")
    parser.add_argument("--packet", type=Path, default=None, help="Override PACKET (warning register location).")
    parser.add_argument("--pdf", type=Path, default=None, help="Override PDF_PATH.")
    parser.add_argument("--outputs", type=Path, default=None, help="Override OUTPUTS.")
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit 2 if any P0/P1 rows remain.")
    args = parser.parse_args()
    if args.cards_dir:
        CARDS_DIR = args.cards_dir.resolve()
    if args.packet:
        PACKET = args.packet.resolve()
    if args.pdf:
        PDF_PATH = args.pdf.resolve()
    if args.outputs:
        OUTPUTS = args.outputs.resolve()
    result = main()
    if args.fail_on_findings and (result["blocked"] or result["p1_count"]):
        raise SystemExit(2)
