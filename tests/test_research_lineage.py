from __future__ import annotations

import pytest

from global_medicines_atlas.research_lineage import (
    ResearchLineageArtifact,
    build_research_lineage_receipt,
)


def _artifact(identifier: str, role: str) -> ResearchLineageArtifact:
    return ResearchLineageArtifact(
        identifier=identifier,
        role=role,  # type: ignore[arg-type]
        public_url=f"https://huggingface.co/datasets/example/resolve/main/{identifier}",
        sha256="b" * 64,
    )


def test_lineage_receipt_is_sorted_deterministic_and_payload_free() -> None:
    receipt = build_research_lineage_receipt(
        export_id="export-1",
        revision="a" * 40,
        artifacts=(
            _artifact("output.json", "output"),
            _artifact("input.json", "input"),
        ),
    )
    assert receipt.payloads_embedded is False
    assert [item.identifier for item in receipt.artifacts] == [
        "input.json",
        "output.json",
    ]
    assert receipt.canonical_bytes() == receipt.canonical_bytes()
    assert len(receipt.sha256()) == 64
    assert "payload" not in receipt.document()


def test_lineage_receipt_requires_both_roles_and_unique_ids() -> None:
    with pytest.raises(ValueError, match="requires input and output"):
        build_research_lineage_receipt(
            export_id="export-1",
            revision="a" * 40,
            artifacts=(_artifact("only.json", "input"),),
        )
    with pytest.raises(ValueError, match="identifiers must be unique"):
        build_research_lineage_receipt(
            export_id="export-1",
            revision="a" * 40,
            artifacts=(
                _artifact("same.json", "input"),
                _artifact("same.json", "output"),
            ),
        )
