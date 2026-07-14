"""Deterministic gold-question checks for compiled corpus retrieval coverage."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from legal_corpus.validation_records import GoldQuestion, GoldRetrievalResult
from legal_corpus.validation_records import RetrievalHit


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def load_gold_questions(path: Path) -> list[GoldQuestion]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("gold questions file must contain a questions list")
    return [GoldQuestion.model_validate(question) for question in questions]


def evaluate_gold_questions(
    output_root: Path,
    gold_path: Path,
    *,
    top_k: int = 5,
) -> list[GoldRetrievalResult]:
    pages = _load_pages(output_root)
    identity_index = _identity_index(pages)
    questions = load_gold_questions(gold_path)
    results = []
    for question in questions:
        hits = _rank_pages(question.question, pages, top_k=top_k)
        hit_aliases = {
            alias
            for hit in hits
            for alias in pages[hit.path].aliases
        }
        missing_clause_ids = [
            clause_id
            for clause_id in question.expected_clause_ids
            if clause_id not in identity_index or clause_id not in hit_aliases
        ]
        missing_parent_ids = [
            parent_id
            for parent_id in question.expected_parent_ids
            if parent_id not in identity_index
            or not _expected_clauses_link_target(question.expected_clause_ids, parent_id, identity_index)
        ]
        missing_definition_ids = [
            definition_id
            for definition_id in question.expected_definition_ids
            if definition_id not in identity_index
            or not _expected_clauses_link_target(question.expected_clause_ids, definition_id, identity_index)
        ]
        results.append(
            GoldRetrievalResult(
                question_id=question.id,
                passed=not missing_clause_ids
                and not missing_parent_ids
                and not missing_definition_ids,
                hits=hits,
                missing_clause_ids=missing_clause_ids,
                missing_parent_ids=missing_parent_ids,
                missing_definition_ids=missing_definition_ids,
            )
        )
    return results


class _GoldPage:
    def __init__(self, *, path: Path, relative_path: str, frontmatter: dict[str, Any], text: str) -> None:
        self.path = path
        self.relative_path = relative_path
        self.frontmatter = frontmatter
        self.text = text

    @property
    def aliases(self) -> set[str]:
        aliases = {self.path.stem}
        for field in ("slug", "clause_id"):
            value = self.frontmatter.get(field)
            if isinstance(value, str) and value:
                aliases.add(value)
        if self.frontmatter.get("type") == "legal_instrument":
            value = self.frontmatter.get("instrument_slug")
            if isinstance(value, str) and value:
                aliases.add(value)
        return aliases

    @property
    def target_id(self) -> str:
        for field in ("clause_id", "slug", "instrument_slug"):
            value = self.frontmatter.get(field)
            if isinstance(value, str) and value:
                return value
        return self.path.stem

    @property
    def links(self) -> set[str]:
        links: set[str] = set()
        for field in ("wikilinks", "parent_chain", "child_clauses", "definitions"):
            value = self.frontmatter.get(field)
            if isinstance(value, list):
                links.update(item for item in value if isinstance(item, str))
        for field in ("parent_clause", "source_clause", "instrument_slug"):
            value = self.frontmatter.get(field)
            if isinstance(value, str) and value:
                links.add(value)
        return links


def _load_pages(output_root: Path) -> dict[str, _GoldPage]:
    root = output_root.resolve()
    pages: dict[str, _GoldPage] = {}
    for path in sorted(root.rglob("*.md")):
        if ".raw" in path.relative_to(root).parts:
            continue
        frontmatter, text = _parse_page(path)
        relative_path = path.relative_to(root).as_posix()
        pages[relative_path] = _GoldPage(
            path=path,
            relative_path=relative_path,
            frontmatter=frontmatter,
            text=text,
        )
    return pages


def _parse_page(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return {}, text
    frontmatter = yaml.safe_load("\n".join(lines[1:closing_index])) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, "\n".join(lines[closing_index + 1 :])


def _identity_index(pages: dict[str, _GoldPage]) -> dict[str, _GoldPage]:
    index: dict[str, _GoldPage] = {}
    for page in pages.values():
        for alias in page.aliases:
            index.setdefault(alias, page)
    return index


def _rank_pages(question: str, pages: dict[str, _GoldPage], *, top_k: int) -> list[RetrievalHit]:
    query_tokens = _tokens(question)
    scored: list[tuple[float, str, _GoldPage]] = []
    for page in pages.values():
        haystack = _page_search_text(page)
        page_tokens = _tokens(haystack)
        overlap = sum(1 for token in query_tokens if token in page_tokens)
        phrase_bonus = 2 if question.lower() in haystack.lower() else 0
        score = overlap + phrase_bonus
        if score <= 0:
            continue
        scored.append((float(score), page.relative_path, page))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        RetrievalHit(target_id=page.target_id, path=relative_path, score=score)
        for score, relative_path, page in scored[:top_k]
    ]


def _page_search_text(page: _GoldPage) -> str:
    frontmatter_parts: list[str] = []
    for value in page.frontmatter.values():
        if isinstance(value, str):
            frontmatter_parts.append(value)
        elif isinstance(value, list):
            frontmatter_parts.extend(str(item) for item in value)
    return "\n".join([page.path.stem, *frontmatter_parts, page.text])


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_RE.finditer(text)}


def _expected_clauses_link_target(
    expected_clause_ids: list[str],
    target_id: str,
    identity_index: dict[str, _GoldPage],
) -> bool:
    for clause_id in expected_clause_ids:
        page = identity_index.get(clause_id)
        if page and target_id in page.links:
            return True
    return False
