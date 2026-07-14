from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from legal_corpus.cli import app
from legal_corpus.compiler import compile_sources
from legal_corpus.export_records import ImportManifest
from legal_corpus.scaffold import create_scaffold


runner = CliRunner()


def compiled_output(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled"
    create_scaffold(workspace)
    compile_sources(workspace, output)
    return output


def test_validate_cli_passes_and_updates_manifest(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)

    result = runner.invoke(app, ["validate", str(output)])

    assert result.exit_code == 0
    assert "Validation passed" in result.output
    manifest = ImportManifest.model_validate(yaml.safe_load((output / "import-manifest.yaml").read_text(encoding="utf-8")))
    assert manifest.validation_status == "passed"
    assert manifest.sync_eligible is False


def test_validate_cli_fails_and_marks_manifest_failed(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    target = output / "legal" / "clauses" / "bylaws" / "example-bylaw-1.1.md"
    target.write_text(target.read_text(encoding="utf-8") + "\n[[missing-target]]\n", encoding="utf-8")

    result = runner.invoke(app, ["validate", str(output)])

    assert result.exit_code == 1
    assert "Validation failed" in result.output
    assert "broken_wikilink" in result.output
    manifest = ImportManifest.model_validate(yaml.safe_load((output / "import-manifest.yaml").read_text(encoding="utf-8")))
    assert manifest.validation_status == "failed"
    assert manifest.sync_eligible is False
