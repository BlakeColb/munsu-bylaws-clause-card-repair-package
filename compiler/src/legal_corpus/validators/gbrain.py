"""Validation for exported GBrain corpus folders."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import yaml

from legal_corpus.export_records import (
    ExportRecordError,
    ImportManifest,
    safe_output_path,
    sha256_file,
)
from legal_corpus.validation_records import ValidationResult
from legal_corpus.validation_records import ValidationIssue


WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

COMMON_REQUIRED = {
    "title",
    "type",
    "confidentiality",
    "generated_at",
    "wikilinks",
}
REQUIRED_BY_TYPE = {
    "legal_instrument": {
        *COMMON_REQUIRED,
        "instrument_slug",
        "document_type",
        "jurisdiction",
        "authority_rank",
        "status",
        "source_path",
        "source_hash",
        "child_clauses",
    },
    "legal_clause": {
        *COMMON_REQUIRED,
        "unit_type",
        "clause_id",
        "slug",
        "instrument_slug",
        "instrument_title",
        "document_type",
        "jurisdiction",
        "authority_rank",
        "status",
        "source_path",
        "source_hash",
        "parent_clause",
        "parent_chain",
        "child_clauses",
    },
    "legal_definition": {
        *COMMON_REQUIRED,
        "term",
        "slug",
        "instrument_slug",
        "source_clause",
        "status",
    },
    "unresolved_reference": {
        *COMMON_REQUIRED,
        "slug",
        "source_clause",
        "reference_type",
        "reference_text",
        "resolution_status",
        "instrument_slug",
    },
    "corpus_resolver": {
        *COMMON_REQUIRED,
        "status",
    },
    "corpus_schema": {
        *COMMON_REQUIRED,
        "status",
    },
    "corpus_index": {
        *COMMON_REQUIRED,
        "status",
    },
}


def validate_gbrain_corpus(output_root: Path, *, update_manifest: bool = False) -> ValidationResult:
    root = output_root.resolve()
    pages: list[_MarkdownPage] = []
    issues: list[ValidationIssue] = []

    for path in _syncable_markdown_paths(root):
        try:
            frontmatter, body = _parse_markdown_page(path)
        except ValueError as error:
            issues.append(
                _issue(
                    "error",
                    "frontmatter",
                    str(error),
                    root=root,
                    path=path,
                )
            )
            continue
        pages.append(_MarkdownPage(path=path, frontmatter=frontmatter, body=body))

    target_index = _target_index(pages)
    issues.extend(_duplicate_issues(pages, root=root))
    issues.extend(_required_field_issues(pages, root=root))
    issues.extend(_wikilink_issues(pages, target_index, root=root))
    issues.extend(_parent_issues(pages, target_index, root=root))
    issues.extend(_unresolved_reference_issues(pages, root=root))

    manifest, manifest_issues = _manifest_issues(root)
    issues.extend(manifest_issues)
    issues.extend(_provenance_warning_issues(root))

    status = manifest.validation_status if manifest else None
    result = _result_from_pages(root, pages, issues, status)
    if update_manifest:
        _write_validation_status(root, result.passed)
        result.validation_status = "passed" if result.passed else "failed"
        _write_validation_artifacts(root, result)
    return result


class _MarkdownPage:
    def __init__(self, *, path: Path, frontmatter: dict[str, Any], body: str) -> None:
        self.path = path
        self.frontmatter = frontmatter
        self.body = body


def _syncable_markdown_paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if ".raw" not in path.relative_to(root).parts
        and path.relative_to(root).as_posix() != "ROLLBACK.md"
    )


def _parse_markdown_page(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} does not start with YAML frontmatter")

    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise ValueError(f"{path} does not close YAML frontmatter")

    try:
        parsed = yaml.safe_load("\n".join(lines[1:closing_index])) or {}
    except yaml.YAMLError as error:
        raise ValueError(f"{path} has invalid YAML frontmatter: {error}") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} frontmatter must parse to a mapping")
    body = "\n".join(lines[closing_index + 1 :])
    return parsed, body


def _target_index(pages: list[_MarkdownPage]) -> set[str]:
    targets: set[str] = set()
    for page in pages:
        frontmatter = page.frontmatter
        for field in ("slug", "clause_id"):
            value = frontmatter.get(field)
            if isinstance(value, str) and value:
                targets.add(value)
        if frontmatter.get("type") == "legal_instrument":
            value = frontmatter.get("instrument_slug")
            if isinstance(value, str) and value:
                targets.add(value)
        targets.add(page.path.stem)
    return targets


def _duplicate_issues(pages: list[_MarkdownPage], *, root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_duplicate_field_issues(pages, field="slug", category="duplicate_slug", root=root))
    issues.extend(
        _duplicate_field_issues(
            pages,
            field="clause_id",
            category="duplicate_clause_id",
            root=root,
        )
    )
    return issues


def _duplicate_field_issues(
    pages: list[_MarkdownPage],
    *,
    field: str,
    category: str,
    root: Path,
) -> list[ValidationIssue]:
    seen: dict[str, Path] = {}
    issues: list[ValidationIssue] = []
    for page in pages:
        value = page.frontmatter.get(field)
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            issues.append(
                _issue(
                    "error",
                    category,
                    f"duplicate {field} '{value}'",
                    root=root,
                    path=page.path,
                    target=value,
                    clause_id=_clause_id(page),
                )
            )
        else:
            seen[value] = page.path
    return issues


def _required_field_issues(pages: list[_MarkdownPage], *, root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for page in pages:
        page_type = page.frontmatter.get("type")
        required = REQUIRED_BY_TYPE.get(page_type)
        if not required:
            issues.append(
                _issue(
                    "error",
                    "missing_required_field",
                    "frontmatter type is missing or unsupported",
                    root=root,
                    path=page.path,
                    clause_id=_clause_id(page),
                )
            )
            continue
        for field in sorted(required):
            if field not in page.frontmatter:
                issues.append(
                    _issue(
                        "error",
                        "missing_required_field",
                        f"missing required frontmatter field '{field}'",
                        root=root,
                        path=page.path,
                        target=field,
                        clause_id=_clause_id(page),
                    )
                )
    return issues


def _wikilink_issues(
    pages: list[_MarkdownPage],
    target_index: set[str],
    *,
    root: Path,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for page in pages:
        for target in _frontmatter_wikilinks(page.frontmatter) + _body_wikilinks(page.body):
            if target not in target_index:
                issues.append(
                    _issue(
                        "error",
                        "broken_wikilink",
                        f"wikilink target '{target}' does not resolve",
                        root=root,
                        path=page.path,
                        target=target,
                        clause_id=_clause_id(page),
                    )
                )
    return issues


def _frontmatter_wikilinks(frontmatter: dict[str, Any]) -> list[str]:
    value = frontmatter.get("wikilinks")
    if not isinstance(value, list):
        return []
    return [target for target in (_normalize_link(item) for item in value) if target]


def _body_wikilinks(body: str) -> list[str]:
    return [target for target in (_normalize_link(match) for match in WIKILINK_RE.findall(body)) if target]


def _normalize_link(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    target = value.strip()
    if not target:
        return None
    return target.split("|", 1)[0].split("#", 1)[0].strip()


def _parent_issues(
    pages: list[_MarkdownPage],
    target_index: set[str],
    *,
    root: Path,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for page in pages:
        if page.frontmatter.get("type") != "legal_clause":
            continue
        parent = page.frontmatter.get("parent_clause")
        if parent is None:
            continue
        if not isinstance(parent, str) or not parent:
            issues.append(
                _issue(
                    "error",
                    "missing_parent",
                    "parent_clause must be a target id or null",
                    root=root,
                    path=page.path,
                    clause_id=_clause_id(page),
                )
            )
            continue
        if parent not in target_index:
            issues.append(
                _issue(
                    "error",
                    "missing_parent",
                    f"parent_clause '{parent}' does not resolve",
                    root=root,
                    path=page.path,
                    target=parent,
                    clause_id=_clause_id(page),
                )
            )
    return issues


def _unresolved_reference_issues(pages: list[_MarkdownPage], *, root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for page in pages:
        if page.frontmatter.get("type") != "unresolved_reference":
            continue
        if page.frontmatter.get("resolution_status") == "unresolved":
            issues.append(
                _issue(
                    "warning",
                    "unresolved_reference",
                    "explicit unresolved reference page remains unresolved",
                    root=root,
                    path=page.path,
                    target=str(page.frontmatter.get("slug") or page.path.stem),
                    clause_id=_clause_id(page),
                )
            )
    return issues


def _manifest_issues(root: Path) -> tuple[ImportManifest | None, list[ValidationIssue]]:
    path = root / "import-manifest.yaml"
    if not path.is_file():
        return None, [
            ValidationIssue(
                severity="error",
                category="manifest_file",
                message="import-manifest.yaml is missing",
                path="import-manifest.yaml",
            )
        ]

    try:
        manifest = ImportManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, yaml.YAMLError) as error:
        return None, [
            ValidationIssue(
                severity="error",
                category="manifest_file",
                message=f"import-manifest.yaml is invalid: {error}",
                path="import-manifest.yaml",
            )
        ]

    issues: list[ValidationIssue] = []
    for file in manifest.files:
        try:
            generated = safe_output_path(root, file.path)
        except ExportRecordError as error:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="manifest_path",
                    message=str(error),
                    path=file.path,
                )
            )
            continue
        if not generated.is_file():
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="manifest_file",
                    message="manifest file entry is missing on disk",
                    path=file.path,
                )
            )
            continue
        actual_hash = sha256_file(generated)
        if actual_hash != file.sha256:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="manifest_hash",
                    message="manifest sha256 does not match generated file",
                    path=file.path,
                    clause_id=file.clause_id,
                )
            )
    return manifest, issues


def _provenance_warning_issues(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    provenance_root = root / ".raw" / "provenance"
    if not provenance_root.is_dir():
        return issues
    for path in sorted(provenance_root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            issues.append(
                _issue(
                    "warning",
                    "extraction_warning",
                    f"provenance sidecar could not be inspected: {error}",
                    root=root,
                    path=path,
                )
            )
            continue
        warnings = data.get("extraction_warnings")
        if not isinstance(warnings, list):
            continue
        for warning in warnings:
            issues.append(
                _issue(
                    "warning",
                    "extraction_warning",
                    f"source extraction warning: {warning}",
                    root=root,
                    path=path,
                    clause_id=data.get("source_unit_id"),
                )
            )
    return issues


def _result_from_pages(
    root: Path,
    pages: list[_MarkdownPage],
    issues: list[ValidationIssue],
    status: str | None,
) -> ValidationResult:
    return ValidationResult(
        root=str(root),
        issues=issues,
        markdown_count=len(pages),
        document_count=_count_type(pages, "legal_instrument"),
        legal_clause_count=_count_type(pages, "legal_clause"),
        definition_count=_count_type(pages, "legal_definition"),
        unresolved_reference_count=_count_type(pages, "unresolved_reference"),
        provenance_count=len(list((root / ".raw" / "provenance").glob("*.json")))
        if (root / ".raw" / "provenance").is_dir()
        else 0,
        extraction_warning_count=sum(1 for issue in issues if issue.category == "extraction_warning"),
        validation_status=status,
    )


def _write_validation_status(root: Path, passed: bool) -> None:
    path = root / "import-manifest.yaml"
    if not path.is_file():
        return
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest = ImportManifest.model_validate(raw)
    except (OSError, ValueError, yaml.YAMLError):
        return
    manifest.validation_status = "passed" if passed else "failed"
    path.write_text(
        yaml.safe_dump(
            manifest.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )


def _write_validation_artifacts(root: Path, result: ValidationResult) -> None:
    import json

    manifest_path = root / "import-manifest.yaml"
    manifest = None
    if manifest_path.is_file():
        try:
            manifest = ImportManifest.model_validate(yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
        except Exception:
            manifest = None
    report = {
        "validationStatus": result.validation_status or ("passed" if result.passed else "failed"),
        "syncEligibility": manifest.sync_eligibility if manifest else "blocked",
        "targetNamespace": manifest.target_namespace if manifest else None,
        "operatorApprovalRequired": manifest.operator_approval_required if manifest else True,
        "operatorApprovalId": None,
        "sensitivity": ",".join(manifest.confidentiality_scope) if manifest else "unknown",
        "contentClass": manifest.classification if manifest and manifest.classification else "legal-corpus",
        "compilerProcess": "legal-corpus-cli",
        "documentCount": result.document_count,
        "markdownCount": result.markdown_count,
        "legalClauseCount": result.legal_clause_count,
        "definitionCount": result.definition_count,
        "unresolvedReferenceCount": result.unresolved_reference_count,
        "provenanceCount": result.provenance_count,
        "warningCount": result.warning_count,
        "blockingErrorCount": result.blocking_error_count,
        "metadataOnly": True,
    }
    (root / "validation-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "ROLLBACK.md").write_text(
        "# Rollback Instructions\n\n"
        "This compiler bundle is file-based and read-only to Mycroft. If a staged import is later approved, rollback must use the exact import receipt and remove only pages/files declared by that receipt.\n\n"
        "Do not directly edit generated legal pages in GBrain. Correct source material through the Legal Corpus Compiler source manifest and rerun compile/validate.\n",
        encoding="utf-8",
    )


def _count_type(pages: list[_MarkdownPage], page_type: str) -> int:
    return sum(1 for page in pages if page.frontmatter.get("type") == page_type)


def _issue(
    severity: str,
    category: str,
    message: str,
    *,
    root: Path,
    path: Path,
    target: str | None = None,
    clause_id: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        category=category,
        message=message,
        path=path.relative_to(root).as_posix(),
        target=target,
        clause_id=clause_id,
    )


def _clause_id(page: _MarkdownPage) -> str | None:
    value = page.frontmatter.get("clause_id") or page.frontmatter.get("source_clause")
    return value if isinstance(value, str) else None
