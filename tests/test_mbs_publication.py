"""Publication protocol tests use in-memory fake Hub clients, never an upload."""

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
from pydantic import AnyUrl

from global_medicines_atlas.mbs_publication import (
    PublicArchiveState,
    publish_mbs_stage,
)
from global_medicines_atlas.mbs_release import (
    MbsArchiveObject,
    MbsReleaseContract,
    MbsReleaseStage,
    stage_mbs_release,
)
from global_medicines_atlas.receipts import (
    DataSensitivity,
    EvidenceClass,
    PersonalDataState,
    PublicationDisposition,
    RightsState,
    SensitivityClassification,
    SourceReceipt,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision


class FakeHub:
    def __init__(self) -> None:
        self.files = {"legacy.xml": b"preserved legacy bytes"}
        self.revision = "a" * 40
        self.private = False
        self.corrupt = False
        self.calls = 0

    def state(self, revision: str | None = None) -> PublicArchiveState:
        return PublicArchiveState(
            revision or self.revision,
            frozenset(self.files),
            self.private,
            gated=False,
        )

    def read(self, revision: str, path: str) -> bytes:
        del revision
        return b"corrupt" if self.corrupt else self.files[path]

    def append(self, files: Mapping[str, Path], *, parent_revision: str) -> str:
        assert parent_revision == self.revision
        self.calls += 1
        self.files.update({
            name: path.read_bytes() for name, path in files.items()
        })
        self.revision = "b" * 40
        return self.revision


@pytest.fixture
def live_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> MbsReleaseStage:
    """Simulate live-class receipts over fixture bytes to exercise hosted policy."""
    contract = MbsReleaseContract.model_validate_json(
        Path(
            "quality/qualifications/mbs-current-release-contract.json"
        ).read_bytes()
    ).model_copy(update={"publication_authorized": True})
    stage = stage_mbs_release(
        contract,
        tmp_path,
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: datetime(2026, 8, 30, tzinfo=UTC),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=b"<MBS_XML><Data><ItemNum>1</ItemNum></Data></MBS_XML>",
                headers={"content-type": "text/xml"},
            )
        ),
    )
    objects: list[MbsArchiveObject] = []
    for item in stage.manifest.objects:
        updated = item
        if item.role == "source_receipt":
            path = stage.path / item.path
            receipt = SourceReceipt.model_validate_json(
                path.read_bytes()
            ).model_copy(
                update={
                    "evidence_class": EvidenceClass.LIVE,
                    "rights_state": RightsState.PERMITTED,
                    "rights_reference": AnyUrl(
                        contract.authorization_reference
                    ),
                    "sensitivity": SensitivityClassification(
                        data_sensitivity=DataSensitivity.NON_SENSITIVE,
                        personal_data=PersonalDataState.NONE,
                        publication=PublicationDisposition.PERMITTED,
                        reason_codes=("synthetic_policy_fixture",),
                    ),
                }
            )
            path.write_bytes(receipt.canonical_json())
            updated = item.model_copy(
                update={
                    "sha256": sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                }
            )
        objects.append(updated)
    manifest = stage.manifest.model_copy(
        update={"evidence_class": EvidenceClass.LIVE, "objects": tuple(objects)}
    )
    (stage.path / stage.manifest_path).write_text(
        manifest.model_dump_json(indent=2) + "\n"
    )
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
    }.items():
        monkeypatch.setenv(name, value)
    return MbsReleaseStage(stage.path, stage.manifest_path, manifest)


def test_append_preserves_legacy_and_verifies_all_objects(
    live_stage: MbsReleaseStage,
) -> None:
    hub = FakeHub()
    receipt = publish_mbs_stage(
        live_stage, live_stage.manifest.contract, public=hub, writer=hub
    )
    assert hub.files["legacy.xml"] == b"preserved legacy bytes"
    assert receipt["anonymous_digest_verification"] == "passed"
    assert receipt["data_acquired"] is True
    assert receipt["temporary_source_bytes_removed"] is False
    assert live_stage.path.exists()


@pytest.mark.parametrize(
    "mode", ["local", "private", "extra", "changed", "anonymous"]
)
def test_publication_fails_closed(
    live_stage: MbsReleaseStage, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    hub = FakeHub()
    if mode == "local":
        monkeypatch.delenv("GITHUB_ACTIONS")
    elif mode == "private":
        hub.private = True
    elif mode == "extra":
        (live_stage.path / "unmanifested").write_bytes(b"unexpected")
    elif mode == "changed":
        (live_stage.path / live_stage.manifest.objects[0].path).write_bytes(
            b"changed"
        )
    else:
        hub.corrupt = True
    with pytest.raises(
        ValueError, match=r"GitHub Actions|public|unmanifested|digest"
    ):
        publish_mbs_stage(
            live_stage, live_stage.manifest.contract, public=hub, writer=hub
        )
    assert live_stage.path.exists()
    assert hub.calls == (1 if mode == "anonymous" else 0)


@pytest.mark.parametrize(
    "mode", ["synthetic", "duplicate", "traversal", "symlink", "collision"]
)
def test_manifest_and_append_boundaries(
    live_stage: MbsReleaseStage, mode: str
) -> None:
    hub = FakeHub()
    manifest = live_stage.manifest
    first = manifest.objects[0]
    if mode == "synthetic":
        manifest = manifest.model_copy(
            update={"evidence_class": EvidenceClass.SYNTHETIC}
        )
    elif mode == "duplicate":
        manifest = manifest.model_copy(
            update={"objects": (*manifest.objects, first)}
        )
    elif mode == "traversal":
        manifest = manifest.model_copy(
            update={
                "objects": (
                    first.model_copy(update={"path": "../escape"}),
                    *manifest.objects[1:],
                )
            }
        )
    elif mode == "symlink":
        path = live_stage.path / first.path
        saved = path.with_suffix(".kept")
        path.rename(saved)
        path.symlink_to(saved)
    else:
        hub.files[first.path] = b"different earlier object"
    stage = MbsReleaseStage(live_stage.path, live_stage.manifest_path, manifest)
    with pytest.raises(
        ValueError, match=r"live manifest|duplicate|unsafe|overwrite"
    ):
        publish_mbs_stage(stage, manifest.contract, public=hub, writer=hub)
    assert hub.calls == 0


def test_existing_identical_object_is_reused(
    live_stage: MbsReleaseStage,
) -> None:
    hub = FakeHub()
    first = live_stage.manifest.objects[0]
    hub.files[first.path] = (live_stage.path / first.path).read_bytes()
    receipt = publish_mbs_stage(
        live_stage, live_stage.manifest.contract, public=hub, writer=hub
    )
    assert receipt["legacy_paths_preserved"] == 2


def test_quarantined_raw_does_not_inherit_file_authorization(
    live_stage: MbsReleaseStage,
) -> None:
    manifest = live_stage.manifest.model_copy(
        update={
            "admission_state": "quarantined",
            "record_count": 0,
            "p7_record_count": 0,
        }
    )
    (live_stage.path / live_stage.manifest_path).write_text(
        manifest.model_dump_json(indent=2) + "\n"
    )
    stage = MbsReleaseStage(live_stage.path, live_stage.manifest_path, manifest)
    hub = FakeHub()
    with pytest.raises(ValueError, match="quarantined"):
        publish_mbs_stage(stage, manifest.contract, public=hub, writer=hub)
    assert hub.calls == 0


@pytest.mark.parametrize("classification", [None, SensitivityClassification()])
def test_missing_sensitivity_blocks_upload(
    live_stage: MbsReleaseStage,
    classification: SensitivityClassification | None,
) -> None:
    objects: list[MbsArchiveObject] = []
    for item in live_stage.manifest.objects:
        updated = item
        if item.role == "source_receipt":
            path = live_stage.path / item.path
            source = SourceReceipt.model_validate_json(
                path.read_bytes()
            ).model_copy(update={"sensitivity": classification})
            path.write_bytes(source.canonical_json())
            updated = item.model_copy(
                update={
                    "sha256": sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                }
            )
        objects.append(updated)
    manifest = live_stage.manifest.model_copy(
        update={"objects": tuple(objects)}
    )
    (live_stage.path / live_stage.manifest_path).write_text(
        manifest.model_dump_json(indent=2) + "\n"
    )
    stage = MbsReleaseStage(live_stage.path, live_stage.manifest_path, manifest)
    hub = FakeHub()
    with pytest.raises(ValueError, match="sensitivity"):
        publish_mbs_stage(stage, manifest.contract, public=hub, writer=hub)
    assert hub.calls == 0
