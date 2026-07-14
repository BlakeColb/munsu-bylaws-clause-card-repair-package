"""Manifest-driven source compilation orchestration."""

from dataclasses import dataclass, field
from pathlib import Path
import shutil

from legal_corpus.exporters.gbrain import export_gbrain_corpus
from legal_corpus.extractors.markdown import extract_markdown
from legal_corpus.manifest import ManifestDocument, load_manifest
from legal_corpus.parsers.legal_structure import parse_legal_structure
from legal_corpus.providers.reducto import ReductoConfigurationError, ReductoProvider
from legal_corpus.source_records import (
    ProviderMetadata,
    SourceExtraction,
    SourceRecordError,
    SourceWarning,
)


class CompileError(RuntimeError):
    """Raised when source compilation cannot complete."""


@dataclass(frozen=True)
class CompileResult:
    """Summary of a source extraction compile run."""

    documents_compiled: int
    extraction_paths: list[Path] = field(default_factory=list)
    structure_paths: list[Path] = field(default_factory=list)
    export_paths: list[Path] = field(default_factory=list)
    provenance_paths: list[Path] = field(default_factory=list)
    import_manifest_path: Path | None = None
    generated_file_count: int = 0
    warning_count: int = 0
    structure_warning_count: int = 0


def compile_sources(
    source_root: Path,
    output_root: Path,
    *,
    pdf_extractor=None,
) -> CompileResult:
    """Compile source files into raw extraction sidecars."""
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    manifest = load_manifest(source_root / "sources" / "manifest.yaml")
    raw_sources = output_root / ".raw" / "sources"
    raw_sources.mkdir(parents=True, exist_ok=True)

    extraction_paths: list[Path] = []
    structure_paths: list[Path] = []
    extractions: list[SourceExtraction] = []
    structures = []
    warning_count = 0
    structure_warning_count = 0
    for document in manifest.documents:
        source_path = _resolve_source_path(source_root, document)
        raw_destination = _raw_source_destination(raw_sources, document, source_path)
        shutil.copy2(source_path, raw_destination)

        extraction = _extract_document(
            source_path,
            document,
            pdf_extractor=pdf_extractor,
        )
        text_extension = ".md" if source_path.suffix.lower() in {".md", ".markdown"} else ".txt"
        written = extraction.write_sidecars(output_root, text_extension=text_extension)
        extraction_paths.append(written.metadata_path)
        extractions.append(extraction)
        warning_count += len(extraction.warnings)

        structure = parse_legal_structure(
            extraction,
            document,
            known_documents=manifest.documents,
        )
        structure_written = structure.write_sidecar(output_root)
        structure_paths.append(structure_written.structure_path)
        structures.append(structure)
        structure_warning_count += len(structure.warnings)

    export_result = export_gbrain_corpus(
        output_root,
        documents=manifest.documents,
        extractions=extractions,
        structures=structures,
        source_manifest_hash=_file_hash(source_root / "sources" / "manifest.yaml"),
    )

    return CompileResult(
        documents_compiled=len(manifest.documents),
        extraction_paths=extraction_paths,
        structure_paths=structure_paths,
        export_paths=[
            (output_root / path).resolve() for path in export_result.markdown_paths
        ],
        provenance_paths=export_result.provenance_paths,
        import_manifest_path=export_result.import_manifest_path,
        generated_file_count=len(export_result.files),
        warning_count=warning_count,
        structure_warning_count=structure_warning_count,
    )


def _extract_document(
    source_path: Path,
    document: ManifestDocument,
    *,
    pdf_extractor,
) -> SourceExtraction:
    suffix = source_path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return extract_markdown(
            source_path,
            slug=document.slug,
            source_path=document.source_path,
            title=document.title,
        )

    if suffix == ".pdf":
        if pdf_extractor is None:
            try:
                provider = ReductoProvider()
            except ReductoConfigurationError:
                return _missing_provider_key_extraction(source_path, document)
            return provider.extract_pdf(
                source_path,
                slug=document.slug,
                source_path=document.source_path,
                title=document.title,
            )
        if hasattr(pdf_extractor, "extract_pdf"):
            return pdf_extractor.extract_pdf(
                source_path,
                slug=document.slug,
                source_path=document.source_path,
                title=document.title,
            )
        return pdf_extractor(
            source_path,
            slug=document.slug,
            source_path=document.source_path,
            title=document.title,
        )

    raise CompileError(f"Unsupported source extension for {document.source_path}")


def _resolve_source_path(source_root: Path, document: ManifestDocument) -> Path:
    candidate = (source_root / document.source_path).resolve()
    try:
        candidate.relative_to(source_root)
    except ValueError as error:
        raise CompileError(
            f"Manifest source_path {document.source_path!r} escapes the source root"
        ) from error
    if not candidate.is_file():
        raise CompileError(f"Manifest source_path {document.source_path!r} does not exist")
    return candidate


def _raw_source_destination(
    raw_sources: Path,
    document: ManifestDocument,
    source_path: Path,
) -> Path:
    if "/" in document.slug or "\\" in document.slug or ".." in document.slug:
        raise CompileError(f"unsafe document slug for raw source copy: {document.slug}")
    destination = (raw_sources / f"{document.slug}{source_path.suffix.lower()}").resolve()
    try:
        destination.relative_to(raw_sources.resolve())
    except ValueError as error:
        raise CompileError(f"raw source destination escapes output root: {document.slug}") from error
    return destination


def _missing_provider_key_extraction(
    source_path: Path,
    document: ManifestDocument,
) -> SourceExtraction:
    warning = SourceWarning(
        category="missing_provider_key",
        severity="error",
        message="REDUCTO_API_KEY is required for live Reducto PDF extraction.",
    )
    return SourceExtraction(
        slug=document.slug,
        title=document.title,
        source_path=document.source_path,
        source_hash=_file_hash(source_path),
        provider="reducto",
        status="failed",
        blocks=[],
        warnings=[warning],
        provider_metadata=ProviderMetadata(
            provider="reducto",
            warnings=[warning.category],
            error_category=warning.category,
        ),
    )


def _file_hash(path: Path) -> str:
    from hashlib import sha256

    return sha256(path.read_bytes()).hexdigest()
