from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from legal_corpus.manifest import Manifest, load_manifest


def valid_manifest_data() -> dict[str, object]:
    return {
        "documents": [
            {
                "source_path": ".raw/sources/example-bylaw.md",
                "document_type": "bylaw",
                "title": "Example Student Association Bylaw",
                "slug": "example-bylaw",
                "jurisdiction": "fictional",
                "authority_rank": 40,
                "status": "active",
                "confidentiality": "internal",
                "effective_date": None,
                "owner": "Legal Corpus Compiler fixtures",
                "version": "fixture-v1",
                "reviewed_by": None,
                "metadata_notes": [
                    "effective_date is null because this is an invented contract fixture.",
                    "reviewed_by is null because no legal review applies to fictional fixtures.",
                ],
            }
        ]
    }


def test_manifest_accepts_required_nullable_fields_with_notes() -> None:
    manifest = Manifest.model_validate(valid_manifest_data())

    assert manifest.documents[0].source_path == ".raw/sources/example-bylaw.md"
    assert manifest.documents[0].effective_date is None
    assert manifest.documents[0].reviewed_by is None


def test_manifest_rejects_null_effective_date_without_matching_note() -> None:
    data = valid_manifest_data()
    document = data["documents"][0]
    assert isinstance(document, dict)
    document["metadata_notes"] = [
        "reviewed_by is null because no legal review applies to fictional fixtures."
    ]

    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_manifest_rejects_missing_confidentiality() -> None:
    data = valid_manifest_data()
    document = data["documents"][0]
    assert isinstance(document, dict)
    document.pop("confidentiality")

    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_manifest_rejects_extra_fields() -> None:
    data = valid_manifest_data()
    document = data["documents"][0]
    assert isinstance(document, dict)
    document["unexpected"] = "not part of the strict contract"

    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_load_manifest_uses_yaml_safe_load(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(valid_manifest_data()), encoding="utf-8")

    manifest = load_manifest(manifest_path)

    assert manifest.documents[0].slug == "example-bylaw"

