"""Qualify exact PBS raw-B2 trust, receipt closure and hosted reader canaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

import httpx

if __package__:
    from . import m112_pbs_utilisation_replay as pbs
    from .qualify_m112_v4_july2016_admission import (
        _download_receipt,  # pyright: ignore[reportPrivateUsage]
        run_reader_canary,
        validate_contract,
    )
else:
    import m112_pbs_utilisation_replay as pbs
    from qualify_m112_v4_july2016_admission import (
        _download_receipt,  # pyright: ignore[reportPrivateUsage]  # ruff: ignore[import-private-name] -- reuse the qualified read-only receipt adapter
        run_reader_canary,
        validate_contract,
    )

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_admission import (
    TrustedAdmissionProfile,
    admit_closed_contract,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.federation_receipt_closure import (
    MAX_RECEIPT_BYTES,
    MAX_TOTAL_BYTES,
    ReceiptClosure,
    ReceiptPayload,
    ReceiptRole,
    contract_receipt_roles,
    verify_receipt_closure,
)

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = Path(
    "quality/qualifications/australian-m112-pbs-v4-contract-candidates-20261028"
)
MANIFEST = DIRECTORY / "manifest.json"
MANIFEST_SHA256 = (
    "cfeb7aada59155023420d760f86a85809850c429b74ff1f10a61031a68d0f4a2"
)
SCHEMA = Path("contracts/medallion/v4.1/federation.schema.json")
SCHEMA_COMMIT = "a5753b1c79ccedd9bb54112bf803882ffc9deb96"
SCHEMA_SHA256 = (
    "03acfbafd80daf0b8b768f7814dbb29a9bd13e7c9d5d68797b30261da29770c6"
)
EVIDENCE_COMMIT = "849c6b7fcaa0241e76e64590cc076e071d1ef4b8"
ASSESSMENT_COMMIT = "156d3e5cd91735b4766b86bd89cada06a44b7b67"
ASSESSMENT = pbs.QUAL + (
    "australian-m112-pbs-utilisation-role-readiness-20261028.json"
)
ASSESSMENT_SHA256 = (
    "fb680271214008a850416151529a51933b16cb8b1521ec156c360872cd46d4b2"
)
V1 = pbs.QUAL + "australian-m112-pbs-utilisation-v1-conformance-20261028.json"
V1_SHA256 = "8e1e783f1e24288645f4b2895933e17dd0db9fdc846b1ee5f842615ca66fd100"
REPLAYS = (
    pbs.QUAL + "australian-m112-pbs-v3-replays-20261028/replay-manifest.json"
)
REPLAYS_SHA256 = (
    "181877c25380042f277ae7e652b178cea50f3b59f0fcb82f4b38923ee380a770"
)
REPOSITORY = "edithatogo/global-medicines-atlas"


def _read(root: Path, relative: str | Path, digest: str) -> dict[str, Any]:
    body = (root / relative).read_bytes()
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("PBS admission evidence digest mismatch")
    value: Any = json.loads(body)
    if not isinstance(value, dict):
        raise TypeError("PBS admission evidence must be an object")
    return cast("dict[str, Any]", value)


def _reference(
    relative: str, digest: str, commit: str = EVIDENCE_COMMIT
) -> dict[str, str]:
    return {
        "url": f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{relative}",
        "sha256": digest,
    }


def load_candidate(  # ruff: ignore[too-many-locals] -- preserve the independent evidence join
    root: Path = ROOT, *, target_path: str
) -> tuple[bytes, TrustedAdmissionProfile]:
    """Bind exact contract bytes to trust derived from source evidence only."""
    manifest = _read(root, MANIFEST, MANIFEST_SHA256)
    selected = [
        row for row in manifest["objects"] if row["path"] == target_path
    ]
    if len(selected) != 1:
        raise ValueError("target is not an exact PBS admission candidate")
    row = selected[0]
    contract_path = Path(row["contract_path"])
    if contract_path.parent != DIRECTORY:
        raise ValueError("PBS contract must be an exact candidate file")
    raw = (root / contract_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["contract_sha256"]:
        raise ValueError("PBS candidate contract digest mismatch")
    if validate_contract(json.loads(raw), root=root) != raw:
        raise ValueError("PBS candidate serialization differs")
    if (
        hashlib.sha256((root / SCHEMA).read_bytes()).hexdigest()
        != SCHEMA_SHA256
    ):
        raise ValueError("PBS admission schema digest differs")
    snapshot, size = pbs.build_snapshot(root, target_path=target_path)
    lineage = _read(root, pbs.LINEAGE, pbs.INPUT_DIGESTS[pbs.LINEAGE])
    landed = next(x for x in lineage["objects"] if x["path"] == target_path)
    event_path = landed["acquisition_event_path"]
    event = _read(root, event_path, lineage["output_bindings"][event_path])
    assessment = _read(root, ASSESSMENT, ASSESSMENT_SHA256)
    assessed = next(
        x for x in assessment["objects"] if x["path"] == target_path
    )
    if (
        assessed["sensitivity_assessment"]["data_sensitivity"]
        != "non_sensitive"
    ):
        raise ValueError("PBS source-specific sensitivity is not qualified")
    replays = _read(root, REPLAYS, REPLAYS_SHA256)
    replay = next(x for x in replays["objects"] if x["path"] == target_path)
    if (
        replay["status"] != "passed"
        or replay["sha256"] != snapshot["payload_sha256"]
    ):
        raise ValueError("PBS exact replay evidence differs")
    _read(root, V1, V1_SHA256)
    _read(root, replay["receipt"]["path"], replay["receipt"]["sha256"])
    expected = [
        {
            "url": f"https://huggingface.co/datasets/{pbs.DATASET}/resolve/{pbs.REVISION}/{landed['receipt_path']}",
            "sha256": landed["receipt_sha256"],
        },
        _reference(event_path, lineage["output_bindings"][event_path]),
        _reference(landed["b2_manifest_path"], landed["b2_manifest_sha256"]),
        _reference(ASSESSMENT, ASSESSMENT_SHA256, ASSESSMENT_COMMIT),
    ]
    lineage_roles = [
        ReceiptRole(role=f"/lineage/inputs/{index}", **ref)
        for index, ref in enumerate(expected)
    ]
    lineage_roles.extend([
        ReceiptRole(
            role="/lineage/v1_conformance", **_reference(V1, V1_SHA256)
        ),
        ReceiptRole(
            role="/lineage/v3_replay",
            **_reference(
                replay["receipt"]["path"], replay["receipt"]["sha256"]
            ),
        ),
    ])
    trusted = TrustedAdmissionProfile(
        producer_repository=REPOSITORY,
        contract_repository=REPOSITORY,
        contract_commit=SCHEMA_COMMIT,
        schema_sha256=SCHEMA_SHA256,
        dataset=pbs.DATASET,
        revision=pbs.REVISION,
        path=target_path,
        byte_count=size,
        sha256=snapshot["payload_sha256"],
        source_id=snapshot["source_id"],
        acquisition_id=landed["acquisition_id"],
        layer="bronze",
        bronze_stratum="B2",
        representation="raw",
        schema_era="unqualified-native-schema",
        comparison_cohort="legacy",
        effective_date=None,
        retrieved_at=event["retrieved_at"],
        evidence_kind="live",
        authorization=ReceiptRole(
            role="/rights/authorization",
            **_reference(
                pbs.RIGHTS_ATTESTATION,
                pbs.INPUT_DIGESTS[pbs.RIGHTS_ATTESTATION],
            ),
        ),
        lineage=tuple(lineage_roles),
    )
    return raw, trusted


def receipt_closure(raw: bytes, *, root: Path = ROOT) -> ReceiptClosure:
    """Fetch opaque metadata once per URL through the existing guarded route."""
    schema = (root / SCHEMA).read_bytes()
    roles = contract_receipt_roles(raw, schema=schema)
    policy = AcquisitionPolicy(
        allowed_hosts=tuple(
            sorted(set(HOSTS) | {"raw.githubusercontent.com", "api.github.com"})
        ),
        max_bytes=MAX_RECEIPT_BYTES,
        timeout_seconds=30,
        max_attempts=1,
        max_redirects=3,
    )
    payloads: dict[str, bytes] = {}
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        follow_redirects=True,
        timeout=30,
        trust_env=False,
    ) as client:
        for role in roles:
            if role.url in payloads:
                continue
            body = _download_receipt(role.url, client)
            if (
                len(body) > MAX_RECEIPT_BYTES
                or sum(map(len, payloads.values())) + len(body)
                > MAX_TOTAL_BYTES
            ):
                raise ValueError("PBS receipt byte budget exceeded")
            payloads[role.url] = body
    return verify_receipt_closure(
        raw,
        tuple(
            ReceiptPayload(url=url, payload=body)
            for url, body in sorted(payloads.items())
        ),
        schema=schema,
    )


def qualify(
    *, target_path: str, workflow_commit: str, root: Path = ROOT
) -> dict[str, Any]:
    """Require exact-main execution before receipt admission and source reads."""
    require_hosted_main(workflow_commit)
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if not attempt.isdigit() or int(attempt) < 1:
        raise ValueError("PBS qualification requires a valid workflow attempt")
    raw, trusted = load_candidate(root, target_path=target_path)
    closure = receipt_closure(raw, root=root)
    admission = admit_closed_contract(
        raw, closure, schema=(root / SCHEMA).read_bytes(), trusted=trusted
    )
    canary = run_reader_canary(
        raw,
        admission.model_dump(mode="json"),
        workflow_commit=workflow_commit,
        workflow_run_id=os.environ["GITHUB_RUN_ID"],
        workflow_run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
        root=root,
    )
    return {
        "schema_id": "global-medicines-atlas.m112-pbs-v4-admission-reader-qualification",
        "schema_version": 1,
        "status": "passed",
        "admission": admission.model_dump(mode="json"),
        "receipt_closure": closure.model_dump(mode="json"),
        "consumer_canary": canary,
        "boundaries": {
            "public_dataset_mutated": False,
            "new_sources": 0,
            "source_values_interpreted": False,
            "independent_recovery_qualified": False,
            "federation_gate_closed": False,
        },
    }


def main() -> None:
    """Check exact local policy or execute one protected hosted qualification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-path", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--workflow-commit")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.check:
        raw, trusted = load_candidate(target_path=args.target_path)
        print(
            json.dumps({
                "status": "candidate_policy_checked_not_admitted",
                "contract_sha256": hashlib.sha256(raw).hexdigest(),
                "path": trusted.path,
            })
        )
        return
    if args.workflow_commit is None or args.report is None:
        parser.error("--verify requires --workflow-commit and --report")
    report = qualify(
        target_path=args.target_path, workflow_commit=args.workflow_commit
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
