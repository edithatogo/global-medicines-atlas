from datetime import UTC, datetime

import pytest

from global_medicines_atlas.research_exports import (
    ExportCitation,
    ExportSource,
    build_query_snapshot_manifest,
    canonical_manifest_bytes,
    manifest_sha256,
)


def _source() -> ExportSource:
    return ExportSource(
        dataset_id="edithatogo/aus-mbs-pbs",
        revision="0123456789abcdef0123456789abcdef01234567",
        path="silver/mbs.parquet",
        sha256="a" * 64,
        schema_id="gma.mbs",
        schema_version="4",
    )


@pytest.mark.unit
def test_manifest_is_order_stable_and_content_addressed() -> None:
    kwargs = {
        "query": {"filters": {"jurisdiction": "AU"}, "select": ["item_id"]},
        "sources": [_source()],
        "citations": [
            ExportCitation(
                citation_id="mbs",
                title="MBS source",
                uri="https://example.invalid/mbs",
            )
        ],
        "generated_at": datetime(2026, 1, 1, tzinfo=UTC),
        "generator_commit": "abc1234",
    }
    first = build_query_snapshot_manifest(
        result_rows=[{"item_id": "2"}, {"item_id": "1"}], **kwargs
    )
    second = build_query_snapshot_manifest(
        result_rows=[{"item_id": "1"}, {"item_id": "2"}], **kwargs
    )
    assert canonical_manifest_bytes(first) == canonical_manifest_bytes(second)
    assert len(manifest_sha256(first)) == 64
    assert first.result_row_count == 2


@pytest.mark.unit
def test_manifest_order_is_stable_when_source_and_citation_keys_tie() -> None:
    source = _source()
    changed_source = source.model_copy(update={"sha256": "b" * 64})
    citation = ExportCitation(
        citation_id="mbs", title="Primary", uri="https://example.invalid/a"
    )
    changed_citation = citation.model_copy(update={"title": "Secondary"})
    kwargs = {
        "query": {"select": ["item_id"]},
        "result_rows": [{"item_id": "1"}],
        "generated_at": datetime(2026, 1, 1, tzinfo=UTC),
        "generator_commit": "abc1234",
    }
    first = build_query_snapshot_manifest(
        sources=[source, changed_source],
        citations=[citation, changed_citation],
        **kwargs,
    )
    second = build_query_snapshot_manifest(
        sources=[changed_source, source],
        citations=[changed_citation, citation],
        **kwargs,
    )
    assert canonical_manifest_bytes(first) == canonical_manifest_bytes(second)
    assert manifest_sha256(first) == manifest_sha256(second)


@pytest.mark.edge
def test_manifest_never_embeds_result_rows() -> None:
    manifest = build_query_snapshot_manifest(
        query={"select": ["item_id"]},
        result_rows=[{"item_id": "secret-looking-fixture"}],
        sources=[_source()],
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        generator_commit="abc1234",
    )
    assert b"secret-looking-fixture" not in canonical_manifest_bytes(manifest)


@pytest.mark.edge
def test_manifest_requires_pinned_source() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        build_query_snapshot_manifest(
            query={},
            result_rows=[],
            sources=[],
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            generator_commit="abc1234",
        )


@pytest.mark.edge
def test_manifest_rejects_non_json_numeric_values() -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        build_query_snapshot_manifest(
            query={"threshold": float("nan")},
            result_rows=[],
            sources=[_source()],
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            generator_commit="abc1234",
        )


@pytest.mark.parametrize(
    "uri",
    [
        "http://example.test/citation",
        "https://user:secret@example.test/citation",
        "https://example.test/citation?access_token=secret",
        "https://example.test/citation#fragment",
        "https://127.0.0.1/citation",
        "https://[::1]/citation",
        "https://169.254.169.254/citation",
        "https://localhost/citation",
    ],
)
def test_citation_uri_rejects_private_or_ambiguous_references(uri: str) -> None:
    with pytest.raises(
        ValueError, match=r"public HTTPS|credentials|query|fragment|public host"
    ):
        ExportCitation(
            citation_id="source",
            title="Source",
            uri=uri,
        )
