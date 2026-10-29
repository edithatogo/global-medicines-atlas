"""Group workbook discovery must not borrow demographic or CSV meanings."""

from hashlib import sha256
from pathlib import Path

import pytest
from test_mbs_demographic_extraction import workbook
from test_mbs_demographic_silver import source

from global_medicines_atlas import mbs_group_workbook_layout as module
from global_medicines_atlas.mbs_group_workbook_layout import (
    inspect_layout,
    load_reference,
)

ROOT = Path(__file__).resolve().parents[1]


def test_exact_group_workbook_identity_has_retained_b1_b2_and_size():
    reference = load_reference(ROOT)
    assert (
        reference["sha256"]
        == "9f2f28b69f58a0aa05a0b56b09515651b1e0b50a634234ce7f6f6c8426373285"
    )
    assert reference["bytes"] == 6857437
    assert reference["source_id"] == "au-data-gov-mbs-group"
    assert reference["path"].endswith("group/mbs-group-2016hr-july.xlsx")
    assert len(reference["b1_sha256"]) == len(reference["b2_sha256"]) == 64


def reference(payload):
    return {"sha256": sha256(payload).hexdigest(), "bytes": len(payload)}


def test_layout_preserves_native_header_candidates_without_assigning_roles():
    payload = workbook(header=tuple(f"Native {i}" for i in range(8)))
    report = inspect_layout(payload, reference(payload))
    assert report["sheet_count"] == 2
    assert report["sheets"][0]["native_cells"] == 17
    assert report["sheets"][0]["native_rows"] == 3
    assert report["sheets"][0]["formula_cells"] == 1
    candidates = report["sheets"][0]["header_candidates"]
    assert [cell["value"] for cell in candidates if cell["row"] == 3] == [
        f"Native {i}" for i in range(8)
    ]
    assert all(cell["row"] <= 3 for cell in candidates)
    assert report["semantic_roles_assigned"] is False
    assert report == inspect_layout(payload, reference(payload))


@pytest.mark.parametrize("change", ["digest", "size", "empty"])
def test_identity_mismatch_stops_before_decoding(change):
    payload = workbook()
    bound = reference(payload)
    if change == "digest":
        bound["sha256"] = "0" * 64
    elif change == "size":
        bound["bytes"] += 1
    else:
        payload = b""
        bound = reference(payload)
    with pytest.raises(ValueError, match="identity"):
        inspect_layout(payload, bound)


def test_duplicate_coordinates_fail_closed():
    payload = workbook(data_row='<c r="A4"><v>1</v></c><c r="A4"><v>2</v></c>')
    with pytest.raises(ValueError, match="coordinate"):
        inspect_layout(payload, reference(payload))


def test_metadata_digest_rejects_changed_receipt(tmp_path):

    path = tmp_path / module.STRUCTURE
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(ValueError, match="metadata digest"):
        load_reference(tmp_path)


@pytest.mark.parametrize(
    "change", ["duplicate", "membership", "status", "digest", "bytes"]
)
def test_retained_reference_drift_rejects(monkeypatch, change):

    original = module._bound

    def altered(root, path, digest):
        report = original(root, path, digest)
        if path == module.STRUCTURE:
            row = next(
                row
                for row in report["per_object_receipts"]
                if row["document"]["raw_reference"]["path"]
                == module.SOURCE_PATH
            )
            document = row["document"]
            if change == "duplicate":
                report["per_object_receipts"].append(row)
            elif change == "status":
                document["result"]["status"] = "failed"
            elif change == "digest":
                document["raw_reference"]["sha256"] = "0" * 64
            elif change == "bytes":
                document["raw_reference"]["byte_count"] = True
        elif change == "membership":
            report["members"] = []
        return report

    monkeypatch.setattr(module, "_bound", altered)
    with pytest.raises(ValueError, match="group workbook"):
        load_reference(ROOT)


def test_unqualified_header_roles_are_unavailable():

    base = source("workbook", b"synthetic")
    raw = module._GroupBinding.model_construct(**base.model_dump())
    with pytest.raises(ValueError, match="unqualified"):
        _ = raw.headers


@pytest.mark.parametrize("change", ["row", "header_bound"])
def test_coordinate_and_candidate_bounds(monkeypatch, change):

    payload = (
        workbook(data_row='<c r="A5"><v>2</v></c>')
        if change == "row"
        else workbook()
    )
    if change == "header_bound":
        monkeypatch.setattr(module, "MAX_HEADER_CELLS", 1)
    with pytest.raises(ValueError, match=r"coordinate|bound"):
        inspect_layout(payload, reference(payload))
