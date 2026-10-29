"""Exact-main bounded groups cover the frozen CSV cohort without exporting values."""

import hashlib
import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed offline CLI probe
import sys
from dataclasses import replace
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import httpx
import pytest
import yaml
from scripts import qualify_mbs_historical_csv_packages as module

from global_medicines_atlas.mbs_archive_inventory import BoundArchive
from global_medicines_atlas.mbs_historical_csv_package import FrozenMbsMember


def test_local_execution_stops_before_transport(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify(
            "a" * 40,
            0,
            transport=httpx.MockTransport(
                lambda _: pytest.fail("transport not allowed")
            ),
        )


def test_all_groups_cover_all_frozen_csv_members_once():
    groups = [
        module.select_group(module.ROOT, index)
        for index in range(module.GROUP_COUNT)
    ]
    members = [member for group in groups for member in group]
    assert len(members) == 90
    assert len({(m.source.source_path, m.path_sha256) for m in members}) == 90
    assert all(len(group) <= 5 for group in groups)


SHA = "a" * 40


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
    }.items():
        monkeypatch.setenv(key, value)
    archive_path = tmp_path / "source.zip"
    raw = []
    with ZipFile(archive_path, "w", compression=ZIP_STORED) as archive:
        archive.mkdir("SYNTHETIC-DIRECTORY/")
        for index in range(90):
            name = f"SYNTHETIC-MEMBER-{index}.csv"
            payload = f"ID,Value\n00{index},SYNTHETIC-CONTENT\n".encode()
            archive.writestr(name, payload)
            raw.append((name, payload))
    archive_bytes = archive_path.read_bytes()
    source = BoundArchive(
        module.DATASET,
        module.REVISION,
        "raw/synthetic.zip",
        hashlib.sha256(archive_bytes).hexdigest(),
        len(archive_bytes),
        "synthetic",
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "unprofiled",
        None,
        None,
        None,
    )
    members = [
        FrozenMbsMember(
            source,
            index,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            hashlib.sha256(name.encode()).hexdigest(),
            ".csv",
            "5" * 64,
        )
        for index, (name, payload) in enumerate(raw)
    ]
    monkeypatch.setattr(module, "load_frozen_members", lambda _: tuple(members))
    info = f"https://huggingface.co/api/datasets/{module.DATASET}/revision/{module.REVISION}"
    url = f"https://huggingface.co/datasets/{module.DATASET}/resolve/{module.REVISION}/{source.source_path}?download=true"
    responses = {
        info: json.dumps({
            "id": module.DATASET,
            "sha": module.REVISION,
            "private": False,
            "gated": False,
        }).encode(),
        url: archive_bytes,
    }
    calls = []

    def handle(request):
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        calls.append(str(request.url))
        return httpx.Response(200, content=responses[str(request.url)])

    return members, responses, calls, httpx.MockTransport(handle), info, url


def test_hosted_group_checks_five_exact_members_and_keeps_values_private(
    synthetic, monkeypatch
):
    paths = []
    original = module.qualify_csv_member_package

    def observe(path, *args):
        paths.append(path)
        assert path.is_file()
        return original(path, *args)

    monkeypatch.setattr(module, "qualify_csv_member_package", observe)
    progress = []
    report = module.qualify(
        SHA,
        0,
        transport=synthetic[3],
        progress=lambda phase, count: progress.append((phase, count)),
    )
    assert report["status"] == "passed"
    assert len(report["members"]) == 5
    assert len(synthetic[2]) == 3
    assert all(not path.exists() for path in paths)
    assert all(
        item["two_builds_equal"] and item["complete_native_restore_verified"]
        for item in report["members"]
    )
    assert progress[0] == ("source-stage", 0)
    assert progress[-1] == ("public-readback", 5)
    assert "SYNTHETIC-" not in json.dumps(report)
    assert (
        report["new_admissions"]
        == report["new_sources"]
        == report["publications"]
        == 0
    )


@pytest.mark.parametrize("group", [-1, 18, True])
def test_invalid_group_rejects_before_transport(synthetic, group):
    with pytest.raises(ValueError, match="group"):
        module.qualify(SHA, group, transport=synthetic[3])
    assert not synthetic[2]


@pytest.mark.parametrize("change", ["missing", "duplicate", "parent"])
def test_frozen_cohort_mismatch_rejects_before_transport(synthetic, change):
    members = synthetic[0]
    if change == "missing":
        members.pop()
    elif change == "duplicate":
        members[1] = members[0]
    else:
        members[1] = replace(
            members[1],
            source=replace(members[1].source, source_sha256="0" * 64),
        )
    with pytest.raises(ValueError, match=r"denominator|binding"):
        module.qualify(SHA, 0, transport=synthetic[3])
    assert not synthetic[2]


def test_private_parent_rejects_before_download(synthetic):
    synthetic[1][synthetic[4]] = json.dumps({"private": True}).encode()
    with pytest.raises(ValueError, match="public revision"):
        module.qualify(SHA, 0, transport=synthetic[3])
    assert synthetic[2] == [synthetic[4]]


def test_changed_parent_stream_never_reaches_member_parse(synthetic):
    synthetic[1][synthetic[5]] += b"changed"
    with pytest.raises(ValueError, match="streamed byte bound"):
        module.qualify(SHA, 0, transport=synthetic[3])


@pytest.mark.parametrize("change", ["size", "digest", "path"])
def test_changed_member_identity_never_qualifies(synthetic, change):
    members = synthetic[0]
    updates = {
        "size": {"byte_count": members[0].byte_count + 1},
        "digest": {"sha256": "0" * 64},
        "path": {"path_sha256": "0" * 64},
    }
    members[0] = replace(members[0], **updates[change])
    with pytest.raises(
        ValueError, match=r"member size|member-identity|identity set"
    ):
        module.qualify(SHA, 0, transport=synthetic[3])


def test_cli_preserves_existing_receipt(tmp_path):
    output = tmp_path / "receipt.json"
    output.write_text("human evidence")
    with pytest.raises(SystemExit):
        module.main([
            "--exact-commit",
            SHA,
            "--group",
            "0",
            "--output",
            str(output),
        ])
    assert output.read_text() == "human evidence"


@pytest.mark.usefixtures("synthetic")
def test_cli_withholds_exception_and_preserves_safe_progress(
    tmp_path, monkeypatch
):
    def fail(*_, progress):
        progress("member-native-check", 2)
        raise ValueError("SYNTHETIC SECRET CONTENT")

    monkeypatch.setattr(module, "qualify", fail)
    output = tmp_path / "receipt.json"
    assert (
        module.main([
            "--exact-commit",
            SHA,
            "--group",
            "0",
            "--output",
            str(output),
        ])
        == 1
    )
    report = json.loads(output.read_bytes())
    assert report["status"] == "failed"
    assert report["completed_members"] == 2
    assert "SYNTHETIC SECRET" not in output.read_text()


@pytest.mark.usefixtures("synthetic")
def test_cli_retains_incomplete_progress_on_interruption(tmp_path, monkeypatch):
    def interrupt(*_, progress):
        progress("member-native-check", 3)
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "qualify", interrupt)
    output = tmp_path / "receipt.json"
    with pytest.raises(KeyboardInterrupt):
        module.main([
            "--exact-commit",
            SHA,
            "--group",
            "0",
            "--output",
            str(output),
        ])
    report = json.loads(output.read_bytes())
    assert report["status"] == "incomplete"
    assert report["completed_members"] == 3
    assert not list(tmp_path.glob(".mbs-csv-receipt-*"))


def test_workflow_qualifies_all_groups_with_original_read_only_bounds():
    document = yaml.load(
        (
            module.ROOT
            / ".github/workflows/mbs-q1-source-meaning-diagnostics.yml"
        ).read_text(),
        Loader=yaml.BaseLoader,
    )
    job = document["jobs"]["historical-csv-packages"]
    assert job["strategy"]["matrix"]["group"] == [str(i) for i in range(18)]
    assert job["strategy"]["max-parallel"] == "2"
    assert job["strategy"]["fail-fast"] == "false"
    assert job["permissions"] == {"contents": "read"}
    assert job["timeout-minutes"] == "30"
    step = next(step for step in job["steps"] if "run" in step)
    assert "scripts/qualify_mbs_historical_csv_packages.py" in step["run"]
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in step["run"]
    assert '--group "$CSV_GROUP"' in step["run"]
    assert job["steps"][-1]["if"] == "always()"
    assert job["steps"][-1]["with"]["path"] == "historical-csv-packages.json"


def test_final_public_revision_readback_is_mandatory(synthetic):
    original = synthetic[3]

    def changed(request):
        if (
            str(request.url) == synthetic[4]
            and synthetic[2].count(synthetic[4]) == 1
        ):
            synthetic[1][synthetic[4]] = json.dumps({"private": True}).encode()
        return original.handle_request(request)

    with pytest.raises(ValueError, match="public revision"):
        module.qualify(SHA, 0, transport=httpx.MockTransport(changed))


def test_cli_success_retains_only_completed_metadata(
    tmp_path, monkeypatch, synthetic
):
    original = module.qualify

    def mocked(exact, group, *, progress):
        return original(exact, group, transport=synthetic[3], progress=progress)

    monkeypatch.setattr(module, "qualify", mocked)
    output = tmp_path / "receipt.json"
    assert (
        module.main([
            "--exact-commit",
            SHA,
            "--group",
            "0",
            "--output",
            str(output),
        ])
        == 0
    )
    report = json.loads(output.read_bytes())
    assert report["status"] == "passed"
    assert len(report["members"]) == 5
    assert "SYNTHETIC-" not in output.read_text()


@pytest.mark.usefixtures("synthetic")
@pytest.mark.parametrize(
    ("phase", "count"),
    [
        ("SYNTHETIC-SECRET", 0),
        ("member-complete", 6),
        ("member-complete", True),
    ],
)
def test_invalid_progress_cannot_enter_a_receipt(
    tmp_path, monkeypatch, phase, count
):
    def invalid(*_, progress):
        progress(phase, count)
        raise AssertionError("unreachable")

    monkeypatch.setattr(module, "qualify", invalid)
    output = tmp_path / "receipt.json"
    assert (
        module.main([
            "--exact-commit",
            SHA,
            "--group",
            "0",
            "--output",
            str(output),
        ])
        == 1
    )
    report = json.loads(output.read_bytes())
    assert report["phase"] == "not-started"
    assert report["completed_members"] == 0
    assert "SYNTHETIC-SECRET" not in output.read_text()


def test_complete_group_receipt_bound_rejects_without_truncation(monkeypatch):
    monkeypatch.setattr(module, "MAX_REPORT_BYTES", 1)
    with pytest.raises(ValueError, match="receipt byte bound"):
        module._encoded({"status": "passed"})


def test_duplicate_native_member_identity_is_rejected(synthetic):
    info = ZipInfo("SYNTHETIC-MEMBER-0.csv")

    class DuplicateArchive:
        def infolist(self):
            return [info, info]

    with pytest.raises(ValueError, match="identity is duplicated"):
        module._lookup(DuplicateArchive(), tuple(synthetic[0]))


def test_standalone_cli_stops_locally_before_real_source_acquisition(tmp_path):
    output = tmp_path / "receipt.json"
    environment = dict(os.environ, GITHUB_ACTIONS="false")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argument vector; no shell
        [
            sys.executable,
            str(module.ROOT / "scripts/qualify_mbs_historical_csv_packages.py"),
            "--exact-commit",
            SHA,
            "--group",
            "0",
            "--output",
            str(output),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    report = json.loads(output.read_bytes())
    assert report["status"] == "failed"
    assert report["completed_members"] == 0
    assert report["failure_category"] == "validation"
