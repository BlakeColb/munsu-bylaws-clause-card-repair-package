from pathlib import Path
from pathlib import PurePosixPath
from textwrap import dedent

from legal_corpus.frontmatter import parse_frontmatter
from legal_corpus.manifest import load_manifest


class ScaffoldError(RuntimeError):
    """Raised when a Phase 1 scaffold cannot be created or validated."""


DIRECTORIES = [
    "sources",
    "corpus/legal/instruments/bylaws",
    "corpus/legal/instruments/policies",
    "corpus/legal/instruments/collective-agreements",
    "corpus/legal/instruments/legislation",
    "corpus/legal/clauses/bylaws",
    "corpus/legal/clauses/policies",
    "corpus/legal/clauses/collective-agreements",
    "corpus/legal/clauses/legislation",
    "corpus/legal/definitions",
    "corpus/legal/issue-briefs",
    "corpus/legal/unresolved-references",
    "corpus/.raw/sources",
    "corpus/.raw/extraction",
    "corpus/.raw/provenance",
    "tests/fixtures/sources",
    "tests/fixtures/expected-corpus/legal/instruments/bylaws",
    "tests/fixtures/expected-corpus/legal/instruments/policies",
    "tests/fixtures/expected-corpus/legal/instruments/collective-agreements",
    "tests/fixtures/expected-corpus/legal/instruments/legislation",
    "tests/fixtures/expected-corpus/legal/clauses/bylaws",
    "tests/fixtures/expected-corpus/legal/clauses/policies",
    "tests/fixtures/expected-corpus/legal/clauses/collective-agreements",
    "tests/fixtures/expected-corpus/legal/clauses/legislation",
    "tests/fixtures/expected-corpus/legal/definitions",
    "tests/fixtures/expected-corpus/legal/issue-briefs",
    "tests/fixtures/expected-corpus/legal/unresolved-references",
    "tests/fixtures/expected-corpus/.raw/sources",
    "tests/fixtures/expected-corpus/.raw/extraction",
    "tests/fixtures/expected-corpus/.raw/provenance",
]

MANIFEST_YAML = """\
documents:
  - source_path: "tests/fixtures/sources/example-bylaw.md"
    document_type: "bylaw"
    title: "Example Student Association Bylaw"
    slug: "example-bylaw"
    jurisdiction: "fictional"
    authority_rank: 40
    status: "active"
    confidentiality: "internal"
    effective_date: null
    owner: "Legal Corpus Compiler fixtures"
    version: "fixture-v1"
    reviewed_by: null
    metadata_notes:
      - "effective_date is null because this is an invented contract fixture."
      - "reviewed_by is null because no legal review applies to fictional fixtures."
  - source_path: "tests/fixtures/sources/example-policy.md"
    document_type: "policy"
    title: "Example Budget Notice Policy"
    slug: "example-policy"
    jurisdiction: "fictional"
    authority_rank: 30
    status: "active"
    confidentiality: "internal"
    effective_date: null
    owner: "Legal Corpus Compiler fixtures"
    version: "fixture-v1"
    reviewed_by: null
    metadata_notes:
      - "effective_date is null because this is an invented contract fixture."
      - "reviewed_by is null because no legal review applies to fictional fixtures."
  - source_path: "tests/fixtures/sources/example-collective-agreement.md"
    document_type: "collective_agreement"
    title: "Example Staff Collective Agreement"
    slug: "example-collective-agreement"
    jurisdiction: "fictional"
    authority_rank: 50
    status: "active"
    confidentiality: "restricted"
    effective_date: null
    owner: "Legal Corpus Compiler fixtures"
    version: "fixture-v1"
    reviewed_by: null
    metadata_notes:
      - "effective_date is null because this is an invented contract fixture."
      - "reviewed_by is null because no legal review applies to fictional fixtures."
  - source_path: "tests/fixtures/sources/example-legislation.md"
    document_type: "legislation"
    title: "Example Campus Safety Act"
    slug: "example-legislation"
    jurisdiction: "fictional"
    authority_rank: 90
    status: "active"
    confidentiality: "public"
    effective_date: null
    owner: "Legal Corpus Compiler fixtures"
    version: "fixture-v1"
    reviewed_by: null
    metadata_notes:
      - "effective_date is null because this is an invented contract fixture."
      - "reviewed_by is null because no legal review applies to fictional fixtures."
"""

RESOLVER_MD = """\
---
title: "Legal Corpus Resolver"
type: corpus_resolver
status: "phase_1_contract"
---
# Legal Corpus Resolver

Use this order when answering from the legal corpus:

1. Retrieve the exact clause or issue brief that matches the question.
2. Retrieve the parent chain before interpreting the clause.
3. Retrieve definitions used by the clause.
4. Retrieve exceptions, subject-to clauses, and read-with clauses.
5. Retrieve higher-authority instruments when a conflict is possible.
6. Answer only with citations to retrieved source text.
7. Say what support is missing when the corpus does not contain enough text.

Exact source text is the authority. Summaries, retrieval hints, and issue notes
are generated aids and must not replace quoted source language.
"""

SCHEMA_MD = """\
---
title: "Legal Corpus Schema"
type: corpus_schema
status: "phase_1_contract"
---
# Legal Corpus Schema

## Page Types

- legal_instrument
- legal_clause
- legal_definition
- unresolved_reference

## Link Verbs

- child_of
- parent_of
- defines
- uses_definition
- read_with
- exception_to
- supersedes
- higher_authority_than

## Manifest Fields

Every source manifest document requires source_path, document_type, title, slug,
jurisdiction, authority_rank, status, confidentiality, effective_date, owner,
version, reviewed_by, and metadata_notes.

Nullable legal metadata uses YAML null and must be explained in metadata_notes.
Unresolved references are explicit corpus pages, not silent parser failures.
"""

INDEX_MD = """\
---
title: "Legal Corpus Index"
type: corpus_index
status: "phase_1_contract"
---
# Legal Corpus Index

This is a fictional Phase 1 contract corpus for Legal Corpus Compiler.

It defines the expected folder shape, page types, raw provenance boundaries,
and fixture breadth for later compile, validation, and retrieval phases.

The corpus is keyword-first today and embedding-ready later because legal unit
metadata, authority, provenance, and source text are separated from summaries.
"""

SOURCE_FIXTURES = {
    "tests/fixtures/sources/example-bylaw.md": """\
# Fictional fixture: Example Student Association Bylaw

## Section 1 - Member Notices

1.1 The Association must keep a list of recognized members.

1.2 "Recognized member" means a student listed in the current member register.

1.3 Budget notices must be read with the Example Budget Notice Policy.
""",
    "tests/fixtures/sources/example-policy.md": """\
# Fictional fixture: Example Budget Notice Policy

## Policy 2 - Notice Timing

2.1 A budget notice must be posted three days before a finance meeting.

2.2 The notice must identify the meeting date, voting body, and affected fund.
""",
    "tests/fixtures/sources/example-collective-agreement.md": """\
# Fictional fixture: Example Staff Collective Agreement

## Article 4 - Schedule Changes

4.1 A schedule change must be given to the affected employee in writing.

4.2 This article does not create a public posting obligation.
""",
    "tests/fixtures/sources/example-legislation.md": """\
# Fictional fixture: Example Campus Safety Act

## Section 7 - Safety Notice

7.1 A campus organization must keep emergency exits clear during meetings.

7.2 The safety notice prevails over an inconsistent internal room policy.
""",
}

EXPECTED_CORPUS_FILES = {
    "tests/fixtures/expected-corpus/RESOLVER.md": RESOLVER_MD,
    "tests/fixtures/expected-corpus/schema.md": SCHEMA_MD,
    "tests/fixtures/expected-corpus/index.md": INDEX_MD,
    "tests/fixtures/expected-corpus/legal/instruments/bylaws/example-bylaw.md": """\
---
title: "Example Student Association Bylaw"
type: legal_instrument
instrument_slug: "example-bylaw"
document_type: "bylaw"
jurisdiction: "fictional"
authority_rank: 40
status: "active"
effective_date: null
confidentiality: "internal"
source_file: ".raw/sources/example-bylaw.md"
---
# Example Student Association Bylaw

Fictional fixture instrument for the Phase 1 corpus contract.

## Source Text

See `.raw/sources/example-bylaw.md`.
""",
    "tests/fixtures/expected-corpus/legal/instruments/policies/example-policy.md": """\
---
title: "Example Budget Notice Policy"
type: legal_instrument
instrument_slug: "example-policy"
document_type: "policy"
jurisdiction: "fictional"
authority_rank: 30
status: "active"
effective_date: null
confidentiality: "internal"
source_file: ".raw/sources/example-policy.md"
---
# Example Budget Notice Policy

Fictional fixture policy for budget notice cross-reference coverage.
""",
    "tests/fixtures/expected-corpus/legal/instruments/collective-agreements/example-collective-agreement.md": """\
---
title: "Example Staff Collective Agreement"
type: legal_instrument
instrument_slug: "example-collective-agreement"
document_type: "collective_agreement"
jurisdiction: "fictional"
authority_rank: 50
status: "active"
effective_date: null
confidentiality: "restricted"
source_file: ".raw/sources/example-collective-agreement.md"
---
# Example Staff Collective Agreement

Fictional fixture collective agreement for authority and confidentiality fields.
""",
    "tests/fixtures/expected-corpus/legal/instruments/legislation/example-legislation.md": """\
---
title: "Example Campus Safety Act"
type: legal_instrument
instrument_slug: "example-legislation"
document_type: "legislation"
jurisdiction: "fictional"
authority_rank: 90
status: "active"
effective_date: null
confidentiality: "public"
source_file: ".raw/sources/example-legislation.md"
---
# Example Campus Safety Act

Fictional fixture legislation that can be higher authority than internal rules.
""",
    "tests/fixtures/expected-corpus/legal/clauses/bylaws/example-bylaw-1.md": """\
---
title: "Example Bylaw 1 - Member Notices"
type: legal_clause
instrument_slug: "example-bylaw"
instrument_title: "Example Student Association Bylaw"
document_type: "bylaw"
jurisdiction: "fictional"
authority_rank: 40
status: "active"
effective_date: null
source_file: ".raw/sources/example-bylaw.md"
source_page_start: null
source_page_end: null
clause_id: "example-bylaw-1"
slug: "example-bylaw-1"
parent_clause: null
path:
  - "Example Student Association Bylaw"
  - "Section 1 - Member Notices"
definitions_used:
  - "recognized-member"
read_with:
  - "example-policy"
exceptions: []
supersedes: []
confidentiality: "internal"
---
# Example Bylaw 1 - Member Notices

## Compiled Truth

The bylaw fixture requires a member list and points budget notice questions to
the budget policy.

## Source Text

1.1 The Association must keep a list of recognized members.

1.2 "Recognized member" means a student listed in the current member register.

1.3 Budget notices must be read with the Example Budget Notice Policy.

## Legal Context

- Defines `recognized member`.
- Read with `Example Budget Notice Policy`.
""",
    "tests/fixtures/expected-corpus/legal/definitions/example-defined-term.md": """\
---
title: "Recognized Member"
type: legal_definition
term: "recognized member"
slug: "recognized-member"
instrument_slug: "example-bylaw"
source_clause: "example-bylaw-1"
status: "active"
confidentiality: "internal"
---
# Recognized Member

## Source Text

"Recognized member" means a student listed in the current member register.
""",
    "tests/fixtures/expected-corpus/legal/unresolved-references/example-unresolved-reference.md": """\
---
title: "Unresolved Reference - Campus Space Regulation 99"
type: unresolved_reference
slug: "campus-space-regulation-99"
source_clause: "example-bylaw-1"
reference_text: "Campus Space Regulation 99"
resolution_status: "unresolved"
confidentiality: "internal"
---
# Unresolved Reference - Campus Space Regulation 99

This fictional reference is intentionally unresolved so later validators prove
that missing cross-references are explicit instead of silently ignored.
""",
    "tests/fixtures/expected-corpus/.raw/sources/example-bylaw.md": """\
# Fictional fixture: Example Student Association Bylaw

## Section 1 - Member Notices

1.1 The Association must keep a list of recognized members.

1.2 "Recognized member" means a student listed in the current member register.

1.3 Budget notices must be read with the Example Budget Notice Policy.
""",
    "tests/fixtures/expected-corpus/.raw/extraction/example-bylaw.json": """\
{
  "source_path": "tests/fixtures/sources/example-bylaw.md",
  "extraction_method": "fictional-fixture",
  "page_start": null,
  "page_end": null,
  "warnings": []
}
""",
}

FILES = {
    "sources/manifest.yaml": MANIFEST_YAML,
    "corpus/RESOLVER.md": RESOLVER_MD,
    "corpus/schema.md": SCHEMA_MD,
    "corpus/index.md": INDEX_MD,
    **SOURCE_FIXTURES,
    **EXPECTED_CORPUS_FILES,
}

REQUIRED_SNIPPETS = {
    "tests/fixtures/expected-corpus/RESOLVER.md": "Retrieve the exact clause",
    "tests/fixtures/expected-corpus/schema.md": "higher_authority_than",
    "tests/fixtures/expected-corpus/index.md": "fictional",
}


def create_scaffold(target: Path) -> None:
    """Create a Phase 1 legal corpus scaffold."""
    if target.exists() and any(target.iterdir()):
        raise ScaffoldError(f"{target} is not empty")

    target.mkdir(parents=True, exist_ok=True)

    for directory in DIRECTORIES:
        _safe_child(target, directory).mkdir(parents=True, exist_ok=True)

    for relative_path, content in FILES.items():
        destination = _safe_child(target, relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(_normalize(content), encoding="utf-8")

    validate_scaffold(target)


def validate_scaffold(target: Path) -> None:
    """Validate the generated Phase 1 legal corpus scaffold."""
    missing = [
        path
        for path in [*DIRECTORIES, *FILES.keys()]
        if not _safe_child(target, path).exists()
    ]
    if missing:
        raise ScaffoldError(f"scaffold is missing required paths: {missing}")

    raw_children = {
        child.name for child in (target / "corpus" / ".raw").iterdir() if child.is_dir()
    }
    if raw_children != {"sources", "extraction", "provenance"}:
        raise ScaffoldError(
            "corpus/.raw must contain only sources, extraction, and provenance"
        )

    load_manifest(target / "sources" / "manifest.yaml")

    for relative_path, snippet in REQUIRED_SNIPPETS.items():
        text = _safe_child(target, relative_path).read_text(encoding="utf-8")
        if snippet not in text:
            raise ScaffoldError(f"{relative_path} does not contain {snippet!r}")

    for source_path in SOURCE_FIXTURES:
        text = _safe_child(target, source_path).read_text(encoding="utf-8")
        if "Fictional fixture" not in text:
            raise ScaffoldError(f"{source_path} is not labelled as fictional")

    for markdown_path in _frontmatter_markdown_files(target):
        frontmatter = parse_frontmatter(markdown_path)
        if not frontmatter.get("title"):
            raise ScaffoldError(f"{markdown_path} is missing a frontmatter title")


def _frontmatter_markdown_files(target: Path) -> list[Path]:
    roots = [
        target / "corpus",
        target / "tests" / "fixtures" / "expected-corpus",
    ]
    markdown_paths: list[Path] = []
    for root in roots:
        markdown_paths.extend(
            path
            for path in root.rglob("*.md")
            if ".raw" not in path.relative_to(target).parts
        )
    return sorted(markdown_paths)


def _safe_child(target: Path, relative_path: str) -> Path:
    parsed = PurePosixPath(relative_path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise ScaffoldError(f"unsafe scaffold path: {relative_path}")
    return target.joinpath(*parsed.parts)


def _normalize(content: str) -> str:
    return dedent(content).strip() + "\n"
