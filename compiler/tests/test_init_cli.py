from pathlib import Path

from typer.testing import CliRunner

from legal_corpus.cli import app
from legal_corpus.manifest import load_manifest


runner = CliRunner()


def test_init_creates_contract_workspace(tmp_path: Path) -> None:
    target = tmp_path / "workspace"

    result = runner.invoke(app, ["init", str(target)])

    assert result.exit_code == 0, result.output
    assert "Legal corpus scaffold created" in result.output
    assert (target / "sources" / "manifest.yaml").is_file()
    assert (target / "corpus" / "RESOLVER.md").is_file()
    assert (target / "corpus" / "schema.md").is_file()
    assert (target / "corpus" / "index.md").is_file()
    assert (target / "corpus" / "legal" / "clauses" / "legislation").is_dir()
    assert (target / "corpus" / ".raw" / "sources").is_dir()
    assert (target / "corpus" / ".raw" / "extraction").is_dir()
    assert (target / "corpus" / ".raw" / "provenance").is_dir()
    assert not (target / "corpus" / ".raw" / "warnings").exists()

    manifest = load_manifest(target / "sources" / "manifest.yaml")
    assert len(manifest.documents) == 4


def test_init_refuses_non_empty_target_without_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("do not replace", encoding="utf-8")

    result = runner.invoke(app, ["init", str(target)])

    assert result.exit_code != 0
    assert sentinel.read_text(encoding="utf-8") == "do not replace"
    assert not (target / "sources" / "manifest.yaml").exists()


def test_validation_commands_require_output_argument() -> None:
    for command in ("validate", "report"):
        result = runner.invoke(app, [command])
        assert result.exit_code != 0
        assert "Missing argument 'OUTPUT'" in result.output


def test_help_lists_compile_validate_and_report_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "compile" in result.output
    assert "validate" in result.output
    assert "report" in result.output
