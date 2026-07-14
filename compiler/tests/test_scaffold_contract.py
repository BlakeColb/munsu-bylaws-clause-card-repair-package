from pathlib import Path

from legal_corpus.frontmatter import parse_frontmatter
from legal_corpus.scaffold import create_scaffold, validate_scaffold


GENERATED_PATHS = [
    "sources/manifest.yaml",
    "corpus/RESOLVER.md",
    "corpus/schema.md",
    "corpus/index.md",
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
    "tests/fixtures/expected-corpus",
]


EXPECTED_FIXTURE_PATHS = [
    "tests/fixtures/sources/example-bylaw.md",
    "tests/fixtures/sources/example-policy.md",
    "tests/fixtures/sources/example-collective-agreement.md",
    "tests/fixtures/sources/example-legislation.md",
    "tests/fixtures/expected-corpus/RESOLVER.md",
    "tests/fixtures/expected-corpus/schema.md",
    "tests/fixtures/expected-corpus/index.md",
    "tests/fixtures/expected-corpus/legal/instruments/bylaws/example-bylaw.md",
    "tests/fixtures/expected-corpus/legal/instruments/policies/example-policy.md",
    "tests/fixtures/expected-corpus/legal/instruments/collective-agreements/example-collective-agreement.md",
    "tests/fixtures/expected-corpus/legal/instruments/legislation/example-legislation.md",
    "tests/fixtures/expected-corpus/legal/clauses/bylaws/example-bylaw-1.md",
    "tests/fixtures/expected-corpus/legal/definitions/example-defined-term.md",
    "tests/fixtures/expected-corpus/legal/unresolved-references/example-unresolved-reference.md",
    "tests/fixtures/expected-corpus/.raw/sources/example-bylaw.md",
    "tests/fixtures/expected-corpus/.raw/extraction/example-bylaw.json",
]


def test_scaffold_contains_required_contract_paths(tmp_path: Path) -> None:
    create_scaffold(tmp_path)

    missing = [path for path in GENERATED_PATHS if not (tmp_path / path).exists()]
    assert missing == []
    assert not (tmp_path / "corpus" / ".raw" / "warnings").exists()

    validate_scaffold(tmp_path)


def test_fixture_tree_exists_in_repository() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    missing = [path for path in EXPECTED_FIXTURE_PATHS if not (repo_root / path).exists()]

    assert missing == []


def test_source_fixtures_are_fictional() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source_paths = [
        repo_root / "tests" / "fixtures" / "sources" / "example-bylaw.md",
        repo_root / "tests" / "fixtures" / "sources" / "example-policy.md",
        repo_root / "tests" / "fixtures" / "sources" / "example-collective-agreement.md",
        repo_root / "tests" / "fixtures" / "sources" / "example-legislation.md",
    ]
    missing = [path for path in source_paths if not path.exists()]
    assert missing == []

    for source_path in source_paths:
        assert "Fictional fixture" in source_path.read_text(encoding="utf-8")


def test_expected_corpus_docs_are_operational() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected_corpus = repo_root / "tests" / "fixtures" / "expected-corpus"
    required_docs = [
        expected_corpus / "RESOLVER.md",
        expected_corpus / "schema.md",
        expected_corpus / "index.md",
    ]
    missing = [path for path in required_docs if not path.exists()]
    assert missing == []

    assert "Retrieve the exact clause" in (
        expected_corpus / "RESOLVER.md"
    ).read_text(encoding="utf-8")
    schema_text = (expected_corpus / "schema.md").read_text(encoding="utf-8")
    assert "legal_clause" in schema_text
    assert "higher_authority_than" in schema_text
    assert "fictional" in (expected_corpus / "index.md").read_text(encoding="utf-8")


def test_expected_corpus_markdown_frontmatter_parses() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected_corpus = repo_root / "tests" / "fixtures" / "expected-corpus"
    markdown_paths = sorted(
        path for path in expected_corpus.rglob("*.md") if ".raw" not in path.parts
    )
    assert markdown_paths

    for path in markdown_paths:
        frontmatter = parse_frontmatter(path)
        assert isinstance(frontmatter, dict)
        assert frontmatter.get("title")
