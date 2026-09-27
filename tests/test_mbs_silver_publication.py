"""Deterministic, receipt-bound packaging for MBS Silver v4 publication."""

import json
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, ClassVar

import pyarrow.parquet as pq
import pytest
from pydantic import AnyUrl
from scripts import publish_australian_mbs_silver_v4 as hosted_publisher

from global_medicines_atlas import mbs_silver_publication
from global_medicines_atlas.mbs_silver_publication import (
    DESTINATION_PREFIX,
    MBS_SOURCE_URI,
    build_mbs_silver_v4_package,
    validate_mbs_silver_v4_package,
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


def _xml(body: str) -> bytes:
    row = f"<Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum>{body}</Data>"
    return f"<MBS_XML>{row}</MBS_XML>".encode()


def _authorized_receipt(
    payload: bytes, commit: str = "b" * 40
) -> SourceReceipt:
    digest = sha256(payload).hexdigest()
    retrieved_at = datetime(2026, 8, 29, 8, 57, 21, tzinfo=UTC)
    return SourceReceipt(
        receipt_id=f"public-archive:au-mbs:{digest}",
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
            payload_sha256=digest,
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
            output_sha256=digest,
            output_byte_count=len(payload),
        ),
    )


def _verification(payload: bytes) -> MbsSourceEraVerification:
    return MbsSourceEraVerification(
        official_source_uri=AnyUrl(OFFICIAL_MBS_V3_URI),
        release_id="MBS-XML-20250701 Version 3",
        released_at=date(2025, 6, 16),
        effective_at=date(2025, 7, 1),
        official_source_sha256=sha256(payload).hexdigest(),
        official_source_byte_count=len(payload),
        compared_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


def test_package_is_deterministic_and_contains_all_six_source_faithful_tables(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_silver_publication._authorization_identity",
        lambda *_: ("a" * 64, "b" * 64),
    )
    payload = _xml(
        "<ItemStartDate>30.08.2026</ItemStartDate>"
        "<ScheduleFee>42.500</ScheduleFee>"
        "<Benefit85>85.00</Benefit85>"
        "<Description>Example service</Description>"
    )
    receipt = _authorized_receipt(payload, "b" * 40)
    verification = _verification(payload)
    first = build_mbs_silver_v4_package(
        payload,
        receipt,
        exact_commit="b" * 40,
        source_era_verification=verification,
        output_dir=tmp_path / "first",
    )
    second = build_mbs_silver_v4_package(
        payload,
        receipt,
        exact_commit="b" * 40,
        source_era_verification=verification,
        output_dir=tmp_path / "second",
    )

    assert first.manifest_sha256 == second.manifest_sha256
    assert first.destination_prefix == DESTINATION_PREFIX
    assert set(first.files) == set(second.files)
    assert {name: path.read_bytes() for name, path in first.files.items()} == {
        name: path.read_bytes() for name, path in second.files.items()
    }
    assert len(first.objects) == 8  # six tables, B1 receipt, qualification
    assert "source.xml" not in first.files
    manifest = json.loads(first.manifest_path.read_text())
    assert manifest["candidate_only"] is True
    assert manifest["source"]["sha256"] == sha256(payload).hexdigest()
    assert manifest["source"]["receipt_sha256"] == receipt.digest()
    assert manifest["official_release"]["release_id"] == (
        "MBS-XML-20250701 Version 3"
    )
    assert manifest["authorization_basis"]["destination"] == (
        "edithatogo/australian-mbs-source-archive"
    )

    validate_mbs_silver_v4_package(first)
    services_path = first.files[f"{DESTINATION_PREFIX}/services.parquet"]
    services = pq.read_table(services_path)
    assert services.schema.metadata[b"schema_version"] == b"1.1"
    assert services.column("ItemStartDate")[0].as_py()["native_value"] == (
        "30.08.2026"
    )


@pytest.mark.parametrize(
    "mutation",
    ["payload", "receipt", "manifest", "missing_object", "extra_object"],
)
def test_package_validation_rejects_any_drift(
    tmp_path, mutation: str, monkeypatch
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_silver_publication._authorization_identity",
        lambda *_: ("a" * 64, "b" * 64),
    )
    payload = _xml("<ScheduleFee>42.00</ScheduleFee>")
    package = build_mbs_silver_v4_package(
        payload,
        _authorized_receipt(payload, "c" * 40),
        exact_commit="c" * 40,
        source_era_verification=_verification(payload),
        output_dir=tmp_path / "package",
    )
    if mutation == "payload":
        package.objects[0].path.write_bytes(b"changed")
    elif mutation == "receipt":
        next(
            item.path
            for item in package.objects
            if item.role == "b1_source_receipt"
        ).write_bytes(b"changed")
    elif mutation == "manifest":
        package.manifest_path.write_bytes(b"{}")
    elif mutation == "missing_object":
        package.objects[0].path.unlink()
    else:
        (package.path / "unmanifested.bin").write_bytes(b"extra")

    with pytest.raises(ValueError, match=r"package|object|manifest|receipt"):
        validate_mbs_silver_v4_package(package)


def test_static_publication_authority_binds_exact_donor_payload() -> None:
    authorization = json.loads(
        Path(
            "quality/qualifications/"
            "australian-health-legacy-publication-authorization.json"
        ).read_text(encoding="utf-8")
    )
    authorized = authorization["donors"][0]["payloads"][0]
    receipt = _authorized_receipt(b"authority probe").model_copy(
        update={
            "payload": PayloadEvidence(
                sha256=authorized["sha256"], byte_count=authorized["bytes"]
            )
        }
    )
    authorization_hash, decision_hash = (
        mbs_silver_publication._authorization_identity(Path.cwd(), receipt)
    )
    assert len(authorization_hash) == 64
    assert len(decision_hash) == 64

    mismatched_receipt = receipt.model_copy(
        update={"payload": PayloadEvidence(sha256="0" * 64, byte_count=0)}
    )
    with pytest.raises(ValueError, match="authorization differs"):
        mbs_silver_publication._authorization_identity(
            Path.cwd(), mismatched_receipt
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("commit", "producer commit"),
        ("payload", "B1 receipt"),
        ("rights", "not publishable"),
        ("transform", "bound to this producer commit"),
        ("source_era", "source era or conversion quality is blocked"),
        ("qualification_source", "qualification differs from B2"),
        ("empty_table", "table is empty"),
    ],
)
def test_package_builder_fails_closed_on_receipt_and_qualification_drift(
    tmp_path, monkeypatch, mutation: str, message: str
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_silver_publication._authorization_identity",
        lambda *_: ("a" * 64, "b" * 64),
    )
    payload = _xml("<ScheduleFee>42.00</ScheduleFee>")
    receipt = _authorized_receipt(payload, "f" * 40)
    verification = _verification(payload)
    call_payload = payload
    commit = "f" * 40
    if mutation == "commit":
        commit = "invalid"
    elif mutation == "payload":
        call_payload = payload + b"drift"
    elif mutation == "rights":
        receipt = receipt.model_copy(
            update={"rights_state": RightsState.UNKNOWN}
        )
    elif mutation == "transform":
        receipt = receipt.model_copy(
            update={
                "transformation": receipt.transformation.model_copy(
                    update={"transformation_sha256": "a" * 64}
                )
            }
        )
    elif mutation == "source_era":
        monkeypatch.setattr(
            mbs_silver_publication,
            "qualify_mbs_silver",
            lambda *_args, **_kwargs: SimpleNamespace(
                blockers=("real_source_era_unqualified",),
                source_sha256=sha256(payload).hexdigest(),
            ),
        )
    elif mutation == "qualification_source":
        monkeypatch.setattr(
            mbs_silver_publication,
            "qualify_mbs_silver",
            lambda *_args, **_kwargs: SimpleNamespace(
                blockers=("public_v4_identity_unverified",),
                source_sha256="0" * 64,
            ),
        )
    else:
        monkeypatch.setattr(
            mbs_silver_publication,
            "iter_mbs_silver_batches",
            lambda *_args, **_kwargs: iter(()),
        )

    with pytest.raises(ValueError, match=message):
        build_mbs_silver_v4_package(
            call_payload,
            receipt,
            exact_commit=commit,
            source_era_verification=verification,
            output_dir=tmp_path / mutation,
        )


def test_package_path_and_manifest_validation_rejects_malformed_objects(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_silver_publication._authorization_identity",
        lambda *_: ("a" * 64, "b" * 64),
    )
    with pytest.raises(ValueError, match="unsafe MBS Silver v4 package path"):
        mbs_silver_publication._write_object(
            tmp_path, "../escape.bin", b"x", "unsafe"
        )

    payload = _xml("<ScheduleFee>42.00</ScheduleFee>")
    package = build_mbs_silver_v4_package(
        payload,
        _authorized_receipt(payload, "e" * 40),
        exact_commit="e" * 40,
        source_era_verification=_verification(payload),
        output_dir=tmp_path / "package",
    )
    with pytest.raises(ValueError, match="destination differs"):
        validate_mbs_silver_v4_package(
            replace(package, destination_dataset="unexpected/dataset")
        )
    with pytest.raises(
        ValueError, match="duplicate MBS Silver v4 package object"
    ):
        validate_mbs_silver_v4_package(
            replace(package, objects=(*package.objects, package.objects[0]))
        )
    valid_manifest = package.manifest_path.read_bytes()
    package.manifest_path.write_bytes(b"{")
    with pytest.raises(ValueError, match="manifest is unreadable"):
        validate_mbs_silver_v4_package(package)
    package.manifest_path.write_bytes(valid_manifest)

    manifest = json.loads(valid_manifest)
    manifest["objects"][0]["role"] = "altered-role"
    changed_manifest = (
        json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode()
        + b"\n"
    )
    package.manifest_path.write_bytes(changed_manifest)
    changed_package = replace(
        package, manifest_sha256=sha256(changed_manifest).hexdigest()
    )
    with pytest.raises(ValueError, match="manifest object inventory differs"):
        validate_mbs_silver_v4_package(changed_package)


@pytest.mark.parametrize(
    "failure",
    [None, "source", "private", "collision", "revision", "inventory", "digest"],
)
def test_hosted_publisher_verifies_or_fails_closed(
    tmp_path, monkeypatch, failure: str | None
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "d" * 40)
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("HF_TOKEN", "test-token")

    source = b"exact pinned public source bytes"
    source_path = tmp_path / "source.xml"
    source_path.write_bytes(source)
    stage_root = tmp_path / "stage"
    staged_files = {
        f"{DESTINATION_PREFIX}/services.parquet": stage_root
        / "services.parquet",
        f"{DESTINATION_PREFIX}/manifest.json": stage_root / "manifest.json",
    }
    for name, path in staged_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    package = SimpleNamespace(
        files=staged_files,
        manifest_sha256="e" * 64,
    )
    source_sha256 = sha256(source).hexdigest()
    compared_at = "2026-09-27T19:48:12Z"
    report = {
        "official_release_check": {
            "matched_pinned_archive": failure != "source",
            "source_sha256": source_sha256,
            "source_byte_count": len(source),
            "release_id": "MBS-XML-20250701 Version 3",
            "released_at": "2025-06-16",
            "effective_at": "2025-07-01",
        },
        "qualification": {
            "source_era_verification": {"compared_at": compared_at}
        },
        "retrieved_at": "2026-09-27T19:48:12+00:00",
    }
    monkeypatch.setattr(hosted_publisher, "qualify", lambda **_: report)
    monkeypatch.setattr(
        hosted_publisher,
        "build_mbs_silver_v4_package",
        lambda *_args, **_kwargs: package,
    )

    class FakeHub:
        appended_paths: ClassVar[set[str]] = set()

        def __init__(self, token: Any = None):
            self.token = token

        def dataset_info(self, _dataset, revision=None, **_kwargs):
            siblings = {"raw/mbs/2025-07/source.xml"}
            if failure == "collision":
                siblings.add(next(iter(staged_files)))
            if revision is not None:
                siblings |= self.appended_paths
                if failure == "inventory":
                    siblings.add("unexpected/object.bin")
            return SimpleNamespace(
                sha=(
                    "different-revision"
                    if revision is not None and failure == "revision"
                    else revision or "parent-revision"
                ),
                private=failure == "private" and revision is None,
                gated=False,
                siblings=[SimpleNamespace(rfilename=name) for name in siblings],
            )

        def create_commit(self, *, parent_commit, operations, **_kwargs):
            assert parent_commit == "parent-revision"
            type(self).appended_paths = {
                item.path_in_repo for item in operations
            }
            return SimpleNamespace(oid="new-revision")

    def fake_download(*, filename, **_kwargs):
        if filename.startswith("raw/"):
            return str(source_path)
        if failure == "digest":
            corrupted = tmp_path / "corrupted.parquet"
            corrupted.write_bytes(b"drifted bytes")
            return str(corrupted)
        return str(staged_files[filename])

    hub_module = ModuleType("huggingface_hub")

    class FakeCommitOperationAdd:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    hub_module.CommitOperationAdd = FakeCommitOperationAdd
    hub_module.HfApi = FakeHub
    hub_module.hf_hub_download = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub_module)
    comments: list[list[str]] = []

    def fake_command(args, **_kwargs):
        comments.append(args)
        if "--body-file" in args:
            receipt = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
            assert receipt["anonymous_digest_verification"] == "passed"
            assert receipt["candidate_only"] is True
            assert len(receipt["verified_objects"]) == 2
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(hosted_publisher.subprocess, "run", fake_command)

    if failure is not None:
        with pytest.raises(RuntimeError):
            hosted_publisher.main()
        return

    assert hosted_publisher.main() == 0
    assert len(comments) == 2
    assert "intent" in comments[0][-1]
    assert "--body-file" in comments[1]
    assert not (tmp_path / "build/mbs-silver-publication").exists()


def test_hosted_publisher_fails_closed_outside_actions(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="protected main Actions"):
        hosted_publisher.main()


def test_publication_workflow_runs_publisher_as_repository_module() -> None:
    workflow = Path(
        ".github/workflows/australian-mbs-silver-publication.yml"
    ).read_text(encoding="utf-8")
    assert "python -m scripts.publish_australian_mbs_silver_v4" in workflow
    assert "python scripts/publish_australian_mbs_silver_v4.py" not in workflow
