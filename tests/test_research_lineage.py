from global_medicines_atlas.research_lineage import LineageReceipt


def test_lineage_receipt_is_deterministic_and_payload_free() -> None:
    r = LineageReceipt(
        source_revision="abc", source_digest="a" * 64, export_digest="b" * 64
    )
    assert r.canonical_bytes() == r.canonical_bytes()
    assert len(r.sha256()) == 64
    assert r.payloads_embedded is False
