"""Production-readiness documents for generated legal corpora."""

from __future__ import annotations

from collections.abc import Sequence

import yaml

from legal_corpus.manifest import ManifestDocument


PRODUCTION_DOCS: tuple[tuple[str, str, str], ...] = (
    ("RESOLVER.md", "corpus_resolver", "Legal Corpus Resolver"),
    ("schema.md", "corpus_schema", "Legal Corpus Schema"),
    ("index.md", "corpus_index", "Legal Corpus Index"),
)

PAGE_TYPES = (
    "legal_instrument",
    "legal_clause",
    "legal_definition",
    "unresolved_reference",
)

LINK_TYPES = (
    "child_of",
    "parent_of",
    "defines",
    "uses_definition",
    "read_with",
    "exception_to",
    "supersedes",
    "higher_authority_than",
)


def render_production_documents(
    documents: Sequence[ManifestDocument],
    *,
    generated_at: str,
    source_manifest_hash: str,
) -> list[tuple[str, str]]:
    """Return generated root Markdown docs as (relative path, content)."""
    return [
        (
            "RESOLVER.md",
            _resolver_markdown(
                documents,
                generated_at=generated_at,
                source_manifest_hash=source_manifest_hash,
            ),
        ),
        ("schema.md", _schema_markdown(generated_at=generated_at)),
        (
            "index.md",
            _index_markdown(
                documents,
                generated_at=generated_at,
                source_manifest_hash=source_manifest_hash,
            ),
        ),
    ]


def render_schema_pack_suggestion() -> str:
    """Return reviewable GBrain schema-pack suggestion YAML."""
    data = {
        "api_version": "gbrain-schema-pack-v1",
        "name": "legal-corpus",
        "version": "0.1.0",
        "gbrain_min_version": "0.39.0",
        "status": "suggestion_requires_validation",
        "page_types": [
            {
                "name": "legal_instrument",
                "description": "One source legal instrument with document-level metadata.",
                "directory": "legal/instruments",
                "required_fields": [
                    "document_type",
                    "jurisdiction",
                    "authority_rank",
                    "status",
                    "effective_date",
                    "confidentiality",
                ],
            },
            {
                "name": "legal_clause",
                "description": "One parsed legal unit with exact source text and parent context.",
                "directory": "legal/clauses",
                "required_fields": [
                    "clause_id",
                    "instrument_slug",
                    "parent_chain",
                    "document_type",
                    "jurisdiction",
                    "authority_rank",
                    "status",
                    "effective_date",
                    "confidentiality",
                ],
            },
            {
                "name": "legal_definition",
                "description": "A defined term scoped to its source instrument.",
                "directory": "legal/definitions",
                "required_fields": ["term", "instrument_slug", "source_clause", "status"],
            },
            {
                "name": "unresolved_reference",
                "description": "An explicit unresolved cross-reference requiring review.",
                "directory": "legal/unresolved-references",
                "required_fields": [
                    "source_clause",
                    "reference_type",
                    "reference_text",
                    "resolution_status",
                ],
            },
        ],
        "link_types": [
            {
                "name": "child_of",
                "description": "Child legal unit belongs under a parent legal unit.",
            },
            {
                "name": "parent_of",
                "description": "Parent legal unit contains a child legal unit.",
            },
            {
                "name": "defines",
                "description": "Clause creates a defined term.",
            },
            {
                "name": "uses_definition",
                "description": "Clause depends on a defined term.",
            },
            {
                "name": "read_with",
                "description": "Clause must be read with another legal unit or instrument.",
            },
            {
                "name": "exception_to",
                "description": "Clause creates or records an exception relationship.",
            },
            {
                "name": "supersedes",
                "description": "Clause or instrument supersedes another legal authority.",
            },
            {
                "name": "higher_authority_than",
                "description": "Authority relationship for conflict-aware retrieval.",
            },
        ],
        "activation_notes": [
            "Run gbrain schema validate against this suggestion before use.",
            "The schema-pack suggestion requires human review before activation.",
            "Do not treat this file as an activated production pack.",
        ],
    }
    return (
        yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=False,
            default_flow_style=False,
        ).rstrip()
        + "\n"
    )


def _resolver_markdown(
    documents: Sequence[ManifestDocument],
    *,
    generated_at: str,
    source_manifest_hash: str,
) -> str:
    body = [
        "# Legal Corpus Resolver",
        "",
        "## Compiled Truth",
        "",
        "This corpus contains compiler-generated legal and governance pages. Exact source text remains authoritative, and generated summaries or hints are retrieval aids only.",
        "",
        "## Source Text",
        "",
        "Exact source text lives inside each legal clause page under `## Source Text` and in `.raw/provenance/` sidecars. Do not substitute resolver guidance for source clauses.",
        "",
        "## Retrieval Hints",
        "",
        "- Prefer keyword-first retrieval by clause ID, defined term, instrument title, and parent legal unit.",
        "- Filter by `document_type`, `jurisdiction`, `authority_rank`, `status`, `effective_date`, and `confidentiality` before ranking answer candidates.",
        "- Retrieve `legal_clause` pages with their parent chain, definitions, exceptions, cross-references, and authority relationships.",
        "",
        "## Mycroft Legal Retrieval Contract",
        "",
        "For legal or governance queries, Mycroft must search only the approved legal corpus by `jurisdiction`, `document_type`, `authority_rank`, `status`, and `effective_date` before answering.",
        "",
        "Mycroft must retrieve the exact clause plus parent context, then retrieve definitions, exceptions, cross-references, and higher-authority relationships before composing an answer.",
        "",
        "Mycroft must verify `validation_status: passed` and the current corpus version before presenting the result as usable. If either check fails, answer with the validation problem and do not provide a legal conclusion.",
        "",
        "Every answer must be source-grounded and informational. It must include citation/clause ID, source version and effective date, key exception or uncertainty, and an escalation boundary for interpretation or legal advice.",
        "",
        "Hindsight may retain only operational follow-up such as verifying policy version, preparing a draft, or seeking professional advice. Hindsight must store no durable legal conclusions.",
        "",
        "## Production Gate",
        "",
        "The future production path is `gbrain sync --repo <compiled-corpus>` followed by `gbrain embed --stale`, but production sync is blocked until external Mycroft/GBrain gates pass for reliability, read-only permissions, backup/restore, and traceability.",
        "",
        f"- Source manifest hash: `{source_manifest_hash}`.",
        f"- Documents covered: {len(documents)}.",
    ]
    return _markdown(
        _frontmatter(
            title="Legal Corpus Resolver",
            page_type="corpus_resolver",
            generated_at=generated_at,
            wikilinks=["schema", "index"],
        ),
        body,
    )


def _schema_markdown(*, generated_at: str) -> str:
    page_type_lines = [f"- `{page_type}`" for page_type in PAGE_TYPES]
    link_type_lines = [f"- `{link_type}`" for link_type in LINK_TYPES]
    body = [
        "# Legal Corpus Schema",
        "",
        "## Compiled Truth",
        "",
        "This schema guide documents the generated legal page types and link verbs for local validation and future GBrain schema-pack review.",
        "",
        "## Source Text",
        "",
        "`legal_clause` pages keep exact clause language under `## Source Text`; `## Compiled Truth` and `## Retrieval Hints` are generated aids and must not be treated as source law.",
        "",
        "## Page Types",
        "",
        *page_type_lines,
        "",
        "## Link Types",
        "",
        *link_type_lines,
        "",
        "## Embedding Targets",
        "",
        "- Embed `## Source Text` for exact legal language.",
        "- Embed `## Compiled Truth` only as a retrieval aid that points back to source text.",
        "- Embed `## Retrieval Hints` for keyword expansion, clause IDs, and instrument names.",
        "- Use frontmatter filters for `document_type`, `jurisdiction`, `authority_rank`, `status`, `effective_date`, and `confidentiality` before reranking.",
        "",
        "## Schema-Pack Suggestion",
        "",
        "The reviewable suggestion is `.raw/schema-pack/legal-corpus-pack.yaml`. Run `gbrain schema validate` before use; the schema-pack suggestion requires human review before activation.",
        "",
        "The future production path is `gbrain sync --repo <compiled-corpus>` followed by `gbrain embed --stale`, but production sync is blocked until external Mycroft/GBrain gates pass.",
    ]
    return _markdown(
        _frontmatter(
            title="Legal Corpus Schema",
            page_type="corpus_schema",
            generated_at=generated_at,
            wikilinks=["RESOLVER", "index"],
        ),
        body,
    )


def _index_markdown(
    documents: Sequence[ManifestDocument],
    *,
    generated_at: str,
    source_manifest_hash: str,
) -> str:
    document_lines = [
        f"- `{document.slug}`: {document.title} (`{document.document_type}`, authority rank `{document.authority_rank}`, status `{document.status}`)."
        for document in sorted(documents, key=lambda item: item.slug)
    ]
    body = [
        "# Legal Corpus Index",
        "",
        "## Compiled Truth",
        "",
        "This index summarizes the generated corpus for operators and retrieval systems. It is not legal advice and does not replace exact source text.",
        "",
        "## Source Text",
        "",
        "Open each clause page and inspect `## Source Text` plus `.raw/provenance/` before relying on a legal answer.",
        "",
        "## Retrieval Hints",
        "",
        "- Start with instrument and clause filters, then inspect parent context and definitions.",
        "- Use `document_type`, `jurisdiction`, `authority_rank`, `status`, `effective_date`, and `confidentiality` as filter metadata.",
        "",
        "## Documents",
        "",
        *document_lines,
        "",
        "## Mycroft Legal Retrieval Contract",
        "",
        "Mycroft must use the resolver contract before answering legal/governance questions and must include citation/clause ID, source version and effective date, key exception or uncertainty, and an escalation boundary.",
        "",
        "Hindsight may retain only operational follow-up and no durable legal conclusions.",
        "",
        "## Production Path",
        "",
        "Keyword-first local use is allowed after local validation passes. Future publication should run `gbrain sync --repo <compiled-corpus>` and then `gbrain embed --stale` only after external gates pass.",
        "",
        "Production sync is blocked until external Mycroft/GBrain gates pass for reliability, read-only permissions, backup/restore, and traceability.",
        "",
        f"- Source manifest hash: `{source_manifest_hash}`.",
        "- Schema-pack suggestion: `.raw/schema-pack/legal-corpus-pack.yaml`.",
    ]
    return _markdown(
        _frontmatter(
            title="Legal Corpus Index",
            page_type="corpus_index",
            generated_at=generated_at,
            wikilinks=["RESOLVER", "schema"],
        ),
        body,
    )


def _frontmatter(
    *,
    title: str,
    page_type: str,
    generated_at: str,
    wikilinks: list[str],
) -> dict[str, object]:
    return {
        "title": title,
        "type": page_type,
        "status": "production_readiness",
        "generated_at": generated_at,
        "confidentiality": "internal",
        "wikilinks": wikilinks,
    }


def _markdown(frontmatter: dict[str, object], body_lines: list[str]) -> str:
    dumped = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    return "---\n" + dumped + "\n---\n" + "\n".join(body_lines).rstrip() + "\n"
