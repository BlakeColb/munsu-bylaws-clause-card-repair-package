"""Build warning-register.json/.md for a compiled corpus.

Derives the register from the corpus's own ``legal/unresolved-references``
pages so the packet metadata always matches what the compiler actually
generated. Mirrors the original register schema (``metadata_only``,
``warning_count``, ``warnings[]`` with ``source_clause``/``warning_id``) and
additionally writes ``affected_clause`` for tooling that expects that key.

Usage:
    python tools/build_warning_register.py \
        [--corpus fixed-generated/compiled] [--out fixed-generated/review-packet]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(text[3:end]) or {}


def build(corpus_root: Path, out_dir: Path) -> dict:
    pages_dir = corpus_root / "legal" / "unresolved-references"
    warnings = []
    for page in sorted(pages_dir.glob("*.md")):
        meta = _frontmatter(page)
        reference_text = str(meta.get("reference_text") or "")
        warnings.append(
            {
                "path": page.relative_to(corpus_root).as_posix(),
                "reference_text_sha256": hashlib.sha256(reference_text.encode("utf-8")).hexdigest(),
                "reference_type": meta.get("reference_type"),
                "resolution_status": meta.get("resolution_status"),
                "sha256": hashlib.sha256(page.read_bytes()).hexdigest(),
                "source_clause": meta.get("source_clause"),
                "affected_clause": meta.get("source_clause"),
                "source_line_start": meta.get("source_line_start"),
                "source_line_end": meta.get("source_line_end"),
                "warning_id": meta.get("slug") or page.stem,
            }
        )
    register = {
        "metadata_only": True,
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "warning-register.json"
    json_path.write_text(json.dumps(register, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path = out_dir / "warning-register.md"
    lines = [
        "# Warning Register",
        "",
        f"Derived from `{corpus_root.as_posix()}/legal/unresolved-references/` ({len(warnings)} warning(s)).",
        "",
        "| warning_id | affected_clause | reference_type | resolution_status | path |",
        "| --- | --- | --- | --- | --- |",
    ]
    for w in warnings:
        lines.append(
            f"| {w['warning_id']} | {w['source_clause']} | {w['reference_type']} | {w['resolution_status']} | {w['path']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return register


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=PACKAGE_ROOT / "fixed-generated" / "compiled")
    parser.add_argument("--out", type=Path, default=PACKAGE_ROOT / "fixed-generated" / "review-packet")
    args = parser.parse_args()
    register = build(args.corpus.resolve(), args.out.resolve())
    print(json.dumps({"warning_count": register["warning_count"], "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
