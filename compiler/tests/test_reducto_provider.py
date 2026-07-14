import json
from pathlib import Path

import pytest

from legal_corpus.providers.reducto import (
    ReductoConfigurationError,
    ReductoProvider,
    build_parse_options,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "reducto"


class FakeParse:
    def __init__(self, response: dict[str, object] | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeReducto:
    def __init__(self, response: dict[str, object] | None = None, error: Exception | None = None):
        self.upload_calls: list[Path] = []
        self.parse = FakeParse(response=response, error=error)

    def upload(self, *, file: Path):
        self.upload_calls.append(file)
        return {"file_id": "reducto://fictional-upload"}


class ProviderStatusError(Exception):
    def __init__(self, status_code: int, message: str = "fictional provider error"):
        super().__init__(message)
        self.status_code = status_code


def load_response(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_build_parse_options_use_scanned_pdf_ocr_settings() -> None:
    options = build_parse_options()

    assert options["settings"]["extraction_mode"] == "ocr"
    assert options["settings"]["ocr_system"] == "standard"
    assert options["settings"]["return_ocr_data"] is True
    assert {"scope": "text"} in options["enhance"]["agentic"]


def test_reducto_provider_maps_successful_response_without_live_api(tmp_path: Path) -> None:
    client = FakeReducto(load_response("scanned_success_response.json"))
    provider = ReductoProvider(client=client)
    pdf = tmp_path / "fictional-scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fictional test scan")

    extraction = provider.extract_pdf(
        pdf,
        slug="fictional-scan",
        source_path="sources/fictional-scan.pdf",
        title="Fictional Scan",
    )

    parse_call = client.parse.calls[0]
    assert parse_call["settings"]["extraction_mode"] == "ocr"
    assert parse_call["settings"]["return_ocr_data"] is True
    assert {"scope": "text"} in parse_call["enhance"]["agentic"]
    assert extraction.provider == "reducto"
    assert extraction.provider_metadata.job_id == "job-fictional-scan-001"
    assert extraction.provider_metadata.page_count == 2
    assert extraction.blocks[0].anchor.page == 1
    assert extraction.blocks[0].bbox == [0.11, 0.22, 0.70, 0.30]
    assert extraction.blocks[0].ocr["lines"][0]["confidence"] == 0.95


def test_reducto_provider_flags_low_confidence_and_empty_ocr(tmp_path: Path) -> None:
    provider = ReductoProvider(
        client=FakeReducto(load_response("low_confidence_response.json"))
    )
    pdf = tmp_path / "fictional-low.pdf"
    pdf.write_bytes(b"%PDF-1.4 fictional low confidence scan")

    extraction = provider.extract_pdf(
        pdf,
        slug="fictional-low",
        source_path="sources/fictional-low.pdf",
    )

    categories = {warning.category for warning in extraction.warnings}
    assert extraction.status == "review_required"
    assert "ocr_low_confidence" in categories
    assert "ocr_empty" in categories


@pytest.mark.parametrize(
    ("status_code", "category"),
    [
        (429, "provider_rate_limit"),
        (504, "provider_timeout"),
        (442, "pdf_password_protected"),
        (415, "pdf_corrupt_or_unsupported"),
        (401, "provider_auth"),
    ],
)
def test_reducto_provider_maps_provider_errors_to_warning_categories(
    tmp_path: Path,
    status_code: int,
    category: str,
) -> None:
    provider = ReductoProvider(
        client=FakeReducto(error=ProviderStatusError(status_code))
    )
    pdf = tmp_path / "fictional-error.pdf"
    pdf.write_bytes(b"%PDF-1.4 fictional error")

    extraction = provider.extract_pdf(
        pdf,
        slug="fictional-error",
        source_path="sources/fictional-error.pdf",
    )

    assert extraction.status == "failed"
    assert extraction.warnings[0].category == category


def test_reducto_provider_requires_key_when_constructing_live_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDUCTO_API_KEY", raising=False)

    with pytest.raises(ReductoConfigurationError) as error:
        ReductoProvider()

    assert "REDUCTO_API_KEY" in str(error.value)
