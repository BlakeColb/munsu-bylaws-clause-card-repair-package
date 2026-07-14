from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from legal_corpus.cli import app
from legal_corpus.compiler import compile_sources
from legal_corpus.scaffold import create_scaffold
from legal_corpus.reports import build_corpus_report, render_corpus_report


runner = CliRunner()


def compiled_output(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled"
    create_scaffold(workspace)
    compile_sources(workspace, output)
    return output


def test_report_renderer_includes_required_labels(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)

    rendered = render_corpus_report(build_corpus_report(output))

    assert "Documents:" in rendered
    assert "Legal clauses:" in rendered
    assert "Definitions:" in rendered
    assert "Unresolved references:" in rendered
    assert "Validation status:" in rendered
    assert "Warnings:" in rendered
    assert "production sync approved" not in rendered.lower()


def test_report_cli_prints_corpus_summary(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)

    result = runner.invoke(app, ["report", str(output)])

    assert result.exit_code == 0
    assert "Documents:" in result.output
    assert "Validation status:" in result.output
