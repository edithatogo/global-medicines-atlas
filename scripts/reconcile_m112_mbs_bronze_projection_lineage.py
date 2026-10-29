"""Reproduce the four frozen August MBS Bronze Parquet projections."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from global_medicines_atlas.adapters.au_mbs import parse_mbs_source_xml
from global_medicines_atlas.mbs_release import mbs_source_parquet
from global_medicines_atlas.receipts import SourceReceipt

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "july-mbs-silver-lineage.json"
)
FROZEN = QUAL / "australian-m112-frozen-object-inventory-20261018.json"
TREE = QUAL / "australian-m112-current-tree-object-inventory-20261004.json"
M108 = QUAL / "australian-m108-derived-products-20261017.json"
DATASET = "edithatogo/australian-mbs-source-archive"
REVISION = "40891976f77ee5e7688edceed25c9ac98a77547e"
RAW_PATH = (
    "raw/mbs/releases/2026-08-01/"
    "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml"
)
RAW_SHA256 = "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
RAW_BYTES = 8_293_331
SOURCE_RECORD_COUNT = 6046
P7_RECORD_COUNT = 165
PREFIX = "bronze/mbs/releases/2026-08-01"
EXPECTED_RUNS = {
    "6bc9bcb2e60728ac6d8b38ef76e9af15de32f026bb9ce83109df426a7f077c64": {
        "acquisition_id": "f5626f2deb09f4301989480f112ec117ccad9efafc54c04d161100d6c5ca08e1",
        "receipt_id": "mbs-release:a7a43be8b30052c192a00d993d5977e524f79b936e2bcfc2919322b4ffcba6d4",
        "decision_id": "a4c8e7850c664db20b80a9f3e6d5cd09c61ebc1447c121c852438eff24a42dba",
    },
    "99fada49ebf8e71e8e14417e9275f36840d46577a39746fea02bd89de30a30fc": {
        "acquisition_id": "783bd12fab14dc8f93cb34b1d87e9c3f7c95543d261b008f4e0da018a3d11e57",
        "receipt_id": "mbs-release:d47c71a685b9b31aa0b0b40979a482635c84888e7334a5610f9fa22bee3709c6",
        "decision_id": "eb05c5b19a731d9009d6fedbfb45b2d56bb742729728f0a54c306835f10d312c",
    },
}
EXPECTED_OUTPUTS = {
    "6bc9bcb2e60728ac6d8b38ef76e9af15de32f026bb9ce83109df426a7f077c64/source.parquet": (
        454_247,
        "80f8e0d3cc67f6f3a22f23cc3bfb0db5da4d44d79741da3ce1c31ee92836627a",
    ),
    "6bc9bcb2e60728ac6d8b38ef76e9af15de32f026bb9ce83109df426a7f077c64/p7.parquet": (
        24_367,
        "2da8606d3e408294bcfdc914906de4814d33c1a72acf5a2ba40f91473267516a",
    ),
    "99fada49ebf8e71e8e14417e9275f36840d46577a39746fea02bd89de30a30fc/source.parquet": (
        454_247,
        "5219094d2ec7f4386380b356cc17f071c97751db43ed367746a6d07ca4ff3eaf",
    ),
    "99fada49ebf8e71e8e14417e9275f36840d46577a39746fea02bd89de30a30fc/p7.parquet": (
        24_367,
        "6362f7f3a5d9870545cc074450b81a82475d68fdb062f38083713f56bd88d2fe",
    ),
}
EXPECTED_DENOMINATOR = 1759
EXPECTED_COMPLETE_RAW = 22
EXPECTED_COMPLETE_PROJECTIONS = 6
EXPECTED_OUTPUT_COUNT = 4
EXPECTED_RUN_COUNT = 2
OBSERVED_AT = "2026-10-19T06:59:00+10:00"
OUTPUT = QUAL / "australian-m112-mbs-bronze-projection-lineage-20261019.json"
OVERLAY_OUTPUT = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "mbs-bronze-projection-lineage.json"
)


def _read(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return _object(value, str(path))


def _object(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {context}")
    return cast("dict[str, Any]", value)


def _rows(value: object, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TypeError(f"expected JSON object rows: {context}")
    rows: list[dict[str, Any]] = []
    for row in cast("list[object]", value):
        if not isinstance(row, dict):
            raise TypeError(f"expected JSON object rows: {context}")
        rows.append(cast("dict[str, Any]", row))
    return rows


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _fetch(path: str) -> bytes:
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{path}"
    request = Request(url, headers={"User-Agent": "gma-m112-lineage/1"})
    with urlopen(request, timeout=90) as response:  # ruff: ignore[suspicious-url-open-usage] - pinned public dataset metadata/payload endpoint
        return response.read()


def rebuild_projection_bytes(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    expected_record_count: int = SOURCE_RECORD_COUNT,
) -> dict[str, bytes]:
    """Rebuild only the two declared table outputs in memory."""
    batch = parse_mbs_source_xml(payload, receipt)
    if batch.record_count != expected_record_count:
        raise ValueError("pinned MBS source record denominator changed")
    return {
        "source.parquet": mbs_source_parquet(batch),
        "p7.parquet": mbs_source_parquet(batch, only_p7=True),
    }


def _entry(rows: list[dict[str, Any]], *, path: str) -> dict[str, Any]:
    matches = [row for row in rows if row.get("path") == path]
    if len(matches) != 1:
        raise ValueError(
            f"expected one object entry for {path}; found {len(matches)}"
        )
    return matches[0]


def _build_bindings(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- verify source, receipts, outputs and frozen identities explicitly
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    base = _read(BASE)
    frozen = _read(FROZEN)
    tree = _read(TREE)
    m108 = _read(M108)
    totals = base["updated_gate_totals"]
    if not all((
        totals.get("approved_denominator") == EXPECTED_DENOMINATOR,
        totals.get("complete_raw_b1_b2_lineage") == EXPECTED_COMPLETE_RAW,
        totals.get("complete_projection_lineage")
        == EXPECTED_COMPLETE_PROJECTIONS,
        totals.get("preserved_deferrals") == EXPECTED_DENOMINATOR,
        totals.get("v4_admissions") == 0,
        totals.get("consumer_canaries") == 0,
    )):
        raise ValueError("base overlay scope or independent gates changed")

    raw = _fetch(RAW_PATH)
    raw_digest = hashlib.sha256(raw).hexdigest()
    if len(raw) != RAW_BYTES or raw_digest != RAW_SHA256:
        raise ValueError(
            "pinned raw B2 stream does not match its expected identity"
        )

    products = [
        row
        for row in _rows(m108.get("products"), "M-108 products")
        if row.get("product_id")
        in {
            "mbs-2026-08-bronze-acquisition-6bc9bcb2",
            "mbs-2026-08-bronze-acquisition-99fada49",
        }
    ]
    m108_outputs = {
        row.get("path"): row
        for product in products
        for row in _rows(product.get("outputs"), "M-108 product outputs")
    }
    products_by_id: dict[object, dict[str, Any]] = {
        row.get("product_id"): row for row in products
    }
    output_evidence: dict[str, dict[str, Any]] = {}
    for run_id, run in EXPECTED_RUNS.items():
        prefix = f"{PREFIX}/{run_id}"
        manifest = _object(
            json.loads(_fetch(f"{prefix}/manifest.json")),
            f"{prefix}/manifest.json",
        )
        receipt_bytes = _fetch(f"{prefix}/source-receipt.json")
        admission = _object(
            json.loads(_fetch(f"{prefix}/admission.json")),
            f"{prefix}/admission.json",
        )
        receipt = SourceReceipt.model_validate_json(receipt_bytes)
        product_id = (
            "mbs-2026-08-bronze-acquisition-6bc9bcb2"
            if run_id.startswith("6bc9")
            else "mbs-2026-08-bronze-acquisition-99fada49"
        )
        product_admission = _object(
            products_by_id.get(product_id, {}).get("admission"),
            f"M-108 admission {product_id}",
        )
        manifest_objects = {
            row.get("path"): row
            for row in _rows(manifest.get("objects"), f"{prefix} objects")
        }
        raw_manifest_object = manifest_objects.get(RAW_PATH)
        if not isinstance(raw_manifest_object, dict):
            raise TypeError(f"MBS run {run_id} manifest omits its raw input")
        if not all((
            receipt.payload.sha256 == RAW_SHA256,
            receipt.payload.byte_count == RAW_BYTES,
            receipt.source.source_id == "au-mbs",
            receipt.receipt_id == run["receipt_id"],
            manifest.get("source_id") == "au-mbs",
            manifest.get("data_acquired") is False,
            manifest.get("admission_state") == "accepted",
            manifest.get("record_count") == SOURCE_RECORD_COUNT,
            manifest.get("p7_record_count") == P7_RECORD_COUNT,
            raw_manifest_object.get("sha256") == RAW_SHA256,
            raw_manifest_object.get("bytes") == RAW_BYTES,
            admission.get("acquisition_id") == run["acquisition_id"],
            admission.get("decision_id") == run["decision_id"],
            admission.get("content_id") == RAW_SHA256,
            admission.get("state") == "accepted",
            admission.get("reviewer_status") == "unreviewed",
            product_admission.get("acquisition_id") == run["acquisition_id"],
            product_admission.get("decision_id") == run["decision_id"],
            product_admission.get("content_id") == RAW_SHA256,
        )):
            raise ValueError(
                f"MBS run {run_id} metadata failed exact source binding"
            )

        generated = rebuild_projection_bytes(raw, receipt)
        for filename, payload in generated.items():
            relative = f"{run_id}/{filename}"
            output_path = f"{PREFIX}/{relative}"
            expected_bytes, expected_digest = EXPECTED_OUTPUTS[relative]
            object_row = manifest_objects.get(output_path)
            identity_row = _entry(
                [
                    row
                    for row in _rows(
                        tree.get("observations"), "tree inventory observations"
                    )
                    if row.get("dataset") == DATASET
                ],
                path=output_path,
            )
            m108_row = m108_outputs.get(output_path)
            if not isinstance(object_row, dict) or not isinstance(
                m108_row, dict
            ):
                raise TypeError(f"pinned metadata omits output: {output_path}")
            if not all((
                len(payload) == expected_bytes,
                hashlib.sha256(payload).hexdigest() == expected_digest,
                object_row.get("sha256") == expected_digest,
                object_row.get("bytes") == expected_bytes,
                object_row.get("role")
                == (
                    "p7_parquet"
                    if filename == "p7.parquet"
                    else "source_parquet"
                ),
                identity_row.get("observed_lfs_sha256") == expected_digest,
                identity_row.get("observed_bytes") == expected_bytes,
                m108_row.get("sha256") == expected_digest,
                m108_row.get("byte_count") == expected_bytes,
            )):
                raise ValueError(
                    f"reproduced projection differs from pinned object: {output_path}"
                )
            frozen_row = _entry(
                [
                    row
                    for row in _rows(frozen.get("members"), "frozen members")
                    if row.get("dataset") == DATASET
                ],
                path=output_path,
            )
            base_row = _entry(
                [
                    row
                    for row in base.get("objects", [])
                    if row.get("dataset") == DATASET
                ],
                path=output_path,
            )
            if not all((
                frozen_row.get("object_class") == "existing_data_projection",
                base_row.get("approved_denominator_member") is True,
                base_row.get("identity", {}).get("sha256") == expected_digest,
                base_row.get("b1_b2_lineage", {}).get("complete") is False,
                base_row.get("disposition") == "deferred_not_admitted",
            )):
                raise ValueError(
                    f"projection no longer matches frozen deferred object: {output_path}"
                )
            output_evidence[output_path] = {
                "run_id": run_id,
                "path": output_path,
                "sha256": expected_digest,
                "byte_count": expected_bytes,
                "source_path": RAW_PATH,
                "source_sha256": RAW_SHA256,
                "source_byte_count": RAW_BYTES,
                "source_receipt_id": receipt.receipt_id,
                "source_receipt_sha256": hashlib.sha256(
                    receipt_bytes
                ).hexdigest(),
                "acquisition_id": run["acquisition_id"],
                "admission_decision_id": run["decision_id"],
                "admission_state": "accepted",
                "admission_reviewer_status": "unreviewed",
                "manifest_path": f"{prefix}/manifest.json",
                "manifest_revision": REVISION,
                "transformation": {
                    "adapter": "parse_mbs_source_xml",
                    "projection": "mbs_source_parquet",
                    "projection_selection": "Group=P7"
                    if filename == "p7.parquet"
                    else "all",
                    "implementation_paths": [
                        "src/global_medicines_atlas/adapters/au_mbs.py",
                        "src/global_medicines_atlas/mbs_release.py",
                    ],
                    "implementation_sha256": {
                        "src/global_medicines_atlas/adapters/au_mbs.py": _sha(
                            Path(
                                "src/global_medicines_atlas/adapters/au_mbs.py"
                            )
                        ),
                        "src/global_medicines_atlas/mbs_release.py": _sha(
                            Path("src/global_medicines_atlas/mbs_release.py")
                        ),
                    },
                    "reproduced_exact_bytes_in_memory": True,
                },
            }

    if (
        len(output_evidence) != EXPECTED_OUTPUT_COUNT
        or len(products) != EXPECTED_RUN_COUNT
    ):
        raise ValueError("expected the exact four-output/two-run MBS cohort")
    qualification: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-m112-mbs-bronze-projection-lineage",
        "schema_version": 1,
        "observed_at": OBSERVED_AT,
        "status": "four_frozen_mbs_bronze_projection_lineages_reproduced",
        "scope": {
            "dataset": DATASET,
            "revision": REVISION,
            "frozen_inventory_revision": "40891976f77ee5e7688edceed25c9ac98a77547e",
            "frozen_object_count": EXPECTED_DENOMINATOR,
            "raw_source_path": RAW_PATH,
            "raw_source_sha256": RAW_SHA256,
            "raw_source_byte_count": RAW_BYTES,
            "output_count": len(output_evidence),
        },
        "input_bindings": {
            str(BASE): _sha(BASE),
            str(FROZEN): _sha(FROZEN),
            str(TREE): _sha(TREE),
            str(M108): _sha(M108),
            "scripts/reconcile_m112_mbs_bronze_projection_lineage.py": _sha(
                Path(__file__).relative_to(ROOT)
            ),
            "src/global_medicines_atlas/adapters/au_mbs.py": _sha(
                Path("src/global_medicines_atlas/adapters/au_mbs.py")
            ),
            "src/global_medicines_atlas/mbs_release.py": _sha(
                Path("src/global_medicines_atlas/mbs_release.py")
            ),
        },
        "outputs": [output_evidence[path] for path in sorted(output_evidence)],
        "boundaries": {
            "new_source_or_dataset_added": False,
            "frozen_inventory_changed": False,
            "raw_payload_retained_locally": False,
            "raw_payload_values_inspected": True,
            "derived_rights_or_licensing_conclusion_added": False,
            "source_rights_changed": False,
            "v4_admission_performed": False,
            "processing_admission_performed": False,
            "consumer_canary_performed": False,
            "public_release_performed": False,
        },
    }
    overlay = copy.deepcopy(base)
    evidence_ref = str(OUTPUT)
    evidence_digest = hashlib.sha256(
        (json.dumps(qualification, indent=2, sort_keys=True) + "\n").encode()
    ).hexdigest()
    changed: list[dict[str, Any]] = []
    for row in overlay["objects"]:
        bound = output_evidence.get(row.get("path"))
        if bound is None or row.get("dataset") != DATASET:
            continue
        previous = copy.deepcopy(row)
        row["b1_b2_lineage"] = {
            "complete": True,
            "state": "complete: exact MBS B2 input, producer B1 receipt/admission metadata, and both output digests independently reproduce from pinned source and code",
            "evidence": {"path": evidence_ref, "sha256": evidence_digest},
        }
        row["disposition"] = "deferred_not_admitted"
        row["v4_admission"] = False
        row["consumer_canary"] = False
        row["lineage_kind"] = "reproduced_mbs_bronze_projection"
        if row["rights"] != previous["rights"]:
            raise ValueError(
                "rights state changed while adding projection lineage"
            )
        changed.append(row)
    if len(changed) != EXPECTED_OUTPUT_COUNT:
        raise ValueError("expected exactly four changed frozen projection rows")

    complete_projection = EXPECTED_COMPLETE_PROJECTIONS + 4
    overlay["observed_at"] = OBSERVED_AT
    overlay["evidence_inputs"].append({
        "path": evidence_ref,
        "sha256": evidence_digest,
    })
    overlay["projection_b1_b2_lineage_expansion"] = {
        "prior_complete_projections": EXPECTED_COMPLETE_PROJECTIONS,
        "new_complete_projections": 4,
        "complete_projections_after_expansion": complete_projection,
        "qualification_path": evidence_ref,
        "qualification_sha256": evidence_digest,
    }
    overlay["updated_gate_totals"].update({
        "complete_raw_b1_b2_lineage": EXPECTED_COMPLETE_RAW,
        "complete_raw_b1_b2_lineage_paths": EXPECTED_COMPLETE_RAW,
        "complete_projection_lineage": complete_projection,
        "complete_b1_b2_lineage_objects": EXPECTED_COMPLETE_RAW
        + complete_projection,
        "preserved_deferrals": EXPECTED_DENOMINATOR,
        "v4_admissions": 0,
        "consumer_canaries": 0,
    })
    return qualification, overlay, changed


def _write(path: Path, value: dict[str, Any]) -> None:
    target = ROOT / path
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if target.exists() and target.read_bytes() != payload:
        raise ValueError(f"immutable qualification conflict: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def main() -> None:
    qualification, overlay, _ = _build_bindings()
    _write(OUTPUT, qualification)
    _write(OVERLAY_OUTPUT, overlay)
    print(f"qualified projections: {len(qualification['outputs'])}")
    print(
        f"complete projection lineages: {overlay['updated_gate_totals']['complete_projection_lineage']}"
    )
    print(
        f"complete B1/B2 lineages: {overlay['updated_gate_totals']['complete_b1_b2_lineage_objects']}"
    )


if __name__ == "__main__":
    main()
