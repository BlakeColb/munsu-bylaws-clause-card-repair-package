from pathlib import Path

from typer.testing import CliRunner

from legal_corpus.cli import app
from legal_corpus.compiler import compile_sources
from legal_corpus.scaffold import create_scaffold
from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
)


runner = CliRunner()


def test_compile_cli_extracts_markdown_fixture_sidecars(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled-corpus"
    create_scaffold(workspace)

    result = runner.invoke(app, ["compile", str(workspace), str(output)])

    assert result.exit_code == 0, result.output
    assert "Compiled 4 source document" in result.output
    assert (output / ".raw" / "extraction" / "example-bylaw.json").is_file()
    assert (output / ".raw" / "extraction" / "example-bylaw.md").is_file()
    assert (output / ".raw" / "sources" / "example-bylaw.md").is_file()
    assert (output / "import-manifest.yaml").is_file()
    assert (
        output / "legal" / "clauses" / "bylaws" / "example-bylaw-1.1.md"
    ).is_file()


def test_compile_rejects_manifest_paths_outside_source_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sources").mkdir()
    (workspace / "sources" / "manifest.yaml").write_text(
        """
documents:
  - source_path: "../outside.md"
    document_type: "policy"
    title: "Escaping Fictional Policy"
    slug: "escaping-fictional-policy"
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
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["compile", str(workspace), str(tmp_path / "out")])

    assert result.exit_code != 0
    assert "escapes the source root" in result.output


def test_compile_accepts_injected_pdf_extractor_without_live_reducto(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sources").mkdir()
    pdf = workspace / "sources" / "fictional-scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fictional scan")
    (workspace / "sources" / "manifest.yaml").write_text(
        """
documents:
  - source_path: "sources/fictional-scan.pdf"
    document_type: "policy"
    title: "Fictional Scanned Policy"
    slug: "fictional-scanned-policy"
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
""".strip()
        + "\n",
        encoding="utf-8",
    )

    def fake_pdf_extractor(path: Path, *, slug: str, source_path: str, title: str):
        assert path == pdf
        return SourceExtraction(
            slug=slug,
            source_path=source_path,
            source_hash="fakehash",
            provider="reducto",
            status="ok",
            blocks=[
                SourceBlock(
                    block_id=f"{slug}-p1-b1",
                    block_type="paragraph",
                    text="Fictional PDF OCR text.",
                    anchor=SourceAnchor(page=1, original_page=1),
                    confidence=0.98,
                )
            ],
            warnings=[],
            provider_metadata=ProviderMetadata(provider="reducto", job_id="fake"),
        )

    result = compile_sources(
        workspace,
        tmp_path / "out",
        pdf_extractor=fake_pdf_extractor,
    )

    assert result.documents_compiled == 1
    assert (tmp_path / "out" / ".raw" / "extraction" / "fictional-scanned-policy.json").is_file()


def test_help_lists_compile_validate_and_report() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "compile" in result.output
    assert "validate" in result.output
    assert "report" in result.output
