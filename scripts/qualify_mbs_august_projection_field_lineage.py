"""Bind eight existing MBS projections to source-native field lineage.

Only retained public-safe metadata and historical Git code blobs are read. The
outside-frozen replay changed a writer footer and is not a historical-writer
execution. This packet neither acquires nor publishes a dataset, reads source
payloads, qualifies field meaning, or grants product admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed Git objects
from pathlib import Path
from typing import Any, cast

import scripts.qualify_m112_existing_reimbursement_batch as bounded
from jsonschema import Draft202012Validator

from global_medicines_atlas.adapters.au_mbs import MBS_NATIVE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
Q = "quality/qualifications/"
OUTPUT = Q + "australian-mbs-august-projection-v2-field-lineage-20261115.json"
REPORT = (
    Q
    + "australian-mbs-august-projection-field-lineage-qualification-20261115.json"
)
SOURCE = "raw/mbs/releases/2026-08-01/c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml"
SOURCE_SHA = "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
SOURCE_BYTES = 8_293_331
DATASET = "edithatogo/australian-mbs-source-archive"
FROZEN_REVISION = "243f9ff5498816af6e4d9ae4db60528728f01834"
OUTSIDE_REVISION = "b925a8a80b0f90db09513e7ce1378045461b05c0"
FIELD_COUNT = 40
SOURCE_RECORDS = 6046
OBJECT_COUNT = 8
RECORDS_PER_OBJECT = 85
SCHEMA = "contracts/medallion/v2/field-lineage.schema.json"
SCHEMA_SHA = "bf31ee62a3566a8fde512748b79f644e0fab760f60924e4eb9d510d3c1ef6f8a"
STATUS = "docs/qualification/mbs-xml-v3-field-semantics-status-2026-08.md"
STATUS_SHA = "2163c7e141bbad4e943894258da813b7ed48734227ac79dd42fd79100e35f6ce"
INPUTS = {
    "readiness": (
        Q + "australian-existing-v4-privacy-readiness-20261115.json",
        "84f76a2187830bf1e0949261df739f6eae45fb39f9c58750d7cdce09d4875d39",
    ),
    "digest": (
        Q + "australian-existing-mbs-digest-binding-20261115.json",
        "9f1211574b46c18bbb37cf47399c68a8c4197c2bb08f9aaccac96930566ed02f",
    ),
    "digest_receipt": (
        Q
        + "australian-existing-mbs-digest-20261115/hosted-43687742836/digest-receipt.json",
        "bbfd25983a89d7aba244a71bd2372b6c23f7d05cc2065a3506bf49e618f08191",
    ),
    "frozen_replay": (
        Q + "australian-m112-mbs-bronze-projection-lineage-20261019.json",
        "ef32417220d838e2cb625d8d0ab7a34009b99bdf3181314e5a4536442d0f1720",
    ),
    "dossiers": (
        Q + "australian-mbs-four-projection-dossiers-20261115.json",
        "0b3e7c53204695148b5b563e4bb7024cad421cc6cfa6ebf2c56f31af3a291d1e",
    ),
    "outside_replay": (
        Q + "australian-privacy-batch-20261115/mbs-outside-frozen-replay.json",
        "eeb694be498244d41fdec69f16f24a9cd135a54fa0420405b7b71751609717f0",
    ),
    "frozen_rights": (
        Q + "australian-mbs-august-bronze-rights-attestation-20261020.json",
        "8c1fe64099098ebe6e34ffe0409415d799e1a4c7c57382218fbfcfd52e0dbb24",
    ),
    "outside_rights": (
        Q
        + "australian-mbs-august-outside-m112-projection-rights-attestation-20261020.json",
        "dc5a53ffaed82e758bbe918f0615b5158bdbdf65ad41da2193c6c84ba41841c5",
    ),
    "profile": (
        Q + "mbs-source-era-candidate-2026-08-01-dmy-profile.json",
        "8e8d14f88baabc10a172fd2ec3947f8a89947828d64fb0237398dc230896763e",
    ),
    "receipt_6bc9": (
        "quality/bronze/receipts/au-mbs/f5626f2deb09f4301989480f112ec117ccad9efafc54c04d161100d6c5ca08e1.json",
        "ff916b49a4993b523da2f41952805b4e1e2064e0ce21edc8bd6643c1acda77a8",
    ),
    "receipt_99fa": (
        Q + "australian-privacy-batch-20261115/frozen-99-source-receipt.json",
        "4f694fd7364061cd05fee33ea52e6dbeef17d1067b8437f72e726ab168fc2fc7",
    ),
    "receipt_d781": (
        Q
        + "australian-mbs-four-projection-dossiers-20261115/d781-source-receipt.json",
        "24703e52245ac5605618c4d19be1cea4adc71f067e77a411b274be3b21d60bf7",
    ),
    "receipt_f9f9": (
        Q
        + "australian-mbs-four-projection-dossiers-20261115/f9f9-source-receipt.json",
        "e741e662dcdf1d64a187af46d8069effe6323b8664cdc90398c4adcb04cad90d",
    ),
}
PRODUCERS = {
    "6bc9": {
        "id": "6bc9bcb2e60728ac6d8b38ef76e9af15de32f026bb9ce83109df426a7f077c64",
        "commit": "0190183f6b313ad21746c5b15b7cf4bd7153085c",
        "frozen": True,
    },
    "99fa": {
        "id": "99fada49ebf8e71e8e14417e9275f36840d46577a39746fea02bd89de30a30fc",
        "commit": "435527a630d055056985372aba1620bcf7340da4",
        "frozen": True,
    },
    "d781": {
        "id": "d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b",
        "commit": "12e5ca4678e077f8e6bf954aaa780aac83040994",
        "frozen": False,
    },
    "f9f9": {
        "id": "f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63",
        "commit": "644f3f6cfd2b76b0866d5ecb90dde397d67a51eb",
        "frozen": False,
    },
}
ADAPTER = "src/global_medicines_atlas/adapters/au_mbs.py"
RELEASE = "src/global_medicines_atlas/mbs_release.py"
SELECTOR = "src/global_medicines_atlas/mbs_compatibility.py"
ADAPTER_SHA = "f874882bb7e0d3675b791e6cc10393595c705f7b2a977dcff1388a0c27862363"
OLD_RELEASE_SHA = (
    "41b344750a8612f97b3f49f19505523335e2eb4b8808be35a1a8aaaa70814fad"
)
NEW_RELEASE_SHA = (
    "d59e04b58783912b557dff53ee536a3cbf7d39725ebb2e77d11bedfc29417828"
)
OLD_SELECTOR_SHA = (
    "2a1d1a5d3709776504b9d9aeec4f708d0e304fa7b8de99b343418f75131c42d7"
)
NEW_SELECTOR_SHA = (
    "3d7a4263a020a7f9569968b3007f5d10a8a52b067154eed67281bd5a52eae111"
)


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def code_hashes(name: str) -> dict[str, str]:
    """Return independently pinned historical producer blob digests."""
    return {
        ADAPTER: ADAPTER_SHA,
        RELEASE: NEW_RELEASE_SHA if name == "f9f9" else OLD_RELEASE_SHA,
        SELECTOR: OLD_SELECTOR_SHA
        if name in {"6bc9", "99fa"}
        else NEW_SELECTOR_SHA,
    }


def check_producer_code(root: Path = ROOT) -> None:
    """Check twelve fixed Git blobs; no payloads or network are read."""
    git = shutil.which("git")
    _require(git is not None, "Git is unavailable for producer code checks")
    for name, producer in PRODUCERS.items():
        for path, expected in code_hashes(name).items():
            result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed commit/path
                [str(git), "show", f"{producer['commit']}:{path}"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            _require(
                _sha(result.stdout) == expected,
                "historical producer code differs",
            )


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {row["path"]: row for row in rows}
    _require(len(result) == len(rows), "duplicate projection identity")
    return result


def _records(
    item: dict[str, Any], producer: dict[str, Any], rights: str
) -> list[dict[str, Any]]:
    fields: list[tuple[str, str, str]] = []
    for native in MBS_NATIVE_FIELDS:
        for output, transformation in (
            ("fields[].name", "xml-child-local-name"),
            ("fields[].value", "xml-child-text-or-null"),
        ):
            fields.append((f"/MBS_XML/Data/{native}", output, transformation))
    fields.extend(
        (
            f"/MBS_XML/Data/{native}",
            "source_record_id",
            "source-record-identity",
        )
        for native in ("ItemNum", "SubItemNum", "ItemStartDate")
    )
    fields.extend((
        (
            "/MBS_XML/Data[position()]",
            "source_record_id",
            "source-record-identity",
        ),
        (
            "/MBS_XML/Data[position()]",
            "source_ordinal",
            "source-record-ordinal",
        ),
    ))
    result: list[dict[str, Any]] = []
    for source_field, output_field, transformation in fields:
        row: dict[str, Any] = {
            "source_dataset": SOURCE,
            "source_field": source_field,
            "transformation_id": "au-mbs-bronze:" + transformation,
            "output_dataset": item["path"],
            "output_field": output_field,
            "code_version": "git:" + str(producer["commit"]),
            "input_sha256": SOURCE_SHA,
            "output_sha256": item["sha256"],
            "rights_decision_id": rights,
        }
        result.append({"record_id": _sha(_canonical(row)), **row})
    _require(
        len(result) == RECORDS_PER_OBJECT, "field lineage denominator differs"
    )
    return result


def reconcile(  # ruff: ignore[too-many-locals] -- preserve per-object evidence joins
    e: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Join all eight exact paths and preserve replay and privacy limitations."""
    candidates = [
        r
        for r in e["readiness"]["mbs_objects"]
        if r["path"].endswith(("/p7.parquet", "/source.parquet"))
    ]
    rows = _index(candidates)
    digest = _index([r for r in e["digest"]["objects"] if r["path"] in rows])
    observed = _index([
        r for r in e["digest_receipt"]["objects"] if r["path"] in rows
    ])
    frozen = _index(e["frozen_replay"]["outputs"])
    outside = _index(e["outside_replay"]["objects"])
    dossiers = _index(e["dossiers"]["dossiers"])
    rights = {
        name: _index(e[name]["authorized_objects"])
        for name in ("frozen_rights", "outside_rights")
    }
    profile = e["profile"]
    diagnostics = profile["field_presence_diagnostics"]
    _require(
        len(rows) == len(digest) == len(observed) == OBJECT_COUNT
        and len(frozen) == len(outside) == len(dossiers) == OBJECT_COUNT // 2
        and set(frozen).isdisjoint(outside)
        and set(frozen) | set(outside) == set(rows)
        and len(MBS_NATIVE_FIELDS)
        == len(set(MBS_NATIVE_FIELDS))
        == len(diagnostics)
        == FIELD_COUNT
        and {r["native_field"] for r in diagnostics} == set(MBS_NATIVE_FIELDS)
        and all(
            r["rows"] == SOURCE_RECORDS and r["presence_state_mismatches"] == 0
            for r in diagnostics
        )
        and profile["source_presence_projection_alignment"] == "matched"
        and profile["qualification"]["source_sha256"] == SOURCE_SHA
        and profile["qualification"]["source_byte_count"] == SOURCE_BYTES
        and e["digest_receipt"]["workflow_run"] == "43687742836"
        and e["digest_receipt"]["boundaries"][
            "payload_bytes_persisted_or_emitted"
        ]
        is False,
        "source profile or projection inventory differs",
    )
    records: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    for name, producer in PRODUCERS.items():
        receipt = e["receipt_" + name]
        sensitivity = receipt["sensitivity"]
        _require(
            receipt["source"]["source_id"] == "au-mbs"
            and receipt["source"]["catalog_version"] == "2026-08-01"
            and receipt["payload"]["sha256"] == SOURCE_SHA
            and receipt["payload"]["byte_count"] == SOURCE_BYTES
            and sensitivity["data_sensitivity"] == "non_sensitive"
            and sensitivity["personal_data"] == "none"
            and receipt["retrieval"]["http"][
                "acquisition_agent_version"
            ].endswith("g" + str(producer["commit"])[:9]),
            "producer receipt or source privacy differs",
        )
        for filename in ("p7.parquet", "source.parquet"):
            path = f"bronze/mbs/releases/2026-08-01/{producer['id']}/{filename}"
            _require(
                path in rows and path in digest and path in observed,
                "projection path missing",
            )
            row, verified = rows[path], observed[path]
            rights_key = (
                "frozen_rights" if producer["frozen"] else "outside_rights"
            )
            auth = rights[rights_key].get(path)
            _require(
                isinstance(auth, dict)
                and row["dataset"] == DATASET
                and row["revision"]
                == (FROZEN_REVISION if producer["frozen"] else OUTSIDE_REVISION)
                and row["privacy"] == "source_profile_assessed_non_sensitive"
                and row["frozen_member"] is producer["frozen"]
                and all(
                    row[k] == digest[path][k] == verified[k]
                    for k in (
                        "dataset",
                        "revision",
                        "path",
                        "sha256",
                        "byte_count",
                    )
                )
                and all(
                    row[k] == auth[k] for k in ("path", "sha256", "byte_count")
                )
                and e[rights_key]["public_release_rights_attested"] is True,
                "projection identity, privacy or rights differs",
            )
            if producer["frozen"]:
                replay = frozen[path]
                _require(
                    replay["sha256"] == row["sha256"]
                    and replay["byte_count"] == row["byte_count"]
                    and replay["source_sha256"] == SOURCE_SHA
                    and replay["source_receipt_sha256"]
                    == INPUTS["receipt_" + name][1]
                    and replay["transformation"][
                        "reproduced_exact_bytes_in_memory"
                    ]
                    is True,
                    "frozen projection replay differs",
                )
                replay_status = (
                    "exact_bytes_reproduced_in_memory_at_prior_revision"
                )
            else:
                replay, dossier = outside[path], dossiers[path]
                _require(
                    all(
                        row[k] == replay[k]
                        for k in (
                            "dataset",
                            "revision",
                            "path",
                            "sha256",
                            "byte_count",
                        )
                    )
                    and replay["exact_digest_after_footer_substitution"] is True
                    and replay["unadjusted_sha256"] != row["sha256"]
                    and replay["footer_adjusted_sha256"] == row["sha256"]
                    and all(
                        row[k] == dossier[k]
                        for k in (
                            "dataset",
                            "revision",
                            "path",
                            "sha256",
                            "byte_count",
                        )
                    )
                    and dossier["source_receipt"] == name + "_receipt",
                    "outside projection footer-adjusted replay differs",
                )
                replay_status = (
                    "footer_adjusted_reproduction_not_historical_writer"
                )
            records.extend(_records(row, producer, INPUTS[rights_key][1]))
            objects.append({
                **{
                    k: row[k]
                    for k in (
                        "dataset",
                        "revision",
                        "path",
                        "sha256",
                        "byte_count",
                        "frozen_member",
                    )
                },
                "producer_commit": producer["commit"],
                "producer_code_sha256": code_hashes(name),
                "source_receipt": {
                    "path": INPUTS["receipt_" + name][0],
                    "sha256": INPUTS["receipt_" + name][1],
                },
                "rights_evidence": {
                    "path": INPUTS[rights_key][0],
                    "sha256": INPUTS[rights_key][1],
                },
                "selection": "Group=P7"
                if filename == "p7.parquet"
                else "all_source_records",
                "expected_records_from_existing_evidence": 165
                if filename == "p7.parquet"
                else 6046,
                "field_lineage_records": RECORDS_PER_OBJECT,
                "reproduction": replay_status,
                "field_semantics_accepted": False,
                "v4_admission": "not_performed",
                "consumer_check": "not_performed",
            })
    _require(
        len(objects) == OBJECT_COUNT
        and len(records) == OBJECT_COUNT * RECORDS_PER_OBJECT
        and len({r["record_id"] for r in records}) == len(records),
        "projection lineage result differs",
    )
    vocabulary = {"vocabulary_version": "2.0.0", "records": records}
    report = {
        "schema_id": "global-medicines-atlas.mbs-august-projection-field-lineage",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            name: {"path": p, "sha256": h} for name, (p, h) in INPUTS.items()
        },
        "semantics_status": {"path": STATUS, "sha256": STATUS_SHA},
        "v2_schema": {"path": SCHEMA, "sha256": SCHEMA_SHA},
        "v2_lineage": {
            "path": OUTPUT,
            "sha256": _sha(
                (
                    json.dumps(vocabulary, sort_keys=True, indent=2) + "\n"
                ).encode()
            ),
            "canonical_sha256": _sha(_canonical(vocabulary)),
            "records": len(records),
            "canonicalization": "sorted_compact_utf8_json",
        },
        "objects": objects,
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "field_semantics_accepted": False,
            "historical_writer_executed_for_outside_outputs": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "independent_recovery_established": False,
            "dataset_added_or_published": False,
        },
    }
    return vocabulary, report


def build(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    for path, expected in ((SCHEMA, SCHEMA_SHA), (STATUS, STATUS_SHA)):
        _require(
            _sha((root / path).read_bytes()) == expected,
            "schema or semantic status differs",
        )
    e = {
        name: bounded.read_bound_metadata(root, path, digest)
        for name, (path, digest) in INPUTS.items()
    }
    vocabulary, report = reconcile(e)
    cast(
        "Any", Draft202012Validator(json.loads((root / SCHEMA).read_bytes()))
    ).validate(vocabulary)
    return vocabulary, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-producer-code", action="store_true")
    args = parser.parse_args()
    if args.check_producer_code:
        check_producer_code()
    vocabulary, report = build()
    for path, value in ((OUTPUT, vocabulary), (REPORT, report)):
        expected = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
        destination = ROOT / path
        if args.check:
            _require(
                destination.is_file() and destination.read_bytes() == expected,
                "projection lineage output is stale",
            )
        else:
            destination.write_bytes(expected)
    print(
        "Eight MBS projection field lineages checked; no payload read or admission"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
