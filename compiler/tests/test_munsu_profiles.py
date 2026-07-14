from pathlib import Path

import yaml
from typer.testing import CliRunner

from legal_corpus.cli import app
from legal_corpus.compiler import compile_sources
from legal_corpus.extractors.local_pdf import LocalPdfExtractor
from legal_corpus.manifest import ManifestDocument
from legal_corpus.parsers.legal_structure import parse_legal_structure
from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
)
from legal_corpus.validators.gbrain import validate_gbrain_corpus


runner = CliRunner()


def document(*, slug: str, profile: str, document_type: str, namespace: str) -> ManifestDocument:
    return ManifestDocument.model_validate(
        {
            "source_path": f"sources/{slug}.pdf",
            "document_type": document_type,
            "title": f"Fictional {slug}",
            "slug": slug,
            "jurisdiction": "CA-NL",
            "authority_rank": 40,
            "status": "active",
            "confidentiality": "public",
            "effective_date": None,
            "owner": "Legal Corpus Compiler tests",
            "version": "test-v1",
            "reviewed_by": None,
            "metadata_notes": [
                "effective_date is null because this is a fictional public profile fixture.",
                "reviewed_by is null because no legal review applies to fictional fixtures.",
            ],
            "profile": profile,
            "corpus_id": slug,
            "corpus_version": "2026-07-13-test",
            "target_namespace": namespace,
            "classification": "public_governance_legal_reference",
            "sync_eligibility": "staging_only",
            "review_date": "2026-07-13",
        }
    )


def extraction(slug: str, text: str) -> SourceExtraction:
    return SourceExtraction(
        slug=slug,
        source_path=f"sources/{slug}.pdf",
        source_hash="a" * 64,
        provider="local_pdf",
        status="ok",
        title=f"Fictional {slug}",
        warnings=[],
        provider_metadata=ProviderMetadata(provider="local_pdf", page_count=1),
        blocks=[
            SourceBlock(
                block_id=f"{slug}-p1-text",
                block_type="body",
                text=text,
                anchor=SourceAnchor(page=1, original_page=1),
            )
        ],
    )


def test_munsu_bylaws_profile_preserves_part_section_clause_hierarchy() -> None:
    doc = document(
        slug="munsu-bylaws-v1",
        profile="munsu_bylaws_v1",
        document_type="bylaw",
        namespace="munsu-bylaws-public-staging-v1",
    )
    structure = parse_legal_structure(
        extraction(
            doc.slug,
            "\n".join(
                [
                    "Part I: CONSTITUTION",
                    "An Act to Incorporate Fictional Students Union",
                    "A. TITLE",
                    "This Act may be cited as the Fictional Act.",
                    "B. INTERPRETATION",
                    '1. "by-laws" means by-laws under this Act;',
                    "D. OBJECTIVES",
                    "1. promote fictional student life;",
                ]
            ),
        ),
        doc,
    )

    ids = [unit.clause_id for unit in structure.units]
    assert "munsu-bylaws-v1-part-i" in ids
    assert "munsu-bylaws-v1-part-i-section-b" in ids
    assert "munsu-bylaws-v1-part-i-section-b-clause-1" in ids
    clause = next(unit for unit in structure.units if unit.clause_id.endswith("section-b-clause-1"))
    assert clause.parent_clause_id == "munsu-bylaws-v1-part-i-section-b"
    assert clause.parent_chain == [
        "munsu-bylaws-v1",
        "munsu-bylaws-v1-part-i",
        "munsu-bylaws-v1-part-i-section-b",
    ]
    assert structure.definitions[0].term == "by-laws"


def test_munsu_policy_profile_extracts_structured_dates() -> None:
    doc = document(
        slug="munsu-policies-v1",
        profile="munsu_policy_v1",
        document_type="policy",
        namespace="munsu-policies-public-staging-v1",
    )
    structure = parse_legal_structure(
        extraction(
            doc.slug,
            "\n".join(
                [
                    "Section 1: Positions/Stances",
                    "I. CREDIT CARD COMPANIES",
                    "(a) The fictional union will not solicit cards.",
                    "(b) The fictional union may create a space-use policy.",
                    "Adopted: March 2002",
                    "Amended: November 2024",
                ]
            ),
        ),
        doc,
    )

    policy = next(unit for unit in structure.units if unit.unit_type == "policy")
    clause = next(unit for unit in structure.units if unit.clause_id.endswith("provision-a"))
    assert policy.metadata["adopted_date"] == "March 2002"
    assert policy.metadata["amended_dates"] == "November 2024"
    assert clause.metadata["adopted_date"] == "March 2002"
    assert clause.metadata["amended_dates"] == "November 2024"


def test_local_pdf_extractor_reads_text_without_reducto(tmp_path: Path) -> None:
    fitz = __import__("fitz")
    pdf = tmp_path / "fixture.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Fictional PDF profile text")
    doc.save(str(pdf))
    doc.close()

    extraction_result = LocalPdfExtractor().extract_pdf(
        pdf,
        slug="fictional-pdf",
        source_path="sources/fictional-pdf.pdf",
        title="Fictional PDF",
    )

    assert extraction_result.provider == "local_pdf"
    assert extraction_result.provider_metadata.page_count == 1
    assert "Fictional PDF profile text" in extraction_result.exact_text()


def test_profile_compile_writes_staging_manifest_report_and_rollback(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = tmp_path / "compiled"
    (workspace / "sources").mkdir(parents=True)
    (workspace / "sources" / "fictional-bylaws.pdf").write_bytes(b"%PDF-1.4 fixture")
    (workspace / "sources" / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_path": "sources/fictional-bylaws.pdf",
                        "document_type": "bylaw",
                        "title": "Fictional Bylaws",
                        "slug": "fictional-bylaws",
                        "jurisdiction": "CA-NL",
                        "authority_rank": 40,
                        "status": "active",
                        "confidentiality": "public",
                        "effective_date": None,
                        "owner": "Legal Corpus Compiler tests",
                        "version": "test-v1",
                        "reviewed_by": None,
                        "metadata_notes": [
                            "effective_date is null because this is a fictional public fixture.",
                            "reviewed_by is null because no legal review applies to fictional fixtures.",
                        ],
                        "profile": "munsu_bylaws_v1",
                        "corpus_id": "fictional-bylaws",
                        "corpus_version": "test-v1",
                        "target_namespace": "munsu-bylaws-public-staging-v1",
                        "classification": "public_governance_legal_reference",
                        "sync_eligibility": "staging_only",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    class FakeExtractor:
        def extract_pdf(self, path: Path, *, slug: str, source_path: str, title: str):
            return extraction(
                slug,
                "Part I: CONSTITUTION\nA. TITLE\n1. A fictional clause is preserved.",
            )

    compile_sources(workspace, output, pdf_extractor=FakeExtractor())
    result = validate_gbrain_corpus(output, update_manifest=True)
    manifest = yaml.safe_load((output / "import-manifest.yaml").read_text(encoding="utf-8"))
    report = (output / "validation-report.json").read_text(encoding="utf-8")

    assert result.passed is True
    assert manifest["validation_status"] == "passed"
    assert manifest["sync_eligibility"] == "staging_only"
    assert manifest["target_namespace"] == "munsu-bylaws-public-staging-v1"
    assert (output / "ROLLBACK.md").is_file()
    assert "public_governance_legal_reference" in report


def test_config_check_reports_without_secret_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("REDUCTO_API_KEY=secret-test-value\n", encoding="utf-8")
    result = runner.invoke(app, ["config-check"])

    assert result.exit_code == 0
    assert "REDUCTO_API_KEY: configured" in result.output
    assert "secret-test-value" not in result.output
