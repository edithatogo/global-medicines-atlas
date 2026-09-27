#!/usr/bin/env python3
"""Hosted-only, append-only publication of the qualified MBS Silver v4."""

# The pinned optional Hub client and its response models are installed only in
# the protected workflow; the typed core package owns the publication contract.
# pyright: reportMissingImports=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportIndexIssue=false, reportArgumentType=false

from __future__ import annotations

import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from datetime import datetime
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from pydantic import AnyUrl
from scripts.qualify_public_mbs_silver import qualify

from global_medicines_atlas.mbs_silver_publication import (
    DESTINATION_DATASET,
    DESTINATION_PREFIX,
    MBS_SOURCE_URI,
    build_mbs_silver_v4_package,
)
from global_medicines_atlas.mbs_silver_qualification import (
    OFFICIAL_MBS_V3_URI,
    MbsSourceEraVerification,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    DataSensitivity,
    EvidenceClass,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    RetrievalEvidence,
    RightsState,
    SensitivityClassification,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    temporal_identity_from_source,
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:  # ruff: ignore[too-many-locals]
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or not os.environ.get("HF_TOKEN")
    ):
        raise RuntimeError(
            "MBS Silver publication requires protected main Actions"
        )
    hub_client: Any = import_module("huggingface_hub")
    commit_operation_add = hub_client.CommitOperationAdd
    hf_api = hub_client.HfApi
    hf_hub_download = hub_client.hf_hub_download

    commit = os.environ["GITHUB_SHA"]
    root = Path.cwd()
    work = root / "build/mbs-silver-publication"
    work.mkdir(parents=True, exist_ok=True)
    report: Any = json.loads(json.dumps(qualify(exact_commit=commit)))
    source_path = Path(
        hf_hub_download(
            repo_id=DESTINATION_DATASET,
            repo_type="dataset",
            revision="4d1dae488ac43522f20e8320a8b2a56bf9138341",
            filename="raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML",
            token=False,
            cache_dir=work / "restore-cache",
        )
    )
    payload = source_path.read_bytes()
    official = report["official_release_check"]
    if (
        not official["matched_pinned_archive"]
        or _sha256(source_path) != official["source_sha256"]
    ):
        raise RuntimeError(
            "public MBS source does not match the official release"
        )
    retrieved_at = datetime.fromisoformat(report["retrieved_at"])
    source_hash = _sha256(source_path)
    receipt = SourceReceipt(
        receipt_id=f"public-archive:au-mbs:{source_hash}",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="July 2025 Medicare Benefits Schedule XML",
            catalog_version="2025-07-version-3",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(MBS_SOURCE_URI),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence.from_bytes(payload),
        temporal=temporal_identity_from_source(
            retrieved_at=retrieved_at,
            source_id="au-mbs",
            payload_sha256=source_hash,
            source_version="2025-07-version-3",
            original_uri=MBS_SOURCE_URI,
        ),
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://github.com/edithatogo/global-medicines-atlas/issues/340"
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PERMITTED,
            reason_codes=(
                "qualified_official_mbs_schedule",
                "exact_release_approval",
            ),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="exact-public-source-restore-v1",
            transformation_sha256=sha256(commit.encode("ascii")).hexdigest(),
            output_sha256=source_hash,
            output_byte_count=len(payload),
        ),
    )
    verification = MbsSourceEraVerification(
        official_source_uri=AnyUrl(OFFICIAL_MBS_V3_URI),
        release_id=official["release_id"],
        released_at=official["released_at"],
        effective_at=official["effective_at"],
        official_source_sha256=official["source_sha256"],
        official_source_byte_count=official["source_byte_count"],
        compared_at=datetime.fromisoformat(
            report["qualification"]["source_era_verification"]["compared_at"]
        ),
    )
    package = build_mbs_silver_v4_package(
        payload,
        receipt,
        exact_commit=commit,
        source_era_verification=verification,
        output_dir=work / "package",
        repository_root=root,
    )

    public: Any = hf_api(token=False)
    before = public.dataset_info(DESTINATION_DATASET, files_metadata=True)
    if before.private or before.gated:
        raise RuntimeError("MBS destination is not anonymously public")
    files = package.files
    paths = set(files)
    before_siblings: list[Any] = cast("list[Any]", before.siblings or [])
    sibling_names: set[str] = {item.rfilename for item in before_siblings}
    if sibling_names.intersection(paths):
        raise RuntimeError("destination already contains a Silver v4 path")
    # Durable public intent must precede the append transaction.
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [  # ruff: ignore[start-process-with-partial-path]
            "gh",
            "issue",
            "comment",
            "340",
            "--body",
            f"MBS Silver v4 publication intent: exact_commit={commit}; run=https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}; dataset={DESTINATION_DATASET}; prefix={DESTINATION_PREFIX}; append-only; candidate remains unpromoted.",
        ],
        check=True,
    )
    result: Any = hf_api(token=os.environ["HF_TOKEN"]).create_commit(
        repo_id=DESTINATION_DATASET,
        repo_type="dataset",
        parent_commit=before.sha,
        commit_message="Publish qualified July 2025 MBS Silver v4 candidate",
        operations=[
            commit_operation_add(path_in_repo=name, path_or_fileobj=str(path))
            for name, path in sorted(files.items())
        ],
    )
    after = public.dataset_info(
        DESTINATION_DATASET, revision=result.oid, files_metadata=True
    )
    if after.private or after.gated or after.sha != result.oid:
        raise RuntimeError("anonymous exact-revision readback failed")
    expected_names = sibling_names | paths
    after_siblings: list[Any] = cast("list[Any]", after.siblings or [])
    if {item.rfilename for item in after_siblings} != expected_names:
        raise RuntimeError("append changed the existing sibling inventory")
    verified: list[dict[str, str | int]] = []
    for name, path in sorted(files.items()):
        anonymous_path = Path(
            hf_hub_download(
                repo_id=DESTINATION_DATASET,
                repo_type="dataset",
                revision=result.oid,
                filename=name,
                token=False,
                cache_dir=work / "verify-cache",
            )
        )
        if anonymous_path.stat().st_size != path.stat().st_size or _sha256(
            anonymous_path
        ) != _sha256(path):
            raise RuntimeError(
                "anonymous per-object digest verification failed"
            )
        verified.append({
            "path": name,
            "sha256": _sha256(path),
            "byte_count": path.stat().st_size,
        })
    receipt_path = work / "hosted-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_id": "global-medicines-atlas.mbs-silver-v4-hosted-publication",
                "dataset": DESTINATION_DATASET,
                "revision": result.oid,
                "parent_revision": before.sha,
                "producer_commit": commit,
                "manifest_sha256": package.manifest_sha256,
                "verified_objects": verified,
                "legacy_paths_preserved": len(sibling_names),
                "anonymous_digest_verification": "passed",
                "candidate_only": True,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ["gh", "issue", "comment", "340", "--body-file", str(receipt_path)],  # ruff: ignore[start-process-with-partial-path]
        check=True,
    )
    shutil.rmtree(work, ignore_errors=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
