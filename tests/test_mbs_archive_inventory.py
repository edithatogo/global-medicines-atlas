"""Historical archive metadata retains frozen identities and unresolved holds."""

import json
from pathlib import Path

import pytest

from global_medicines_atlas import mbs_archive_inventory as module
from global_medicines_atlas.mbs_archive_inventory import load_archives

ROOT = Path(__file__).resolve().parents[1]


def test_all_six_frozen_archives_keep_original_b1_b2_and_prior_state():
    sources = load_archives(ROOT)
    assert len(sources) == 6
    assert (
        sum(source.prior_status == "structure_verified" for source in sources)
        == 4
    )
    assert (
        sum(source.prior_status == "resource_hold" for source in sources) == 2
    )
    for source in sources:
        assert source.dataset == "edithatogo/australian-mbs-utilisation-archive"
        assert source.source_path.endswith(".zip")
        assert source.source_bytes > 0
        assert len(source.b1_sha256) == 64
        assert len(source.b2_sha256) == 64
    held = next(
        source for source in sources if "2008-2012" in source.source_path
    )
    assert held.prior_member_count is None
    assert held.prior_inventory_sha256 is None


def test_changed_structural_receipt_is_rejected(tmp_path):
    path = tmp_path / module.STRUCTURE
    path.parent.mkdir(parents=True)
    path.write_text("changed")
    with pytest.raises(ValueError, match="metadata digest"):
        load_archives(tmp_path)


@pytest.mark.parametrize(
    "change", ["membership", "payload_digest", "byte_count", "cohort_count"]
)
def test_frozen_archive_binding_rejects_inconsistent_input(monkeypatch, change):
    structure = json.loads((ROOT / module.STRUCTURE).read_bytes())
    frozen = json.loads((ROOT / module.FROZEN).read_bytes())
    document = next(
        row["document"]
        for row in structure["per_object_receipts"]
        if row["document"]["raw_reference"]["path"].endswith(".zip")
    )
    if change == "membership":
        frozen["members"] = []
    elif change == "payload_digest":
        document["raw_reference"]["sha256"] = "0" * 64
    elif change == "byte_count":
        document["raw_reference"]["byte_count"] += 1
    else:
        structure["per_object_receipts"] = []
    monkeypatch.setattr(
        module,
        "_bound",
        lambda _, path, __: structure if path == module.STRUCTURE else frozen,
    )
    with pytest.raises(ValueError, match="MBS archive"):
        load_archives(ROOT)
