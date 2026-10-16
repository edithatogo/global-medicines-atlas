from __future__ import annotations

from typing import Literal

import pytest

from global_medicines_atlas.research_lineage import (
    ResearchLineageArtifact,
    ResearchLineageReceipt,
    build_research_lineage_receipt,
)


def _artifact(
    identifier: str,
    role: Literal["input", "output"],
) -> ResearchLineageArtifact:
    return ResearchLineageArtifact(
        identifier=identifier,
        role=role,
        public_url=(
            f"https://huggingface.co/datasets/example/resolve/{'a' * 40}/{identifier}"
        ),
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
    assert receipt.schema_version == 1
    assert [item.identifier for item in receipt.artifacts] == [
        "input.json",
        "output.json",
    ]
    assert receipt.canonical_bytes() == receipt.canonical_bytes()
    assert len(receipt.sha256()) == 64
    assert "payload" not in receipt.document()
    assert b'"revision":null' not in receipt.canonical_bytes()


def test_cross_dataset_inputs_bind_their_own_revisions() -> None:
    receipt = build_research_lineage_receipt(
        export_id="cross-dataset-export",
        revision="b" * 40,
        artifacts=(
            ResearchLineageArtifact(
                identifier="mbs-source",
                role="input",
                public_url=(
                    f"https://huggingface.co/datasets/example/mbs/resolve/"
                    f"{'c' * 40}/raw.xml"
                ),
                sha256="c" * 64,
                revision="c" * 40,
            ),
            ResearchLineageArtifact(
                identifier="pbs-source",
                role="input",
                public_url=(
                    f"https://huggingface.co/datasets/example/pbs/resolve/"
                    f"{'d' * 40}/raw.xml"
                ),
                sha256="d" * 64,
                revision="d" * 40,
            ),
            ResearchLineageArtifact(
                identifier="export.json",
                role="output",
                public_url=(
                    f"https://huggingface.co/datasets/example/export/resolve/"
                    f"{'b' * 40}/export.json"
                ),
                sha256="e" * 64,
            ),
        ),
    )

    assert {
        item.identifier: item.revision
        for item in receipt.artifacts
        if item.role == "input"
    } == {"mbs-source": "c" * 40, "pbs-source": "d" * 40}
    assert receipt.revision == "b" * 40
    assert receipt.schema_version == 2


def test_lineage_outputs_must_use_the_export_revision() -> None:
    with pytest.raises(ValueError, match="output revision must match"):
        build_research_lineage_receipt(
            export_id="cross-dataset-export",
            revision="b" * 40,
            artifacts=(
                ResearchLineageArtifact(
                    identifier="source.json",
                    role="input",
                    public_url=(
                        f"https://huggingface.co/datasets/example/source/resolve/"
                        f"{'c' * 40}/source.json"
                    ),
                    sha256="c" * 64,
                    revision="c" * 40,
                ),
                ResearchLineageArtifact(
                    identifier="export.json",
                    role="output",
                    public_url=(
                        f"https://huggingface.co/datasets/example/export/resolve/"
                        f"{'c' * 40}/export.json"
                    ),
                    sha256="e" * 64,
                    revision="c" * 40,
                ),
            ),
        )


def test_schema_v1_rejects_artifact_specific_revisions() -> None:
    revision = "a" * 40
    with pytest.raises(
        ValueError,
        match="artifact revisions require research-lineage schema version 2",
    ):
        ResearchLineageReceipt(
            schema_id="global-medicines-atlas.research-lineage",
            schema_version=1,
            export_id="legacy-export",
            revision=revision,
            artifacts=(
                ResearchLineageArtifact(
                    identifier="input.json",
                    role="input",
                    public_url=(
                        "https://huggingface.co/datasets/example/resolve/"
                        f"{revision}/input.json"
                    ),
                    sha256="b" * 64,
                    revision=revision,
                ),
                ResearchLineageArtifact(
                    identifier="output.json",
                    role="output",
                    public_url=(
                        "https://huggingface.co/datasets/example/resolve/"
                        f"{revision}/output.json"
                    ),
                    sha256="c" * 64,
                ),
            ),
        )


def test_lineage_receipt_requires_both_roles_and_unique_ids() -> None:
    with pytest.raises(ValueError, match="requires input and output"):
        build_research_lineage_receipt(
            export_id="export-1",
            revision="a" * 40,
            artifacts=(_artifact("only.json", "input"),),
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test/a",
        "https://user:pass@example.test/a",
        "https://example.test/a#fragment",
    ],
)
def test_artifact_url_must_be_public_https_without_credentials_or_fragment(
    url: str,
) -> None:
    with pytest.raises(ValueError, match=r"public HTTPS|credentials|fragment"):
        ResearchLineageArtifact(
            identifier="input.json",
            role="input",
            public_url=url,
            sha256="b" * 64,
        )


def test_artifact_urls_bind_to_receipt_revision() -> None:
    with pytest.raises(
        ValueError, match="bind to the declared immutable revision"
    ):
        build_research_lineage_receipt(
            export_id="export-1",
            revision="c" * 40,
            artifacts=(
                _artifact("input.json", "input"),
                _artifact("output.json", "output"),
            ),
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
