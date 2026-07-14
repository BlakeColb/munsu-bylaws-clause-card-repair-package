"""Reducto OCR provider adapter."""

from hashlib import sha256
import os
from pathlib import Path
from typing import Any

from legal_corpus.source_records import (
    ProviderMetadata,
    SourceAnchor,
    SourceBlock,
    SourceExtraction,
    SourceWarning,
)


LOW_CONFIDENCE_THRESHOLD = 0.75


def build_parse_options() -> dict[str, Any]:
    """Return the Reducto parse options for degraded scanned PDFs."""
    return {
        "settings": {
            "ocr_system": "standard",
            "extraction_mode": "ocr",
            "return_ocr_data": True,
        },
        "enhance": {
            "agentic": [{"scope": "text"}],
        },
    }


class ReductoConfigurationError(RuntimeError):
    """Raised when Reducto cannot be configured safely."""


class ReductoProvider:
    """Reducto provider wrapper with fake-client injection for tests."""

    def __init__(self, client=None, api_key: str | None = None):
        if client is not None:
            self.client = client
            return

        resolved_key = api_key or os.environ.get("REDUCTO_API_KEY")
        if not resolved_key:
            raise ReductoConfigurationError(
                "REDUCTO_API_KEY is required for live Reducto PDF extraction"
            )

        self.client = _build_live_client(resolved_key)

    def extract_pdf(
        self,
        path: Path,
        *,
        slug: str,
        source_path: str,
        title: str | None = None,
    ) -> SourceExtraction:
        options = build_parse_options()
        try:
            upload = self.client.upload(file=path)
            upload_reference = _upload_reference(upload)
            response = self.client.parse.run(
                input=upload_reference,
                settings=options["settings"],
                enhance=options["enhance"],
            )
        except Exception as error:  # noqa: BLE001 - provider adapters normalize all SDK errors
            return _failed_extraction(path, slug, source_path, title, error, options)

        return _map_response(path, slug, source_path, title, response, options)


def _build_live_client(api_key: str):
    try:
        from reducto import Reducto
    except ImportError as error:
        raise ReductoConfigurationError(
            "Install the reductoai package before live Reducto extraction"
        ) from error
    return Reducto(api_key=api_key)


def _upload_reference(upload: Any) -> str:
    upload_data = _as_mapping(upload)
    for key in ("file_id", "url", "presigned_url"):
        value = upload_data.get(key)
        if value:
            return str(value)
    raise ReductoConfigurationError("Reducto upload did not return a file reference")


def _map_response(
    path: Path,
    slug: str,
    source_path: str,
    title: str | None,
    response: Any,
    options: dict[str, Any],
) -> SourceExtraction:
    data = _as_mapping(response)
    result = _as_mapping(data.get("result", {}))
    chunks = list(_as_sequence(result.get("chunks")))
    blocks: list[SourceBlock] = []
    warnings: list[SourceWarning] = []

    for chunk_index, chunk in enumerate(chunks, start=1):
        chunk_data = _as_mapping(chunk)
        provider_blocks = list(_as_sequence(chunk_data.get("blocks")))
        if not provider_blocks and chunk_data.get("content"):
            provider_blocks = [chunk_data]

        for block_index, provider_block in enumerate(provider_blocks, start=1):
            block_data = _as_mapping(provider_block)
            text = str(block_data.get("text") or block_data.get("content") or "")
            page = _int_or_none(block_data.get("page"))
            original_page = _int_or_none(block_data.get("original_page", page))
            bbox = _float_list(block_data.get("bbox"))
            confidence = _confidence_value(block_data)
            block_id = str(
                block_data.get("id")
                or f"{slug}-p{page or 'unknown'}-c{chunk_index}-b{block_index}"
            )

            blocks.append(
                SourceBlock(
                    block_id=block_id,
                    block_type=str(block_data.get("type") or "text"),
                    text=text,
                    anchor=SourceAnchor(
                        page=page,
                        original_page=original_page,
                        bbox=bbox,
                    ),
                    confidence=confidence,
                    bbox=bbox,
                    ocr=_as_mapping(block_data.get("ocr", {})),
                )
            )

            if not text.strip():
                warnings.append(
                    SourceWarning(
                        category="ocr_empty",
                        severity="warning",
                        message="OCR returned no text for a scanned page region.",
                        anchor=SourceAnchor(page=page, original_page=original_page, bbox=bbox),
                        confidence=confidence,
                    )
                )
            if _is_low_confidence(block_data, confidence):
                warnings.append(
                    SourceWarning(
                        category="ocr_low_confidence",
                        severity="warning",
                        message="OCR confidence is below the review threshold.",
                        anchor=SourceAnchor(page=page, original_page=original_page, bbox=bbox),
                        confidence=confidence,
                    )
                )

    status = "review_required" if warnings else "ok"
    usage = _as_mapping(data.get("usage", {}))
    provider_metadata = ProviderMetadata(
        provider="reducto",
        job_id=_string_or_none(data.get("job_id")),
        page_count=_int_or_none(usage.get("num_pages") or data.get("page_count")),
        duration=_float_or_none(data.get("duration")),
        settings=options,
        result_type=_string_or_none(result.get("type")),
        warnings=[warning.category for warning in warnings],
    )
    return SourceExtraction(
        slug=slug,
        title=title,
        source_path=source_path,
        source_hash=_file_hash(path),
        provider="reducto",
        status=status,
        blocks=blocks,
        warnings=warnings,
        provider_metadata=provider_metadata,
    )


def _failed_extraction(
    path: Path,
    slug: str,
    source_path: str,
    title: str | None,
    error: Exception,
    options: dict[str, Any],
) -> SourceExtraction:
    category = _error_category(error)
    provider_code = getattr(error, "status_code", None)
    warning = SourceWarning(
        category=category,
        severity="error",
        message=f"Reducto extraction failed with category {category}.",
        provider_code=provider_code,
    )
    return SourceExtraction(
        slug=slug,
        title=title,
        source_path=source_path,
        source_hash=_file_hash(path),
        provider="reducto",
        status="failed",
        blocks=[],
        warnings=[warning],
        provider_metadata=ProviderMetadata(
            provider="reducto",
            settings=options,
            warnings=[category],
            error_category=category,
        ),
    )


def _error_category(error: Exception) -> str:
    status_code = getattr(error, "status_code", None)
    if status_code is None and hasattr(error, "response"):
        status_code = getattr(error.response, "status_code", None)
    name = type(error).__name__.lower()
    message = str(error).lower()

    if status_code in {401, 403} or "auth" in name or "permission" in name:
        return "provider_auth"
    if status_code == 429 or "ratelimit" in name or "rate limit" in message:
        return "provider_rate_limit"
    if status_code in {408, 504} or "timeout" in name or "timed out" in message:
        return "provider_timeout"
    if status_code == 442 or "password" in message:
        return "pdf_password_protected"
    if status_code in {413, 415} or "corrupt" in message or "unsupported" in message:
        return "pdf_corrupt_or_unsupported"
    if "connection" in name:
        return "provider_connection"
    if status_code == 422 or "validation" in name:
        return "provider_validation"
    if status_code:
        return "provider_api_error"
    return "unknown_provider_error"


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _confidence_value(block: dict[str, Any]) -> float | None:
    for key in ("parse_confidence", "confidence_score", "score"):
        value = _float_or_none(block.get(key))
        if value is not None:
            return value
    confidence = block.get("confidence")
    if isinstance(confidence, (int, float)):
        return float(confidence)
    if isinstance(confidence, str):
        lowered = confidence.lower()
        if lowered == "high":
            return 1.0
        if lowered == "medium":
            return 0.75
        if lowered == "low":
            return 0.0
    return None


def _is_low_confidence(block: dict[str, Any], confidence: float | None) -> bool:
    label = str(block.get("confidence") or "").lower()
    if label == "low":
        return True
    return confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_list(value: Any) -> list[float] | None:
    if not isinstance(value, list):
        return None
    floats = [_float_or_none(item) for item in value]
    if any(item is None for item in floats):
        return None
    return [float(item) for item in floats if item is not None]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
