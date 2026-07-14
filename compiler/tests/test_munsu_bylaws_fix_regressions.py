"""Focused regressions for the MUNSU Bylaws Clause Card repair.

Unit tests exercise ``_parse_munsu_bylaws`` on synthetic extractions that
reproduce the source layout quirks behind the original P0/P1 findings:
two-line mixed-case lettered headings, numbered ``Section N:`` parents,
roman/alpha marker collisions, bare and run-in list markers, section-body
item runs, and page-spanning clauses.

Corpus-level tests gate the packaged fixed output (``fixed-generated/``)
and are skipped when those artifacts or pdfplumber are unavailable.
"""

from pathlib import Path
import re
import subprocess
import sys

import pytest

from legal_corpus.manifest import ManifestDocument
from legal_corpus.parsers.legal_structure import parse_legal_structure
from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
FIXED_CARDS = PACKAGE_ROOT / "fixed-generated" / "compiled" / "legal" / "clauses" / "bylaws"
SOURCE_PDF = PACKAGE_ROOT / "source" / "munsu-bylaws-2026.pdf"
AUDIT_TOOL = PACKAGE_ROOT / "tools" / "analyze_clause_cards.py"


def _document(slug: str = "fictional-bylaws") -> ManifestDocument:
    return ManifestDocument.model_validate(
        {
            "source_path": f"sources/{slug}.pdf",
            "document_type": "bylaw",
            "title": f"Fictional {slug}",
            "slug": slug,
            "jurisdiction": "CA-NL",
            "authority_rank": 40,
            "status": "active",
            "confidentiality": "public",
            "effective_date": None,
            "owner": "Legal Corpus Compiler tests",
            "version": "test-v1",
            "reviewed_by": None,
            "metadata_notes": [
                "effective_date is null because this is a fictional fixture.",
                "reviewed_by is null because no legal review applies to fictional fixtures.",
            ],
            "profile": "munsu_bylaws_v1",
            "corpus_id": slug,
            "corpus_version": "2026-07-14-test",
            "target_namespace": "fixture-staging",
            "classification": "public_governance_legal_reference",
            "sync_eligibility": "staging_only",
            "review_date": "2026-07-14",
        }
    )


def _extraction(pages: list[str], slug: str = "fictional-bylaws") -> SourceExtraction:
    blocks = [
        SourceBlock(
            block_id=f"{slug}-p{number}-text",
            block_type="body",
            text=text,
            anchor=SourceAnchor(page=number, original_page=number),
        )
        for number, text in enumerate(pages, start=1)
    ]
    return SourceExtraction(
        slug=slug,
        source_path=f"sources/{slug}.pdf",
        source_hash="a" * 64,
        provider="local_pdf",
        status="ok",
        title=f"Fictional {slug}",
        warnings=[],
        provider_metadata=ProviderMetadata(provider="local_pdf", page_count=len(pages)),
        blocks=blocks,
    )


def _units_by_id(pages: list[str]) -> dict:
    structure = parse_legal_structure(_extraction(pages), _document())
    return {unit.clause_id: unit for unit in structure.units}


def test_part_i_two_line_mixed_case_heading_not_swallowed() -> None:
    """A bare letter line followed by a mixed-case title (Section I 'By LAWS') is its own section."""
    pages = [
        "Part I: An Act\n"
        "H.\u200bCOUNCIL SEAL\n"
        "1.\u200b The seal of the Union is the seal of the Council\n"
        "2.\u200b Subject to the by-laws, all deeds shall be authenticated.\n"
        "I.\u200b\u200b\n"
        "By LAWS\n"
        "Subject to the by-laws, the Council may\n"
        "1.\u200b appoint committees; and\n"
        "2.\u200b make rules and regulations.\n"
        "J.\u200b\u200b\n"
        "EFFECTIVE BY LAWS\n"
        "Until repealed or amended under this Act\n"
        "1.\u200b the constitution continues.\n"
    ]
    units = _units_by_id(pages)
    section_i = units["fictional-bylaws-part-i-section-i"]
    assert section_i.unit_type == "section"
    assert section_i.title == "By LAWS"
    clause = units["fictional-bylaws-part-i-section-i-clause-1"]
    assert clause.parent_clause_id == "fictional-bylaws-part-i-section-i"
    # Section H keeps only its own clauses; no page-suffixed collision ids exist.
    assert "fictional-bylaws-part-i-section-h-clause-1" in units
    assert not [cid for cid in units if re.search(r"-p\d+$", cid)]
    section_h_text = units["fictional-bylaws-part-i-section-h-clause-2"].text
    assert "By LAWS" not in section_h_text


def test_part_ii_numbered_sections_parent_lettered_sections() -> None:
    """'Section N: Title' headings become true parents, including wrapped titles."""
    pages = [
        "Part II: Bylaws\n"
        "Section 8: Board of Directors Membership\n"
        "and Responsibilities\n"
        "A.\u200bREPRESENTATION\n"
        "Directors shall be elected to represent the following wards:\n"
        "1.\u200b Faculty Directors\n"
        "a.\u200b The following shall be elected:\n"
        "i.\u200b Humanities Representative\n"
        "ii.\u200b Business Representative\n"
    ]
    units = _units_by_id(pages)
    numbered = units["fictional-bylaws-part-ii-section-8"]
    assert numbered.unit_type == "section"
    assert numbered.number == "8"
    assert numbered.title == "Board of Directors Membership and Responsibilities"
    letter = units["fictional-bylaws-part-ii-section-8-a"]
    assert letter.parent_clause_id == numbered.clause_id
    assert "Directors shall be elected" in letter.text
    clause = units["fictional-bylaws-part-ii-section-8-a-clause-1"]
    assert clause.parent_clause_id == letter.clause_id
    assert "\na. The following shall be elected:" in clause.text
    assert "\n  i. Humanities Representative" in clause.text
    assert "\n  ii. Business Representative" in clause.text


def test_clauses_directly_under_numbered_section() -> None:
    """Sections without lettered subsections (Section 6 pattern) parent clauses directly."""
    pages = [
        "Part II: Bylaws\n"
        "Section 6: By-Elections\n"
        "1.\u200b By-elections shall be considered at the first meeting of the Board.\n"
        "2.\u200b Vacant positions shall be filled promptly.\n"
    ]
    units = _units_by_id(pages)
    clause = units["fictional-bylaws-part-ii-section-6-clause-1"]
    assert clause.parent_clause_id == "fictional-bylaws-part-ii-section-6"


def test_nested_alpha_roman_items_preserved_and_disambiguated() -> None:
    """Alpha items whose letters collide with roman charset (c, d, i, l, m) stay alpha by sequence."""
    items = "".join(
        f"{letter}.\u200b duty item {letter};\n" for letter in "abcdefghijklm"
    )
    pages = [
        "Part II: Bylaws\n"
        "Section 8: Board\n"
        "B.\u200bDUTIES AND RESPONSIBILITIES\n"
        "1.\u200b All Directors shall:\n" + items + "2.\u200b Faculty Directors shall report.\n"
    ]
    units = _units_by_id(pages)
    clause = units["fictional-bylaws-part-ii-section-8-b-clause-1"]
    for letter in "abcdefghijklm":
        assert f"\n{letter}. duty item {letter};" in clause.text, letter
    # None of the sequence-continuing letters were mis-indented as roman items.
    assert "\n  i. duty item i;" not in clause.text
    assert "\n  l. duty item l;" not in clause.text


def test_clause_subitems_after_roman_collision_letters() -> None:
    """Section 7 Referendum Voting clause 4 keeps subitems a-d despite c./d. matching roman charset."""
    pages = [
        "Part II: Bylaws\n"
        "Section 7: Referenda\n"
        "C.\u200bREFERENDUM VOTING\n"
        "1.\u200b Voting shall be open to all members.\n"
        "4.\u200b Referendum voting shall have the following features:\n"
        "a.\u200b Measures to ensure that only members can vote;\n"
        "b.\u200b Measures to ensure that voters do not vote more than once;\n"
        "c.\u200b The option to vote for or against a motion;\n"
        "d.\u200b The option not to vote on all motions.\n"
        "5.\u200b A motion may only be passed by Referendum with quorum.\n"
    ]
    units = _units_by_id(pages)
    clause = units["fictional-bylaws-part-ii-section-7-c-clause-4"]
    for marker, fragment in (
        ("a", "only members can vote;"),
        ("b", "do not vote more than once;"),
        ("c", "for or against a motion;"),
        ("d", "not to vote on all motions."),
    ):
        assert f"\n{marker}. " in clause.text, marker
        assert fragment in clause.text
    assert clause.text.rstrip().endswith("The option not to vote on all motions.")


def test_page_spanning_clause_anchor_extends_to_continuation_page() -> None:
    """A clause continuing on the next page anchors page_start on the first and page_end on the last."""
    pages = [
        "Part II: Bylaws\n"
        "Section 12: Resource Centres\n"
        "D.\u200bSUPERVISORY BODY\n"
        "4.\u200b The Resource Centres' shall operate under a Resource Centres Board of\n",
        "Directors.\n"
        "5.\u200b The Board shall exist as a guiding body.\n",
    ]
    units = _units_by_id(pages)
    spanning = units["fictional-bylaws-part-ii-section-12-d-clause-4"]
    assert spanning.anchor.page == 1
    assert spanning.anchor.page_end == 2
    assert spanning.text.endswith("Board of Directors.")
    following = units["fictional-bylaws-part-ii-section-12-d-clause-5"]
    assert following.anchor.page == 2
    assert following.anchor.page_end is None


def test_bare_marker_lines_start_items() -> None:
    """A marker alone on its line (text following on the next line) starts a new item."""
    pages = [
        "Part II: Bylaws\n"
        "Section 4: Elections\n"
        "D.\u200bINTERIM\n"
        "3.\u200b Interim representatives listed below:\n"
        "vii.\u200b Medicine Representative: the Medical society;\n"
        "viii.\u200b\n"
        "Nursing Representative: the Nursing society;\n"
        "ix.\u200b Pharmacy Representative: the Pharmacy society;\n"
    ]
    units = _units_by_id(pages)
    clause = units["fictional-bylaws-part-ii-section-4-d-clause-3"]
    assert "\n  viii. Nursing Representative: the Nursing society;" in clause.text
    assert "society; viii." not in clause.text


def test_runin_markers_split_onto_own_lines() -> None:
    """Items continuing mid-line after ;/: are split onto their own lines without changing words."""
    pages = [
        "Part II: Bylaws\n"
        "Section 4: Elections\n"
        "D.\u200bINTERIM\n"
        "3.\u200b Interim representatives listed below:\n"
        "a.\u200b Faculty wards:\n"
        "i.\u200b Humanities Representative: the collective societies;\n"
        "b.\u200b Constituency wards: xiii.\u200b Indigenous Representative: the Resource Centre;\n"
    ]
    units = _units_by_id(pages)
    clause = units["fictional-bylaws-part-ii-section-4-d-clause-3"]
    assert "\nb. Constituency wards:" in clause.text
    assert "\n  xiii. Indigenous Representative: the Resource Centre;" in clause.text
    assert "wards: xiii." not in clause.text


def test_section_body_items_attach_to_section_not_previous_clause() -> None:
    """Clause-less item runs under a lettered section stay on the section card."""
    pages = [
        "Part II: Bylaws\n"
        "Section 7: Referenda\n"
        "A.\u200bINITIATING A REFERENDUM\n"
        "1.\u200b A referendum may be initiated at any time.\n"
        "B.\u200bREFERENDUM PROCEDURES\n"
        "a.\u200b A referendum may only take place in the Fall or Winter semesters.\n"
        "b.\u200b The referendum must be held promptly.\n"
        "c.\u200b The question shall be published by appropriate student media.\n"
        "C.\u200bREFERENDUM VOTING\n"
        "1.\u200b Voting shall be open to all members.\n"
    ]
    units = _units_by_id(pages)
    section_b = units["fictional-bylaws-part-ii-section-7-b"]
    for marker in "abc":
        assert f"\n{marker}. " in section_b.text, marker
    prior_clause = units["fictional-bylaws-part-ii-section-7-a-clause-1"]
    assert "Fall or Winter" not in prior_clause.text
    assert "student media" not in prior_clause.text


_corpus_available = FIXED_CARDS.is_dir() and SOURCE_PDF.exists()
try:  # pragma: no cover - environment probe only
    import pdfplumber  # noqa: F401

    _pdfplumber_available = True
except Exception:  # pragma: no cover
    _pdfplumber_available = False

corpus_gate = pytest.mark.skipif(
    not (_corpus_available and _pdfplumber_available),
    reason="fixed-generated corpus, source PDF, or pdfplumber unavailable",
)


@corpus_gate
def test_fixed_corpus_key_cards_structure() -> None:
    """The packaged fixed corpus realizes the specific P0 repairs the fix prompt names."""

    def read(cid: str) -> str:
        return (FIXED_CARDS / f"{cid}.md").read_text(encoding="utf-8")

    assert not list(FIXED_CARDS.glob("*-p[0-9]*.md")), "page-suffixed collision ids remain"

    section_i = read("munsu-bylaws-part-i-section-i")
    assert "parent_clause: munsu-bylaws-part-i" in section_i
    clause_i1 = read("munsu-bylaws-part-i-section-i-clause-1")
    assert "parent_clause: munsu-bylaws-part-i-section-i" in clause_i1

    span = read("munsu-bylaws-part-ii-section-12-d-clause-4")
    assert "source_page_start: 46" in span
    assert "source_page_end: 47" in span
    assert "Board of Directors." in span

    representation = read("munsu-bylaws-part-ii-section-8-a-clause-1")
    assert "\n  xiii. Music Students" in representation

    voting = read("munsu-bylaws-part-ii-section-7-c-clause-4")
    for marker in ("\na. ", "\nb. ", "\nc. ", "\nd. "):
        assert marker in voting

    duties = read("munsu-bylaws-part-ii-section-8-b-clause-1")
    for letter in "abcdefghijklm":
        assert f"\n{letter}. " in duties, letter


@corpus_gate
def test_fixed_corpus_reaudit_has_zero_p0_p1(tmp_path: Path) -> None:
    """The re-audit gate holds: zero P0 and zero P1 findings on the fixed corpus."""
    result = subprocess.run(
        [
            sys.executable,
            str(AUDIT_TOOL),
            "--outputs",
            str(tmp_path),
            "--fail-on-findings",
        ],
        capture_output=True,
        text=True,
        cwd=str(PACKAGE_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
