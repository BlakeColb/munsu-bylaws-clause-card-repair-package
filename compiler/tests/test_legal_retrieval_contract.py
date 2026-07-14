from __future__ import annotations

from pathlib import Path

from legal_corpus.compiler import compile_sources
from legal_corpus.scaffold import create_scaffold


def compiled_output(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled"
    create_scaffold(workspace)
    compile_sources(workspace, output)
    return output


def test_mycroft_legal_retrieval_contract_is_generated(tmp_path: Path) -> None:
    output = compiled_output(tmp_path)
    contract_text = "\n".join(
        (output / name).read_text(encoding="utf-8")
        for name in ("RESOLVER.md", "index.md")
    )

    for required in (
        "Mycroft Legal Retrieval Contract",
        "jurisdiction",
        "document_type",
        "authority_rank",
        "status",
        "effective_date",
        "exact clause plus parent context",
        "definitions, exceptions, cross-references, and higher-authority relationships",
        "validation_status: passed",
        "current corpus version",
        "citation/clause ID",
        "source version and effective date",
        "key exception or uncertainty",
        "escalation boundary",
        "Hindsight may retain only operational follow-up",
        "no durable legal conclusions",
    ):
        assert required in contract_text
