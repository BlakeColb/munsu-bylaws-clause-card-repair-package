from legal_corpus.validation_records import (
    CorpusReport,
    GoldQuestion,
    GoldRetrievalResult,
    RetrievalHit,
    ValidationIssue,
    ValidationResult,
)


def test_validation_result_computes_status_counts() -> None:
    result = ValidationResult(
        root="compiled",
        markdown_count=3,
        document_count=1,
        legal_clause_count=1,
        definition_count=1,
        issues=[
            ValidationIssue(severity="warning", category="unresolved_reference", message="explicitly unresolved"),
            ValidationIssue(severity="error", category="broken_wikilink", message="missing target"),
        ],
    )

    assert result.passed is False
    assert result.blocking_error_count == 1
    assert result.warning_count == 1


def test_corpus_report_carries_validation_summary() -> None:
    report = CorpusReport(
        root="compiled",
        document_count=3,
        legal_clause_count=12,
        definition_count=2,
        unresolved_reference_count=1,
        validation_status="passed",
        warning_count=1,
    )

    assert report.validation_status == "passed"
    assert report.unresolved_reference_count == 1


def test_gold_retrieval_result_exposes_missing_targets() -> None:
    result = GoldRetrievalResult(
        question_id="q1",
        passed=False,
        hits=[RetrievalHit(target_id="example-bylaw-1.1", path="legal/clauses/bylaws/example-bylaw-1.1.md", score=3)],
        missing_clause_ids=["example-bylaw-1.2"],
        missing_parent_ids=["example-bylaw-section-1"],
        missing_definition_ids=["recognized-member"],
    )

    assert result.missing_targets == [
        "example-bylaw-1.2",
        "example-bylaw-section-1",
        "recognized-member",
    ]


def test_gold_question_requires_expected_targets() -> None:
    question = GoldQuestion(
        id="recognized-member-definition",
        question="What does recognized member mean?",
        expected_clause_ids=["example-bylaw-1.2"],
        expected_parent_ids=["example-bylaw-section-1"],
        expected_definition_ids=["recognized-member"],
    )

    assert question.expected_clause_ids == ["example-bylaw-1.2"]
