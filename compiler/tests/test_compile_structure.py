import json
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


def test_compile_sources_writes_legal_structure_sidecars(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled-corpus"
    create_scaffold(workspace)

    result = compile_sources(workspace, output)

    structure_path = output / ".raw" / "extraction" / "example-bylaw.structure.json"
    assert structure_path in result.structure_paths
    assert structure_path.is_file()
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    assert structure["instrument_slug"] == "example-bylaw"
    assert any(unit["clause_id"] == "example-bylaw-1.1" for unit in structure["units"])
    assert any(
        definition["term"] == "Recognized member"
        for definition in structure["definitions"]
    )
    assert any(
        reference["reference_type"] == "read_with"
        and reference["source_unit_id"] == "example-bylaw-1.3"
        for reference in structure["references"]
    )


def test_compile_cli_writes_structure_sidecars_with_validation_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled-corpus"
    create_scaffold(workspace)

    result = runner.invoke(app, ["compile", str(workspace), str(output)])

    assert result.exit_code == 0, result.output
    assert (output / ".raw" / "extraction" / "example-bylaw.structure.json").is_file()

    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "init" in help_result.output
    assert "compile" in help_result.output
    assert "validate" in help_result.output
    assert "report" in help_result.output


def test_compile_accepts_injected_pdf_extractor_and_writes_structure_sidecar(
    tmp_path: Path,
) -> None:
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
                    text="1.1 Fictional scan text must remain source-grounded.",
                    anchor=SourceAnchor(page=1, original_page=1),
                    confidence=0.98,
                )
            ],
            warnings=[],
            provider_metadata=ProviderMetadata(provider="reducto", job_id="fake"),
            title=title,
        )

    result = compile_sources(
        workspace,
        tmp_path / "out",
        pdf_extractor=fake_pdf_extractor,
    )

    structure_path = tmp_path / "out" / ".raw" / "extraction" / "fictional-scanned-policy.structure.json"
    assert structure_path in result.structure_paths
    assert structure_path.is_file()
