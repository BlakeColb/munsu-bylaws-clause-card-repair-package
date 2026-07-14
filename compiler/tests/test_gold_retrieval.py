from __future__ import annotations

from pathlib import Path

from legal_corpus.compiler import compile_sources
from legal_corpus.scaffold import create_scaffold
from legal_corpus.retrieval_gold import evaluate_gold_questions, load_gold_questions


FIXTURE = Path(__file__).parent / "fixtures" / "gold-questions.yaml"


def compiled_output(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled"
    create_scaffold(workspace)
    compile_sources(workspace, output)
    return output


def test_load_gold_questions() -> None:
    questions = load_gold_questions(FIXTURE)

    assert [question.id for question in questions] == [
        "recognized-member-definition",
        "budget-notice-deadline",
        "safety-register-access",
    ]


def test_gold_questions_pass_against_compiled_fixture(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)

    results = evaluate_gold_questions(output, FIXTURE, top_k=8)

    assert results
    assert all(result.passed for result in results)


def test_gold_question_fails_when_direct_clause_is_missing(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    (output / "legal" / "clauses" / "bylaws" / "example-bylaw-1.2.md").unlink()

    result = evaluate_gold_questions(output, FIXTURE, top_k=8)[0]

    assert result.passed is False
    assert result.missing_clause_ids == ["example-bylaw-1.2"]


def test_gold_question_fails_when_parent_context_is_missing(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    (output / "legal" / "clauses" / "bylaws" / "example-bylaw-section-1.md").unlink()

    result = evaluate_gold_questions(output, FIXTURE, top_k=8)[0]

    assert result.passed is False
    assert result.missing_parent_ids == ["example-bylaw-section-1"]


def test_gold_question_fails_when_definition_page_is_missing(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    (output / "legal" / "definitions" / "recognized-member.md").unlink()

    result = evaluate_gold_questions(output, FIXTURE, top_k=8)[0]

    assert result.passed is False
    assert result.missing_definition_ids == ["recognized-member"]
