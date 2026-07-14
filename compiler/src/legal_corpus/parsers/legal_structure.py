"""Deterministic legal structure parser."""

import re
from typing import cast

from legal_corpus.manifest import ManifestDocument
from legal_corpus.source_records import SourceAnchor, SourceBlock, SourceExtraction
from legal_corpus.structure_records import (
    DefinitionRecord,
    LegalStructure,
    LegalUnit,
    ReferenceRecord,
    ReferenceType,
    StructureRecordError,
    UnitType,
)


_LABELLED_HEADING_RE = re.compile(
    r"^(?P<label>Section|Article|Policy|Schedule|Appendix)\s+"
    r"(?P<number>[A-Za-z0-9.]+)"
    r"(?:\s*[-:]\s*(?P<title>.+))?$",
    re.IGNORECASE,
)
_NUMBERED_UNIT_RE = re.compile(r"^\s*(?P<number>\d+(?:\.\d+)+)\s+(?P<text>.+?)\s*$")
_PROFILE_NUMBERED_CLAUSE_RE = re.compile(r"^\s*(?P<number>\d+)\.\s*(?P<text>.*)$")
_BYLAW_PART_RE = re.compile(r"^Part\s+(?P<roman>[IVXLCDM]+)\s*:\s*(?P<title>.+)$", re.IGNORECASE)
_BYLAW_SECTION_RE = re.compile(r"^(?P<letter>[A-Z])\.\s*(?P<title>.*)$")
_BYLAW_NUMBERED_SECTION_RE = re.compile(r"^Section\s+(?P<number>\d+)\s*:\s*(?P<title>.+)$")
_BYLAW_LIST_ITEM_RE = re.compile(r"^(?P<marker>[a-z]|[ivxlcdm]{2,6})\.(?:\s+(?P<text>\S.*))?$")
_ROMAN_MARKER_CHARS = frozenset("ivxlcdm")
_RUNIN_MARKER_SPLIT_RE = re.compile(r"(?<=[;:.])\s+(?=(?:[a-z]|[ivxlcdm]{2,6})\.(?:\s+\S|$))")


def _split_runin_list_markers(line: str) -> list[str]:
    """Split list items that run on mid-line in the source text layer.

    The PDF occasionally places the next marker on the same physical line as
    the previous item (e.g. "... society; viii. Nursing ..."). Splitting on
    the marker boundary changes only whitespace, never source words or order.
    """
    if not _RUNIN_MARKER_SPLIT_RE.search(line):
        return [line]
    return [part.strip() for part in _RUNIN_MARKER_SPLIT_RE.split(line) if part.strip()]
_POLICY_SECTION_RE = re.compile(r"^Section\s+(?P<number>\d+)\s*:\s*(?P<title>.+)$", re.IGNORECASE)
_POLICY_ROMAN_RE = re.compile(r"^(?P<roman>[IVXLCDM]+)\.\s*(?P<title>.+)$", re.IGNORECASE)
_POLICY_PROVISION_RE = re.compile(r"^\((?P<letter>[a-z])\)\s*(?P<text>.*)$", re.IGNORECASE)
_ADOPTED_RE = re.compile(r"^Adopted:\s*(?P<value>.+)$", re.IGNORECASE)
_AMENDED_RE = re.compile(r"^Amended:\s*(?P<value>.+)$", re.IGNORECASE)
_QUOTED_DEFINITION_RE = re.compile(
    r'^\s*(?:\d+(?:\.\d+)*\.?\s+)?(?P<definition>(?P<quote>["\u201c])'
    r'(?P<term>[^"\u201d]+)["\u201d]\s+means\s+.+)',
    re.IGNORECASE,
)
_UNQUOTED_DEFINITION_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?"
    r"(?P<definition>(?P<term>[A-Z][A-Za-z0-9 -]{1,80})\s+means\s+.+)"
)
_REFERENCE_TARGET = r"(?P<target>\d+(?:\.\d+)+|.+?)"
_REFERENCE_PATTERNS: tuple[tuple[ReferenceType, re.Pattern[str]], ...] = (
    (
        "read_with",
        re.compile(rf"\bread with\s+(?:the\s+)?{_REFERENCE_TARGET}(?:\.|$)", re.IGNORECASE),
    ),
    (
        "subject_to",
        re.compile(
            rf"\bsubject to\s+(?:section\s+)?{_REFERENCE_TARGET}(?:\.|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "despite",
        re.compile(
            rf"\bdespite\s+(?:section\s+)?{_REFERENCE_TARGET}(?:\.|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "exception_to",
        re.compile(
            rf"\bexcept(?:ion to)?\s+(?:section\s+)?{_REFERENCE_TARGET}(?:\.|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "amends",
        re.compile(
            rf"\b(?:amends|amended by)\s+(?:section\s+)?{_REFERENCE_TARGET}(?:\.|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "supersedes",
        re.compile(
            rf"\bsupersedes\s+(?:section\s+)?{_REFERENCE_TARGET}(?:\.|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "higher_authority_than",
        re.compile(
            rf"\bprevails over\s+(?:an?\s+|the\s+)?{_REFERENCE_TARGET}(?:\.|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "section_reference",
        re.compile(r"\bunder section\s+(?P<target>\d+(?:\.\d+)+)\b", re.IGNORECASE),
    ),
)


def parse_legal_structure(
    extraction: SourceExtraction,
    document: ManifestDocument,
    *,
    known_documents: list[ManifestDocument] | None = None,
) -> LegalStructure:
    """Parse source extraction records into legal structure records."""
    if document.profile == "munsu_bylaws_v1":
        return _parse_munsu_bylaws(extraction, document, known_documents=known_documents)
    if document.profile == "munsu_policy_v1":
        return _parse_munsu_policy(extraction, document, known_documents=known_documents)

    instrument = _instrument_unit(extraction, document)
    units = [instrument]
    definitions: list[DefinitionRecord] = []
    warnings: list[str] = []
    current_heading: LegalUnit | None = None

    for block in extraction.blocks:
        if block.block_type == "heading":
            heading_unit = _heading_unit(block, document, instrument)
            if heading_unit:
                units.append(heading_unit)
                current_heading = heading_unit
            continue

        parsed_units = _body_units(block, document, instrument, current_heading)
        if not parsed_units and block.text.strip():
            warnings.append(f"unparsed block retained for review: {block.block_id}")
        units.extend(parsed_units)

    seen_definition_terms: set[str] = set()
    for unit in units:
        if unit.unit_type != "clause":
            continue
        definition = _definition_from_unit(unit, document)
        if definition and definition.slug not in seen_definition_terms:
            definitions.append(definition)
            seen_definition_terms.add(definition.slug)

    references = _references_from_units(
        units,
        known_documents=known_documents or [],
    )

    return LegalStructure(
        instrument_slug=document.slug,
        instrument_title=document.title,
        document_type=document.document_type,
        source_path=document.source_path,
        source_hash=extraction.source_hash,
        units=units,
        definitions=definitions,
        references=references,
        warnings=warnings,
    )


def _parse_munsu_bylaws(
    extraction: SourceExtraction,
    document: ManifestDocument,
    *,
    known_documents: list[ManifestDocument] | None = None,
) -> LegalStructure:
    instrument = _instrument_unit(extraction, document)
    units: list[LegalUnit] = [instrument]
    warnings: list[str] = []
    current_part: LegalUnit | None = None
    current_numbered_section: LegalUnit | None = None
    current_section: LegalUnit | None = None
    current_clause: LegalUnit | None = None
    pending_act_title: str | None = None
    started = False
    lines = _profile_lines(extraction)
    skip_pdf_front_matter = extraction.provider == "local_pdf" and (extraction.provider_metadata.page_count or 0) > 10
    index = 0
    while index < len(lines):
        line, anchor, block_id = lines[index]
        if skip_pdf_front_matter and anchor.page is not None and anchor.page < 5:
            index += 1
            continue
        if _skip_profile_line(line):
            index += 1
            continue
        part_match = _BYLAW_PART_RE.match(line)
        if part_match:
            started = True
            current_part = _profile_unit(
                document,
                unit_type="part",
                suffix=f"part-{_normalize_identifier(part_match.group('roman'))}",
                text=line,
                title=part_match.group("title").strip(),
                number=part_match.group("roman").upper(),
                anchor=anchor,
                parent=instrument,
                source_block_id=block_id,
            )
            _append_profile_unit(units, current_part)
            current_numbered_section = None
            current_section = None
            current_clause = None
            pending_act_title = None
            index += 1
            continue
        if not started:
            index += 1
            continue
        numbered_match = _BYLAW_NUMBERED_SECTION_RE.match(line)
        if numbered_match:
            if current_part is None:
                raise StructureRecordError("munsu_bylaws_v1 numbered section appeared before a Part heading")
            number = numbered_match.group("number")
            title = numbered_match.group("title").strip()
            heading_lines = [line]
            consumed_extra_title = False
            if index + 1 < len(lines):
                continuation = lines[index + 1][0]
                if (
                    continuation
                    and continuation[0].islower()
                    and not _heading_like(continuation)
                    and not _BYLAW_LIST_ITEM_RE.match(continuation)
                ):
                    # Wrapped heading, e.g. "Section 8: Board of Directors
                    # Membership" continued by "and Responsibilities".
                    title = f"{title} {continuation.strip()}"
                    heading_lines.append(continuation)
                    consumed_extra_title = True
            suffix = f"{current_part.slug}-section-{_normalize_identifier(number)}".removeprefix(f"{document.slug}-")
            current_numbered_section = _profile_unit(
                document,
                unit_type="section",
                suffix=suffix,
                text=_join_profile_text(heading_lines),
                title=title,
                number=number,
                anchor=anchor,
                parent=current_part,
                source_block_id=block_id,
            )
            _append_profile_unit(units, current_numbered_section)
            current_section = None
            current_clause = None
            index += 2 if consumed_extra_title else 1
            continue
        section_match = _BYLAW_SECTION_RE.match(line)
        if section_match and _is_bylaw_section_heading(line, lines, index):
            if current_part is None:
                raise StructureRecordError("munsu_bylaws_v1 section appeared before a Part heading")
            letter = section_match.group("letter").upper()
            title = section_match.group("title").strip()
            consumed_extra_title = False
            if not title and index + 1 < len(lines):
                next_line = lines[index + 1][0]
                if next_line and not _heading_like(next_line):
                    title = next_line.strip()
                    consumed_extra_title = True
            section_parent = current_numbered_section or current_part
            if current_numbered_section is not None:
                suffix = f"{current_numbered_section.slug}-{letter.lower()}".removeprefix(f"{document.slug}-")
            else:
                suffix = f"{current_part.slug}-section-{letter.lower()}".removeprefix(f"{document.slug}-")
            metadata: dict[str, str | list[str]] = {}
            if pending_act_title:
                metadata["act_title"] = pending_act_title
            current_section = _profile_unit(
                document,
                unit_type="section",
                suffix=suffix,
                text=f"{letter}. {title}".strip(),
                title=title or f"Section {letter}",
                number=letter,
                anchor=anchor,
                parent=section_parent,
                source_block_id=block_id,
            )
            current_section.metadata.update(metadata)
            _append_profile_unit(units, current_section)
            current_clause = None
            index += 2 if consumed_extra_title else 1
            continue
        if current_part and current_section is None and pending_act_title is None and line.lower().startswith("an act"):
            pending_act_title = line
            index += 1
            continue
        clause_match = _PROFILE_NUMBERED_CLAUSE_RE.match(line)
        if clause_match:
            clause_parent = current_section or current_numbered_section
            if clause_parent is None:
                raise StructureRecordError("munsu_bylaws_v1 numbered clause appeared before a section heading")
            text, last_page, index = _consume_bylaw_flow(lines, index)
            number = clause_match.group("number")
            suffix = f"{clause_parent.slug}-clause-{_normalize_identifier(number)}".removeprefix(f"{document.slug}-")
            current_clause = _profile_unit(
                document,
                unit_type="clause",
                suffix=suffix,
                text=text,
                title=f"{clause_parent.title or clause_parent.number} {number}",
                number=number,
                anchor=_anchor_with_span(anchor, last_page),
                parent=clause_parent,
                source_block_id=block_id,
            )
            _append_profile_unit(units, current_clause)
            continue
        is_list_item = bool(_BYLAW_LIST_ITEM_RE.match(line))
        if (
            current_section is not None
            and current_clause is None
            and line
            and (is_list_item or not _heading_like(line))
        ):
            # Section body before any numbered clause: intro sentences and
            # clause-less list runs (e.g. Referendum Procedures items a-e)
            # belong to the section card instead of being dropped or spliced
            # into a neighbouring clause.
            text, last_page, index = _consume_bylaw_flow(lines, index)
            if text:
                current_section.text = f"{current_section.text}\n{text}"
            _extend_unit_span(current_section, last_page)
            continue
        if current_clause is not None and line and (is_list_item or not _heading_like(line)):
            text, last_page, index = _consume_bylaw_flow(lines, index)
            if text:
                current_clause.text = f"{current_clause.text}\n{text}"
            _extend_unit_span(current_clause, last_page)
            continue
        index += 1

    _require_profile_units(units, document.slug, "munsu_bylaws_v1")
    definitions = _definitions_from_units(units, document)
    references = _references_from_units(units, known_documents=known_documents or [])
    return LegalStructure(
        instrument_slug=document.slug,
        instrument_title=document.title,
        document_type=document.document_type,
        source_path=document.source_path,
        source_hash=extraction.source_hash,
        units=units,
        definitions=definitions,
        references=references,
        warnings=warnings,
    )


def _parse_munsu_policy(
    extraction: SourceExtraction,
    document: ManifestDocument,
    *,
    known_documents: list[ManifestDocument] | None = None,
) -> LegalStructure:
    instrument = _instrument_unit(extraction, document)
    units: list[LegalUnit] = [instrument]
    warnings: list[str] = []
    current_section: LegalUnit | None = None
    current_policy: LegalUnit | None = None
    current_clause: LegalUnit | None = None
    started = False
    lines = _profile_lines(extraction)
    skip_pdf_front_matter = extraction.provider == "local_pdf" and (extraction.provider_metadata.page_count or 0) > 10
    index = 0
    while index < len(lines):
        line, anchor, block_id = lines[index]
        if skip_pdf_front_matter and anchor.page is not None and anchor.page < 4:
            index += 1
            continue
        if _skip_profile_line(line):
            index += 1
            continue
        section_match = _POLICY_SECTION_RE.match(line)
        if section_match:
            started = True
            number = section_match.group("number")
            current_section = _profile_unit(
                document,
                unit_type="section",
                suffix=f"section-{_normalize_identifier(number)}",
                text=line,
                title=section_match.group("title").strip(),
                number=number,
                anchor=anchor,
                parent=instrument,
                source_block_id=block_id,
            )
            _append_profile_unit(units, current_section)
            current_policy = None
            current_clause = None
            index += 1
            continue
        if not started:
            index += 1
            continue
        roman_match = _POLICY_ROMAN_RE.match(line)
        if roman_match:
            if current_section is None:
                raise StructureRecordError("munsu_policy_v1 policy heading appeared before a Section heading")
            roman = roman_match.group("roman").upper()
            current_policy = _profile_unit(
                document,
                unit_type="policy",
                suffix=f"{current_section.slug}-policy-{_normalize_identifier(roman)}".removeprefix(f"{document.slug}-"),
                text=line,
                title=roman_match.group("title").strip(),
                number=roman,
                anchor=anchor,
                parent=current_section,
                source_block_id=block_id,
            )
            _append_profile_unit(units, current_policy)
            current_clause = None
            index += 1
            continue
        provision_match = _POLICY_PROVISION_RE.match(line)
        if provision_match:
            if current_policy is None:
                raise StructureRecordError("munsu_policy_v1 lettered provision appeared before a roman policy heading")
            clause_lines, index = _consume_profile_body(lines, index, start_pattern=_POLICY_PROVISION_RE)
            letter = provision_match.group("letter").lower()
            text = _join_profile_text(clause_lines)
            current_clause = _profile_unit(
                document,
                unit_type="clause",
                suffix=f"{current_policy.slug}-provision-{letter}".removeprefix(f"{document.slug}-"),
                text=text,
                title=f"{current_policy.title or current_policy.number} ({letter})",
                number=f"({letter})",
                anchor=anchor,
                parent=current_policy,
                source_block_id=block_id,
            )
            _append_profile_unit(units, current_clause)
            continue
        adopted_match = _ADOPTED_RE.match(line)
        amended_match = _AMENDED_RE.match(line)
        if adopted_match or amended_match:
            if current_policy is None:
                raise StructureRecordError("munsu_policy_v1 date line appeared before a roman policy heading")
            if adopted_match:
                current_policy.metadata["adopted_date"] = adopted_match.group("value").strip()
            if amended_match:
                current_policy.metadata["amended_dates"] = amended_match.group("value").strip()
            _propagate_policy_metadata(units, current_policy)
            index += 1
            continue
        if current_clause and line and not _heading_like(line):
            current_clause.text = _join_profile_text([current_clause.text, line])
        index += 1

    _require_profile_units(units, document.slug, "munsu_policy_v1")
    definitions = _definitions_from_units(units, document)
    references = _references_from_units(units, known_documents=known_documents or [])
    return LegalStructure(
        instrument_slug=document.slug,
        instrument_title=document.title,
        document_type=document.document_type,
        source_path=document.source_path,
        source_hash=extraction.source_hash,
        units=units,
        definitions=definitions,
        references=references,
        warnings=warnings,
    )


def _profile_lines(extraction: SourceExtraction) -> list[tuple[str, SourceAnchor, str]]:
    lines: list[tuple[str, SourceAnchor, str]] = []
    for block in extraction.blocks:
        for offset, raw_line in enumerate(block.text.splitlines()):
            line = _clean_profile_line(raw_line)
            if not line:
                continue
            anchor = SourceAnchor(
                page=block.anchor.page,
                original_page=block.anchor.original_page,
                line_start=block.anchor.line_start + offset if block.anchor.line_start is not None else None,
                line_end=block.anchor.line_start + offset if block.anchor.line_start is not None else None,
                bbox=block.anchor.bbox,
            )
            lines.append((line, anchor, block.block_id))
    return lines


def _clean_profile_line(value: str) -> str:
    value = value.replace("\u200b", " ").replace("\ufeff", " ")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", value).strip()


def _skip_profile_line(line: str) -> bool:
    if not line:
        return True
    if line.isdigit():
        return True
    lowered = line.lower()
    return lowered in {"table of contents"} or lowered.startswith("last amended:")


def _heading_like(line: str) -> bool:
    return bool(
        _BYLAW_PART_RE.match(line)
        or _BYLAW_SECTION_RE.match(line)
        or _POLICY_SECTION_RE.match(line)
        or _POLICY_ROMAN_RE.match(line)
        or _POLICY_PROVISION_RE.match(line)
        or _ADOPTED_RE.match(line)
        or _AMENDED_RE.match(line)
        or _PROFILE_NUMBERED_CLAUSE_RE.match(line)
    )


def _is_bylaw_section_heading(
    line: str,
    lines: list[tuple[str, SourceAnchor, str]],
    index: int,
) -> bool:
    match = _BYLAW_SECTION_RE.match(line)
    if not match:
        return False
    remainder = match.group("title").strip()
    if remainder and (remainder.isupper() or len(remainder.split()) <= 6):
        return True
    if not remainder and index + 1 < len(lines):
        candidate = lines[index + 1][0]
        if not candidate or _heading_like(candidate) or _BYLAW_LIST_ITEM_RE.match(candidate):
            return False
        # Two-line lettered headings carry a short title on the next line. The
        # source titles are not always fully upper-case (Part I Section I is
        # "By LAWS"), so accept any short title-like line containing capitals.
        return len(candidate.split()) <= 6 and any(ch.isupper() for ch in candidate)
    return False


def _classify_list_marker(marker: str, alpha_next: str) -> str:
    """Disambiguate single-letter markers that are both alpha and roman (c, d, i, l, m, v, x).

    Lower-alpha lists advance sequentially, so a marker equal to the next
    expected alpha letter is an alpha item (e.g. "i." after "h."); otherwise a
    roman-charset letter starts or continues a nested roman list (e.g. "i."
    directly after "a.").
    """
    if len(marker) > 1:
        return "roman"
    if marker == alpha_next:
        return "alpha"
    if marker in _ROMAN_MARKER_CHARS:
        return "roman"
    return "alpha"


def _next_alpha(letter: str) -> str:
    return chr(ord(letter) + 1) if letter < "z" else letter


def _is_bylaw_break_line(
    line: str,
    lines: list[tuple[str, SourceAnchor, str]],
    index: int,
    *,
    clause_pattern: re.Pattern[str],
) -> bool:
    if _BYLAW_PART_RE.match(line) or _BYLAW_NUMBERED_SECTION_RE.match(line):
        return True
    if clause_pattern.match(line):
        return True
    if _ADOPTED_RE.match(line) or _AMENDED_RE.match(line):
        return True
    return bool(_BYLAW_SECTION_RE.match(line) and _is_bylaw_section_heading(line, lines, index))


def _consume_bylaw_flow(
    lines: list[tuple[str, SourceAnchor, str]],
    start: int,
    *,
    clause_pattern: re.Pattern[str] = _PROFILE_NUMBERED_CLAUSE_RE,
) -> tuple[str, int | None, int]:
    """Consume a bylaws clause or section-body run, preserving nested lists.

    Unlike the generic profile consumer, lower-alpha and lowercase roman list
    items are neither flattened into one paragraph nor treated as structural
    breaks: each item is kept on its own line (roman items indented two spaces
    under their alpha parent) so the source list hierarchy survives in the
    generated card. Plain lines continue the open item or the head text, and
    page-spanning continuations are followed. Returns the assembled text, the
    page of the last consumed line, and the index of the first unconsumed
    line.
    """
    head: list[str] = []
    items: list[tuple[str, list[str]]] = []
    current_item: tuple[str, list[str]] | None = None
    alpha_next = "a"
    last_page = lines[start][1].page
    index = start
    while index < len(lines):
        line, anchor, _block_id = lines[index]
        if _skip_profile_line(line):
            index += 1
            continue
        if index != start and _is_bylaw_break_line(line, lines, index, clause_pattern=clause_pattern):
            break
        item_start = index != start or not clause_pattern.match(line)
        for part in _split_runin_list_markers(line):
            item_match = _BYLAW_LIST_ITEM_RE.match(part) if item_start else None
            item_start = True
            if item_match:
                marker = item_match.group("marker")
                kind = _classify_list_marker(marker, alpha_next)
                if kind == "alpha":
                    alpha_next = _next_alpha(marker)
                    current_item = ("", [part])
                else:
                    current_item = ("  ", [part])
                items.append(current_item)
            elif current_item is not None:
                current_item[1].append(part)
            else:
                head.append(part)
        if anchor.page is not None:
            last_page = anchor.page if last_page is None else max(last_page, anchor.page)
        index += 1
    parts: list[str] = []
    head_text = re.sub(r"\s+", " ", " ".join(head)).strip()
    if head_text:
        parts.append(head_text)
    for indent, item_lines in items:
        parts.append(indent + re.sub(r"\s+", " ", " ".join(item_lines)).strip())
    return "\n".join(parts), last_page, index


def _anchor_with_span(anchor: SourceAnchor, last_page: int | None) -> SourceAnchor:
    if last_page is None or anchor.page is None or last_page <= anchor.page:
        return anchor
    return anchor.model_copy(update={"page_end": last_page})


def _extend_unit_span(unit: LegalUnit, last_page: int | None) -> None:
    if last_page is None or unit.anchor.page is None:
        return
    if last_page > (unit.anchor.page_end or unit.anchor.page):
        unit.anchor = unit.anchor.model_copy(update={"page_end": last_page})


def _consume_profile_body(
    lines: list[tuple[str, SourceAnchor, str]],
    start: int,
    *,
    start_pattern: re.Pattern[str],
) -> tuple[list[str], int]:
    collected = [lines[start][0]]
    index = start + 1
    while index < len(lines):
        line = lines[index][0]
        if _skip_profile_line(line):
            index += 1
            continue
        if (
            _BYLAW_PART_RE.match(line)
            or _BYLAW_SECTION_RE.match(line)
            or _POLICY_SECTION_RE.match(line)
            or _POLICY_ROMAN_RE.match(line)
            or start_pattern.match(line)
            or _ADOPTED_RE.match(line)
            or _AMENDED_RE.match(line)
        ):
            break
        collected.append(line)
        index += 1
    return collected, index


def _join_profile_text(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    return re.sub(r"\s+", " ", text).strip()


def _profile_unit(
    document: ManifestDocument,
    *,
    unit_type: UnitType,
    suffix: str,
    text: str,
    title: str | None,
    number: str | None,
    anchor: SourceAnchor,
    parent: LegalUnit,
    source_block_id: str,
    metadata: dict[str, str | list[str]] | None = None,
) -> LegalUnit:
    safe_suffix = _normalize_identifier(suffix)
    clause_id = f"{document.slug}-{safe_suffix}"
    return LegalUnit(
        clause_id=clause_id,
        slug=clause_id,
        unit_type=unit_type,
        text=text,
        title=title,
        number=number,
        anchor=anchor,
        parent_clause_id=parent.clause_id,
        parent_chain=[*parent.parent_chain, parent.clause_id] if not parent.is_top_level else [parent.clause_id],
        source_block_id=source_block_id,
        metadata=metadata or {},
    )


def _append_profile_unit(units: list[LegalUnit], unit: LegalUnit) -> None:
    existing = {item.clause_id for item in units}
    if unit.clause_id in existing:
        page = unit.anchor.page or len(units) + 1
        base = unit.clause_id
        candidate = f"{base}-p{page}"
        suffix = 2
        while candidate in existing:
            candidate = f"{base}-p{page}-{suffix}"
            suffix += 1
        unit.clause_id = candidate
        unit.slug = candidate
    units.append(unit)


def _propagate_policy_metadata(units: list[LegalUnit], policy: LegalUnit) -> None:
    if not policy.metadata:
        return
    for unit in units:
        if policy.clause_id in unit.parent_chain:
            unit.metadata.update(policy.metadata)


def _require_profile_units(units: list[LegalUnit], slug: str, profile: str) -> None:
    clause_count = sum(1 for unit in units if unit.unit_type == "clause")
    context_count = sum(1 for unit in units if unit.unit_type in {"part", "section", "policy"})
    if context_count == 0 or clause_count == 0:
        raise StructureRecordError(f"{profile} produced no usable hierarchy for {slug}")


def _definitions_from_units(
    units: list[LegalUnit],
    document: ManifestDocument,
) -> list[DefinitionRecord]:
    definitions: list[DefinitionRecord] = []
    seen_definition_terms: set[str] = set()
    for unit in units:
        if unit.unit_type != "clause":
            continue
        definition = _definition_from_unit(unit, document)
        if definition and definition.slug not in seen_definition_terms:
            definitions.append(definition)
            seen_definition_terms.add(definition.slug)
    return definitions


def _instrument_unit(extraction: SourceExtraction, document: ManifestDocument) -> LegalUnit:
    first_anchor = extraction.blocks[0].anchor if extraction.blocks else SourceAnchor()
    return LegalUnit(
        clause_id=document.slug,
        slug=document.slug,
        unit_type="instrument",
        text=document.title,
        title=document.title,
        anchor=first_anchor,
        is_top_level=True,
    )


def _heading_unit(
    block: SourceBlock,
    document: ManifestDocument,
    instrument: LegalUnit,
) -> LegalUnit | None:
    heading_text = _clean_heading_text(block)
    heading_match = _LABELLED_HEADING_RE.match(heading_text)
    if not heading_match:
        return None

    label = heading_match.group("label").lower()
    number = heading_match.group("number")
    title = heading_match.group("title")
    normalized_number = _normalize_identifier(number)
    clause_id = f"{document.slug}-{label}-{normalized_number}"
    return LegalUnit(
        clause_id=clause_id,
        slug=clause_id,
        unit_type=cast(UnitType, label),
        text=heading_text,
        title=title or heading_text,
        number=number,
        anchor=block.anchor,
        heading_path=list(block.heading_path),
        parent_clause_id=instrument.clause_id,
        parent_chain=[instrument.clause_id],
        source_block_id=block.block_id,
    )


def _body_units(
    block: SourceBlock,
    document: ManifestDocument,
    instrument: LegalUnit,
    current_heading: LegalUnit | None,
) -> list[LegalUnit]:
    units: list[LegalUnit] = []
    for offset, line in enumerate(block.text.splitlines()):
        unit_match = _NUMBERED_UNIT_RE.match(line)
        if not unit_match:
            continue

        number = unit_match.group("number")
        text = f"{number} {unit_match.group('text').strip()}"
        parent = current_heading or instrument
        parent_chain = [instrument.clause_id]
        if current_heading:
            parent_chain.append(current_heading.clause_id)

        units.append(
            LegalUnit(
                clause_id=f"{document.slug}-{_normalize_identifier(number)}",
                slug=f"{document.slug}-{_normalize_identifier(number)}",
                unit_type="clause",
                text=text,
                number=number,
                anchor=_line_anchor(block, offset),
                heading_path=list(block.heading_path),
                parent_clause_id=parent.clause_id,
                parent_chain=parent_chain,
                source_block_id=block.block_id,
            )
        )
    return units


def _definition_from_unit(
    unit: LegalUnit,
    document: ManifestDocument,
) -> DefinitionRecord | None:
    match = _QUOTED_DEFINITION_RE.match(unit.text)
    if not match:
        match = _UNQUOTED_DEFINITION_RE.match(unit.text)
    if not match:
        return None

    term = match.group("term").strip()
    return DefinitionRecord(
        term=term,
        slug=_slugify(term),
        instrument_slug=document.slug,
        source_unit_id=unit.clause_id,
        definition_text=match.group("definition").strip(),
        anchor=unit.anchor,
    )


def _references_from_units(
    units: list[LegalUnit],
    *,
    known_documents: list[ManifestDocument],
) -> list[ReferenceRecord]:
    references: list[ReferenceRecord] = []
    document_targets = _document_targets(known_documents)
    unit_targets = _unit_targets(units)
    for unit in units:
        if unit.unit_type != "clause":
            continue
        for reference_type, reference_text in _reference_matches(unit.text):
            resolved_slug = document_targets.get(_reference_key(reference_text))
            resolved_target_id = unit_targets.get(_unit_key(reference_text))
            references.append(
                ReferenceRecord(
                    reference_id=f"{unit.clause_id}-{reference_type}-{len(references) + 1}",
                    reference_type=reference_type,
                    source_unit_id=unit.clause_id,
                    reference_text=reference_text,
                    anchor=unit.anchor,
                    resolution_status=(
                        "resolved" if resolved_slug or resolved_target_id else "unresolved"
                    ),
                    resolved_target_id=resolved_target_id,
                    resolved_target_slug=resolved_slug,
                )
            )
    return references


def _reference_matches(text: str) -> list[tuple[ReferenceType, str]]:
    matches: list[tuple[ReferenceType, str]] = []
    for reference_type, pattern in _REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            matches.append((reference_type, match.group("target").strip()))
    return matches


def _document_targets(known_documents: list[ManifestDocument]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for known_document in known_documents:
        targets[_reference_key(known_document.title)] = known_document.slug
        targets[_reference_key(known_document.slug)] = known_document.slug
    return targets


def _unit_targets(units: list[LegalUnit]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for unit in units:
        targets[_unit_key(unit.clause_id)] = unit.clause_id
        if unit.number:
            targets[_unit_key(unit.number)] = unit.clause_id
            targets[_unit_key(f"section {unit.number}")] = unit.clause_id
    return targets


def _clean_heading_text(block: SourceBlock) -> str:
    if block.heading_path:
        return block.heading_path[-1].strip()
    return re.sub(r"^#{1,6}\s+", "", block.text).strip()


def _line_anchor(block: SourceBlock, offset: int) -> SourceAnchor:
    if block.anchor.line_start is None:
        return block.anchor
    line_number = block.anchor.line_start + offset
    return SourceAnchor(
        page=block.anchor.page,
        original_page=block.anchor.original_page,
        line_start=line_number,
        line_end=line_number,
        bbox=block.anchor.bbox,
    )


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", value.strip()).strip("-").lower()


def _reference_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _unit_key(value: str) -> str:
    normalized = re.sub(r"^(?:section|article|policy|clause)\s+", "", value.strip().lower())
    return _normalize_identifier(normalized)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "definition"
