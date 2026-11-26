"""Fail-closed boundaries for bulk archive publication."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import types
import zipfile
from collections import Counter
from pathlib import Path
from threading import Barrier
from typing import Any, cast
from unittest.mock import Mock

import httpx
import pytest
from scripts import check_archive_status as archives
from scripts import publish_bulk_archive as publisher
from scripts import publish_fresh_openfda as fresh
from scripts import publish_october_openfda_hosted as october

from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main as real_require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    ArtifactVerification,
    PublicationDestination,
    PublicationPlan,
    PublicationTarget,
)

COMMIT = "a" * 40
FRESH_BATCH = "openfda-20261120"
SYNTHETIC_HF_TOKEN = "synthetic-token"  # ruff: ignore[hardcoded-password-string] -- synthetic fixture, not a credential.


def test_aems_stages_only_the_approved_ascii_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = (
        Path(__file__).resolve().parents[1]
        / "quality/source-batches/aems-2026q3/manifest.json"
    )
    manifest = json.loads(contract.read_bytes())
    file = io.BytesIO()
    with zipfile.ZipFile(file, "w") as package:
        package.writestr("source.txt", "synthetic")
    body = file.getvalue()
    manifest["expected_payload_bytes"] = len(body)

    def serve(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == manifest["source_url"]
        return httpx.Response(200, stream=httpx.ByteStream(body))

    monkeypatch.setattr(
        publisher,
        "BoundIPAddressTransport",
        Mock(return_value=httpx.MockTransport(serve)),
    )
    monkeypatch.delenv("RUNNER_ENVIRONMENT", raising=False)
    with pytest.raises(ValueError, match="GitHub-hosted"):
        publisher.stage_aems(tmp_path / "local", manifest)
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    root = tmp_path / "approved"
    publisher.stage_aems(root, manifest)
    [filename] = publisher.assert_archive_matches_contract(root, manifest)
    assert (root / filename).read_bytes() == body
    receipt = json.loads((root / f"{filename}.receipt.json").read_text())
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["size"] == len(body)
    assert receipt["source_url"] == manifest["source_url"]
    with pytest.raises(ValueError, match="exact official ASCII ZIP"):
        publisher.stage_aems(
            tmp_path / "wrong-quarter",
            manifest
            | {"source_url": manifest["source_url"].replace("q3", "q2")},
        )


def test_october_reviewed_receipt_requires_the_original_bytes(
    tmp_path: Path,
) -> None:
    plan = PublicationPlan.model_validate_json(
        (october.ONLINE_SOURCES.parent / "publication-plan.json").read_bytes()
    )
    receipt = next(
        artifact
        for artifact in plan.artifacts
        if artifact.relative_path.endswith(".receipt.json")
    )
    url = "https://archive.example.org/original-receipt.json"
    configured = tmp_path / "sources.json"
    configured.write_text(
        json.dumps({receipt.relative_path: url + "?token=example"})
    )
    with pytest.raises(ValueError, match="direct HTTPS"):
        october.reviewed_sources(configured, plan)
    configured.write_text(json.dumps({"unrecorded.json": url}))
    with pytest.raises(ValueError, match="outside the frozen plan"):
        october.reviewed_sources(configured, plan)
    configured.write_text(json.dumps({receipt.relative_path: url}))
    assert october.reviewed_sources(configured, plan) == {
        receipt.relative_path: url
    }

    exact = b'{"recorded":true}'
    artifact = ArtifactBinding(
        relative_path=receipt.relative_path,
        sha256=hashlib.sha256(exact).hexdigest(),
        size=len(exact),
    )

    def serve(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == url
        return httpx.Response(200, stream=httpx.ByteStream(exact))

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        for checked, matched in october.check_online_groups(
            client, [artifact], {artifact.relative_path: url}
        ):
            assert checked[artifact.relative_path]["status"] == "match"
            assert matched[0][1].read_bytes() == exact
        for checked, matched in october.check_online_groups(
            client,
            [artifact.model_copy(update={"sha256": "0" * 64})],
            {artifact.relative_path: url},
        ):
            assert (
                checked[artifact.relative_path]["status"] == "digest_mismatch"
            )
            assert matched == []


def test_october_hosted_resume_uses_verified_batches() -> None:
    files = {
        "first.zip": b"first",
        "second.zip": b"second",
        "third.zip": b"third",
    }
    artifacts = tuple(
        ArtifactBinding(
            relative_path=path,
            size=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
        )
        for path, body in files.items()
    )
    plan = PublicationPlan(
        release_version=october.BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=october.REPOSITORY,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{october.REPOSITORY}",
        ),
        artifacts=artifacts,
    )
    api = Mock()
    api.repo_info.return_value = types.SimpleNamespace(
        sha=COMMIT, private=False
    )
    first = artifacts[0]
    remote = types.SimpleNamespace(
        path=first.relative_path,
        size=first.size,
        lfs=types.SimpleNamespace(sha256=first.sha256, size=first.size),
    )
    api.list_repo_tree.return_value = [remote]
    api.list_repo_files.return_value = [".gitattributes", *files]
    committed = "b" * 40
    scratch_files = []

    def commit(_repo, *, parent_commit, operations, **_kw):
        assert parent_commit == COMMIT
        assert [operation.path_in_repo for operation in operations] == [
            "second.zip",
            "third.zip",
        ]
        for operation in operations:
            scratch_files.append(operation.path_or_fileobj)
            assert (
                operation.path_or_fileobj.read_bytes()
                == files[operation.path_in_repo]
            )
        return types.SimpleNamespace(oid=committed)

    api.create_commit.side_effect = commit
    hub = types.SimpleNamespace(
        RepoFile=types.SimpleNamespace, CommitOperationAdd=types.SimpleNamespace
    )
    requests = []

    def serve(request):
        path = request.url.path.removeprefix("/")
        requests.append(path)
        return httpx.Response(200, stream=httpx.ByteStream(files[path]))

    with httpx.Client(
        base_url=october.source_origin("http://100.64.1.2:18043/"),
        transport=httpx.MockTransport(serve),
    ) as client:
        assert october.publish_batches(
            api,
            hub,
            client,
            plan,
            prepared={"third.zip": files["third.zip"]},
        ) == october.BatchResult(
            revision=committed, complete=True, newly_committed=2
        )
        assert requests == ["second.zip"]
        api.create_commit.reset_mock()
        with pytest.raises(ValueError, match="October rebuilt file differs"):
            october.publish_batches(
                api, hub, client, plan, prepared={"third.zip": b"corrupt"}
            )
        api.create_commit.assert_not_called()
    assert scratch_files
    assert all(not path.exists() for path in scratch_files)
    remote.lfs.sha256 = "0" * 64
    with pytest.raises(ValueError, match="destination checksum differs"):
        october.remaining_artifacts(api, hub, plan)


def test_october_checkpoints_only_after_a_committed_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = {"first.zip": b"first", "second.zip": b"second"}
    artifacts = tuple(
        ArtifactBinding(
            relative_path=path,
            size=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
        )
        for path, body in files.items()
    )
    plan = PublicationPlan(
        release_version=october.BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=october.REPOSITORY,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{october.REPOSITORY}",
        ),
        artifacts=artifacts,
    )
    api, hub = Mock(), Mock()
    monkeypatch.setattr(october, "COMMIT_FILES", 1)
    monkeypatch.setattr(
        october, "remaining_artifacts", Mock(return_value=(COMMIT, artifacts))
    )
    commit = Mock(return_value="b" * 40)
    monkeypatch.setattr(october, "commit_artifacts", commit)
    monkeypatch.setattr(
        october,
        "time",
        types.SimpleNamespace(monotonic=Mock(side_effect=[0.0, 2.0])),
    )

    with httpx.Client() as client:
        result = october.publish_batches(
            api, hub, client, plan, prepared=files, deadline=1.0
        )
        assert result == october.BatchResult(
            revision="b" * 40, complete=False, newly_committed=1
        )
        assert commit.call_count == 1
        api.list_repo_files.assert_not_called()

        commit.reset_mock()
        monkeypatch.setattr(
            october,
            "time",
            types.SimpleNamespace(monotonic=Mock(return_value=2.0)),
        )
        with pytest.raises(TimeoutError, match="no checkpoint progress"):
            october.publish_batches(
                api, hub, client, plan, prepared=files, deadline=1.0
            )
        commit.assert_not_called()


def test_october_abandons_an_unfinished_batch_at_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = {"first.zip": b"first", "second.zip": b"second"}
    artifacts = tuple(
        ArtifactBinding(
            relative_path=path,
            size=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
        )
        for path, body in files.items()
    )
    plan = PublicationPlan(
        release_version=october.BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=october.REPOSITORY,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{october.REPOSITORY}",
        ),
        artifacts=artifacts,
    )
    api, hub = Mock(), Mock()
    monkeypatch.setattr(october, "COMMIT_FILES", 1)
    monkeypatch.setattr(
        october, "remaining_artifacts", Mock(return_value=(COMMIT, artifacts))
    )
    monkeypatch.setattr(
        october, "time", types.SimpleNamespace(monotonic=Mock(return_value=0.0))
    )
    commit = Mock(return_value="b" * 40)
    monkeypatch.setattr(october, "commit_artifacts", commit)
    download = Mock(side_effect=october.CheckpointDeadlineError)
    monkeypatch.setattr(october, "download_artifact", download)
    with httpx.Client() as client:
        result = october.publish_batches(
            api,
            hub,
            client,
            plan,
            prepared={"first.zip": files["first.zip"]},
            deadline=1.0,
        )
    assert result == october.BatchResult(
        revision="b" * 40, complete=False, newly_committed=1
    )
    assert commit.call_count == 1
    assert download.call_count == 1
    api.list_repo_files.assert_not_called()


def test_october_source_range_honours_the_publication_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b"test"
    artifact = ArtifactBinding(
        relative_path="source.zip",
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    monkeypatch.setattr(
        october,
        "time",
        types.SimpleNamespace(monotonic=Mock(side_effect=[0.0, 2.0])),
    )
    output = io.BytesIO()
    with (
        httpx.Client(
            base_url="http://100.64.1.2:18043/",
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200, stream=httpx.ByteStream(body)
                )
            ),
        ) as client,
        pytest.raises(october.CheckpointDeadlineError),
    ):
        october.download_range_once(
            client, artifact, output, 0, len(body), publication_deadline=1.0
        )
    assert output.getvalue() == b""


def test_october_download_does_not_start_ranges_after_the_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"test"
    artifact = ArtifactBinding(
        relative_path="source.zip",
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    monkeypatch.setattr(
        october, "time", types.SimpleNamespace(monotonic=Mock(return_value=2.0))
    )
    transport = Mock(side_effect=AssertionError("No source request is allowed"))
    with (
        httpx.Client(
            base_url="http://100.64.1.2:18043/",
            transport=httpx.MockTransport(transport),
        ) as client,
        pytest.raises(october.CheckpointDeadlineError),
    ):
        october.download_artifact(
            client, artifact, tmp_path / "source.zip", publication_deadline=1.0
        )
    transport.assert_not_called()


@pytest.mark.parametrize("transient", [False, True])
def test_october_deadline_does_not_hide_a_non_transient_source_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, transient: bool
) -> None:
    body = b"test"
    artifact = ArtifactBinding(
        relative_path="source.zip",
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    request = httpx.Request("GET", "http://100.64.1.2:18043/source.zip")
    error = (
        httpx.ReadTimeout("timeout", request=request)
        if transient
        else httpx.HTTPStatusError(
            "denied",
            request=request,
            response=httpx.Response(404, request=request),
        )
    )
    monkeypatch.setattr(
        october,
        "time",
        types.SimpleNamespace(monotonic=Mock(side_effect=[0.0, 2.0])),
    )
    monkeypatch.setattr(october, "download_range_once", Mock(side_effect=error))
    expected = october.CheckpointDeadlineError if transient else ValueError
    with httpx.Client() as client, pytest.raises(expected):
        october.download_artifact(
            client, artifact, tmp_path / "source.zip", publication_deadline=1.0
        )


@pytest.mark.parametrize("complete", [False, True])
def test_october_distinguishes_a_checkpoint_from_a_completed_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, complete: bool
) -> None:
    plan_file = october.ONLINE_SOURCES.parent / "publication-plan.json"
    (tmp_path / "plan.json").write_bytes(plan_file.read_bytes())
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GMA_OCTOBER_SOURCE_URL", "http://100.64.1.2:18043")
    monkeypatch.setenv("HF_TOKEN", SYNTHETIC_HF_TOKEN)
    monkeypatch.setattr(
        october,
        "authorization_from_environment",
        Mock(return_value=types.SimpleNamespace(permits_external_write=True)),
    )
    monkeypatch.setattr(
        october,
        "import_module",
        Mock(return_value=types.SimpleNamespace(HfApi=Mock())),
    )
    monkeypatch.setattr(
        october,
        "publish_batches",
        Mock(
            return_value=october.BatchResult(
                revision="b" * 40, complete=complete, newly_committed=4
            )
        ),
    )

    october.publish(tmp_path, COMMIT)

    if complete:
        receipt = json.loads((tmp_path / "uploaded.json").read_text())
        assert receipt["state"] == "uploaded"
        assert receipt["remote_revision"] == "b" * 40
        assert not (tmp_path / "checkpoint.json").exists()
    else:
        checkpoint = json.loads((tmp_path / "checkpoint.json").read_text())
        assert checkpoint == {
            "plan_sha256": october.PLAN_SHA256,
            "remote_revision": "b" * 40,
            "newly_committed": 4,
            "run_id": "123",
        }
        assert not (tmp_path / "uploaded.json").exists()


def test_october_hosted_download_checks_each_source_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parts = {"0-3": b"abcd", "4-7": b"efgh", "8-9": b"ij"}
    body = b"".join(parts.values())
    artifact = ArtifactBinding(
        relative_path="archive.zip",
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    output = tmp_path / artifact.relative_path
    monkeypatch.setattr(october, "SOURCE_REQUEST_BYTES", 4)
    ranges_seen = []
    corrupt_range = False

    class InterruptedStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"zz"
            raise httpx.ReadError("interrupted range")

    def serve(request):
        requested = request.headers["Range"].removeprefix("bytes=")
        ranges_seen.append(requested)
        returned = "0-3" if corrupt_range and requested == "4-7" else requested
        stream = (
            InterruptedStream()
            if requested == "4-7" and ranges_seen.count(requested) == 1
            else httpx.ByteStream(parts[requested])
        )
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {returned}/{len(body)}"},
            stream=stream,
        )

    with httpx.Client(
        base_url="http://100.64.1.2:18043/",
        transport=httpx.MockTransport(serve),
    ) as client:
        october.download_artifact(client, artifact, output)
        assert output.read_bytes() == body
        assert Counter(ranges_seen) == Counter(["0-3", "4-7", "4-7", "8-9"])
        corrupt_range = True
        with pytest.raises(ValueError, match="source range differs"):
            october.download_artifact(client, artifact, output)
        corrupt_range = False
        parts["8-9"] = b"xy"
        with pytest.raises(ValueError, match="source checksum differs"):
            october.download_artifact(client, artifact, output)


def test_october_reads_bounded_ranges_concurrently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"abcdefgh"
    artifact = ArtifactBinding(
        relative_path="archive.zip",
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    monkeypatch.setattr(october, "SOURCE_REQUEST_BYTES", 4)
    barrier = Barrier(2)

    def serve(request: httpx.Request) -> httpx.Response:
        start, end = map(
            int, request.headers["Range"].removeprefix("bytes=").split("-")
        )
        barrier.wait(timeout=5)
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(body)}"},
            stream=httpx.ByteStream(body[start : end + 1]),
        )

    with httpx.Client(
        base_url="http://100.64.1.2:18043/",
        transport=httpx.MockTransport(serve),
    ) as client:
        output = tmp_path / "archive.zip"
        october.download_artifact(client, artifact, output)
        assert output.read_bytes() == body


@pytest.mark.parametrize(
    ("head_status", "size", "body", "expected"),
    [
        (200, 4, b"data", "match"),
        (200, 4, b"date", "digest_mismatch"),
        (200, 20, None, "size_mismatch"),
        (404, 0, None, "unavailable"),
    ],
)
def test_october_online_checks_the_frozen_digest(
    tmp_path: Path,
    head_status: int,
    size: int,
    body: bytes | None,
    expected: str,
) -> None:
    artifact = ArtifactBinding(
        relative_path="drug/event/sample.json.zip",
        size=4,
        sha256=hashlib.sha256(b"data").hexdigest(),
    )

    def serve(request: httpx.Request) -> httpx.Response:
        assert (
            str(request.url) == october.FDA_ZIP_ORIGIN + artifact.relative_path
        )
        if request.method == "HEAD":
            return httpx.Response(
                head_status, headers={"Content-Length": str(size)}
            )
        assert body is not None, (
            "Only size-matched candidates should be fetched"
        )
        return httpx.Response(200, stream=httpx.ByteStream(body))

    with httpx.Client(
        base_url=october.FDA_ZIP_ORIGIN, transport=httpx.MockTransport(serve)
    ) as client:
        path = tmp_path / "candidate"
        url = october.FDA_ZIP_ORIGIN + artifact.relative_path
        assert (
            october.check_fda_zip(client, artifact, path, url)["status"]
            == expected
        )
        if expected == "match":
            assert path.read_bytes() == body


def test_october_online_only_appends_exact_matches_and_reads_them_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    matched, updated = (
        ArtifactBinding(
            relative_path=f"{name}.json.zip",
            size=4,
            sha256=hashlib.sha256(body).hexdigest(),
        )
        for name, body in (("matched", b"data"), ("updated", b"test"))
    )
    card = b"original README"
    final_card = ArtifactBinding(
        relative_path="README.md",
        size=len(card),
        sha256=hashlib.sha256(card).hexdigest(),
    )
    plan = PublicationPlan(
        release_version=october.BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=october.REPOSITORY,
            public_base_url=f"https://huggingface.co/datasets/{october.REPOSITORY}",
            revision="main",
        ),
        artifacts=(final_card, matched, updated),
    )
    revision = "b" * 40
    hub = types.SimpleNamespace(CommitOperationAdd=types.SimpleNamespace)
    writer = Mock()

    def commit(_repo, *, parent_commit, operations, **_options):
        assert parent_commit == COMMIT
        [addition] = operations
        assert addition.path_in_repo == matched.relative_path
        assert addition.path_or_fileobj.read_bytes() == b"data"
        return types.SimpleNamespace(oid=revision)

    writer.create_commit.side_effect = commit
    verifier = Mock()
    verifier.verify_artifact.return_value = ArtifactVerification(
        relative_path=matched.relative_path,
        size=matched.size,
        sha256=matched.sha256,
        verification_uri=f"{plan.target.public_base_url}/resolve/{revision}/{matched.relative_path}",
    )
    monkeypatch.setattr(october, "OctoberReadback", Mock(return_value=verifier))
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setitem(
        october.WAYBACK_CAPTURES, matched.relative_path, ("20260501030408",)
    )

    def serve(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"Content-Length": "4"})
        body = b"data" if request.url.host == "web.archive.org" else b"date"
        return httpx.Response(200, stream=httpx.ByteStream(body))

    client = httpx.Client(
        base_url=october.FDA_ZIP_ORIGIN, transport=httpx.MockTransport(serve)
    )
    monkeypatch.setattr(october.httpx, "Client", Mock(return_value=client))
    report_path = tmp_path / "online.json"
    assert (
        october.recover_fda_zips(
            report_path,
            plan,
            COMMIT,
            [final_card, matched, updated],
            writer,
            hub,
            COMMIT,
            prepared={final_card.relative_path: card},
        )
        == revision
    )
    verifier.verify_artifact.assert_called_once_with(
        target=plan.target, revision=revision, artifact=matched
    )
    report = json.loads(report_path.read_text())
    assert report["metadata_results"]["README.md"]["status"] == "match"
    assert report["completion_metadata_held"] == ["README.md"]
    assert report["missing_metadata"] == ["README.md"]
    assert report["zip_counts"] == {"match": 1, "digest_mismatch": 1}
    assert report["zip_results"][matched.relative_path][
        "source_url"
    ].startswith("https://web.archive.org/")
    assert (
        report["published_batches"][0]["verified"][0]["sha256"]
        == matched.sha256
    )


def test_october_rebuilds_exact_completion_metadata_from_conserved_evidence() -> (
    None
):
    frozen = PublicationPlan.model_validate_json(
        (october.ONLINE_SOURCES.parent / "publication-plan.json").read_bytes()
    )
    rebuilt = october.rebuild_completion_metadata(frozen)
    assert set(rebuilt) == {"README.md", "ARTIFACT-MANIFEST.json"}
    for artifact in frozen.artifacts:
        if artifact.relative_path in rebuilt:
            body = rebuilt[artifact.relative_path]
            assert (len(body), hashlib.sha256(body).hexdigest()) == (
                artifact.size,
                artifact.sha256,
            )
    assert october.archive_plan(rebuilt["ARTIFACT-MANIFEST.json"]) == frozen


def test_october_online_upload_requires_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GMA_MAINTAINER_PUBLICATION_APPROVED", raising=False)
    with pytest.raises(PermissionError, match="requires approval"):
        october.recover_online(tmp_path, COMMIT, publish_matches=True)


def test_fresh_openfda_waits_before_retrying_fda_rate_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = "drug/event/example.json.zip"
    request = httpx.Request("GET", fresh.ZIP_ROOT + path)
    advised = httpx.Response(
        429, headers={"Retry-After": "120"}, request=request
    )
    no_advice = httpx.Response(429, request=request)
    result = {"path": path}
    download = Mock(
        side_effect=[
            httpx.HTTPStatusError(
                "rate limited", request=request, response=advised
            ),
            httpx.HTTPStatusError(
                "rate limited", request=request, response=no_advice
            ),
            result,
        ]
    )
    waits: list[float] = []
    monkeypatch.setattr(fresh, "download_zip", download)
    monkeypatch.setattr(fresh.time, "sleep", waits.append)
    with httpx.Client() as client:
        assert fresh.fetch_zip(client, path, tmp_path / "archive.zip") == result
    assert waits == [120, 600]
    assert download.call_count == 3


def fresh_openfda_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    first, second = "drug/event/first.json.zip", "drug/event/second.json.zip"
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("data.json", "{}")
        payload = buffer.getvalue()
    index = fresh.json_bytes({
        "meta": {"last_updated": "2026-11-20"},
        "results": {
            "drug": {
                "event": {
                    "partitions": [
                        {"file": fresh.ZIP_ROOT + path}
                        for path in (first, second)
                    ]
                }
            },
            "device": {
                "udi": {
                    "partitions": [
                        {
                            "file": fresh.ZIP_ROOT
                            + "device/udi/excluded.json.zip"
                        }
                    ]
                }
            },
        },
    })
    contract = {
        "batch_id": FRESH_BATCH,
        "source_index_sha256": hashlib.sha256(index).hexdigest(),
        "source_index_date": "2026-11-20",
        "indexed_endpoints": 2,
        "indexed_payload_count": 3,
        "expected_endpoints": 1,
        "expected_payload_count": 2,
        "excluded_endpoint": "device/udi",
        "excluded_payload_count": 1,
        "source_url": fresh.INDEX_URL,
        "repository": f"edithatogo/global-medicines-atlas-{FRESH_BATCH}",
        "publication_approved": True,
        "approval_reference": "Synthetic maintainer approval.",
        "rights": {},
    }
    contract_path = tmp_path / "batches" / FRESH_BATCH / "manifest.json"
    contract_path.parent.mkdir(parents=True)
    contract_path.write_bytes(fresh.json_bytes(contract))
    monkeypatch.setattr(fresh, "BATCHES", contract_path.parent.parent)
    monkeypatch.setattr(fresh, "BATCH_SIZE", 1)
    monkeypatch.setattr(fresh, "CHECKPOINT_SIZE", 1)
    return first, second, index, payload, contract


def test_fresh_openfda_resumes_an_interrupted_upload_and_verification(  # ruff: ignore[too-many-statements] -- exercise both recovery points on one archive without rebuilding its state.
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second, index, payload, contract = fresh_openfda_fixture(
        tmp_path, monkeypatch
    )
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_SHA": COMMIT,
        "GITHUB_RUN_ID": "12345",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
        "GMA_PUBLICATION_ENVIRONMENT": "production",
        "HF_TOKEN": SYNTHETIC_HF_TOKEN,
    }.items():
        monkeypatch.setenv(name, value)
    requests = []

    stopped = True

    def serve(request):
        url = str(request.url)
        if url == fresh.INDEX_URL:
            return httpx.Response(200, content=index)
        requests.append(url)
        if len(requests) == 1:
            return httpx.Response(503)
        if url == fresh.ZIP_ROOT + second and stopped:
            return httpx.Response(403)
        return httpx.Response(
            200,
            headers={"Content-Length": str(len(payload)), "ETag": '"source"'},
            stream=httpx.ByteStream(payload),
        )

    monkeypatch.setattr(
        fresh,
        "BoundIPAddressTransport",
        lambda **_kw: httpx.MockTransport(serve),
    )
    monkeypatch.setattr(fresh.time, "sleep", lambda _delay: None)
    api = Mock()
    api.repo_info.return_value = types.SimpleNamespace(
        private=False, sha=COMMIT
    )
    published = {}
    preuploaded = {}
    scratch_files = []
    api.list_repo_refs.return_value = types.SimpleNamespace(tags=[])
    api.list_repo_files.side_effect = lambda *_args, **_kw: [
        ".gitattributes",
        *published,
    ]
    api.list_repo_tree.side_effect = lambda *_args, **_kw: [
        types.SimpleNamespace(
            path=path,
            size=len(body),
            lfs=types.SimpleNamespace(
                sha256=hashlib.sha256(body).hexdigest(), size=len(body)
            ),
        )
        for path, body in published.items()
    ]

    def preupload(_repo, *, additions, repo_type):
        assert repo_type == "dataset"
        (operation,) = additions
        path = Path(operation.path_or_fileobj)
        scratch_files.append(path)
        if operation.path_in_repo == first:
            preuploaded[first] = path.read_bytes()
            operation.path_or_fileobj = b""

    def commit(_repo, *, operations, parent_commit, **_kw):
        assert parent_commit == api.repo_info.return_value.sha
        assert all(not path.exists() for path in scratch_files)
        for operation in operations:
            name = operation.path_in_repo
            if getattr(operation, "delete", False):
                del published[name]
            else:
                published[name] = operation.path_or_fileobj or preuploaded[name]
        revision = f"{api.create_commit.call_count:040x}"
        api.repo_info.return_value.sha = revision
        return types.SimpleNamespace(oid=revision)

    def download_metadata(*, repo_id, filename, revision, repo_type, token):
        assert repo_id == contract["repository"]
        assert revision == api.repo_info.return_value.sha
        assert repo_type == "dataset"
        assert token is False
        path = tmp_path / filename
        path.write_bytes(published[filename])
        return path

    api.preupload_lfs_files.side_effect = preupload
    api.create_commit.side_effect = commit
    hub = types.SimpleNamespace(
        HfApi=lambda **_kw: api,
        hf_hub_download=download_metadata,
        RepoFile=types.SimpleNamespace,
        CommitOperationAdd=types.SimpleNamespace,
        CommitOperationDelete=lambda **kw: types.SimpleNamespace(
            **kw, delete=True
        ),
    )
    monkeypatch.setattr(fresh, "import_module", lambda _name: hub)

    def readback(*, target, revision, artifact):
        body = published[artifact.relative_path]
        return ArtifactVerification(
            relative_path=artifact.relative_path,
            sha256=hashlib.sha256(body).hexdigest(),
            size=len(body),
            verification_uri=f"{target.public_base_url}/resolve/{revision}/{artifact.relative_path}",
        )

    monkeypatch.setattr(
        fresh,
        "HuggingFaceAnonymousArtifactVerifier",
        lambda **_kw: types.SimpleNamespace(verify_artifact=readback),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "publisher",
            "publish",
            "--output",
            str(tmp_path),
            "--exact-commit",
            COMMIT,
            "--batch",
            FRESH_BATCH,
        ],
    )
    with pytest.raises(httpx.HTTPStatusError):
        fresh.main()
    assert set(published) == {first, fresh.PROGRESS}
    assert api.create_commit.call_count == 1
    stopped = False
    published[first] = b"x" * len(payload)
    with pytest.raises(ValueError, match="checkpoint checksum differs"):
        fresh.main()
    assert api.create_commit.call_count == 1
    published[first] = payload
    assert fresh.main() == 0
    assert set(published) == {first, second, fresh.MANIFEST, *fresh.METADATA}
    assert api.create_commit.call_count == 3
    # The next hosted run can recover an upload receipt after verification failed.
    monkeypatch.setenv("GITHUB_RUN_ID", "12346")
    assert fresh.main() == 0
    assert api.create_commit.call_count == 3
    sys.argv[1] = "verify"
    assert fresh.main() == 0
    assert (
        requests == [fresh.ZIP_ROOT + first] * 2 + [fresh.ZIP_ROOT + second] * 2
    )
    assert published[first] == published[second] == payload
    assert (
        json.loads((tmp_path / "verified.json").read_bytes())["state"]
        == "public"
    )
    manifest = json.loads(published["ARTIFACT-MANIFEST.json"])
    receipts = {record["path"]: record for record in manifest["artifacts"]}
    assert receipts[first]["source_etag"] == '"source"'
    assert manifest["excluded_payload_count"] == 1
    revision = api.repo_info.return_value.sha
    api.create_tag.side_effect = lambda *_args, **_kw: setattr(
        api.list_repo_refs.return_value,
        "tags",
        [
            types.SimpleNamespace(
                name=fresh.VERIFIED_TAG, target_commit=revision
            )
        ],
    )
    sys.argv[1] = "mark-verified"
    assert fresh.main() == 0
    api.create_tag.assert_called_once_with(
        contract["repository"],
        repo_type="dataset",
        tag=fresh.VERIFIED_TAG,
        revision=revision,
        exist_ok=True,
    )
    assert fresh.is_verified(api, contract, revision)
    monkeypatch.setenv("GITHUB_RUN_ID", "54321")
    with pytest.raises(ValueError, match="receipts do not match"):
        fresh.verify(tmp_path, COMMIT, FRESH_BATCH)


def test_fresh_openfda_refuses_local_or_changed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, index, _, contract = fresh_openfda_fixture(tmp_path, monkeypatch)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        fresh.publish(tmp_path, COMMIT, FRESH_BATCH)
    with pytest.raises(ValueError, match="FDA index SHA-256"):
        fresh.index_paths(index + b" ", contract)
    foreign_index = index.replace(b"download.open.fda.gov", b"example.test")
    foreign_contract = {
        **contract,
        "source_index_sha256": hashlib.sha256(foreign_index).hexdigest(),
    }
    with pytest.raises(ValueError, match="unapproved ZIP URL"):
        fresh.index_paths(foreign_index, foreign_contract)


def test_scheduled_index_change_records_candidate_without_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, index, _, contract = fresh_openfda_fixture(tmp_path, monkeypatch)
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_SHA": COMMIT,
        "GITHUB_RUN_ID": "12345",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
    }.items():
        monkeypatch.setenv(name, value)
    contract_path = fresh.BATCHES / FRESH_BATCH / "manifest.json"
    contract_path.write_bytes(
        fresh.json_bytes({**contract, "verified_revision": COMMIT})
    )
    revised = index.replace(b"2026-11-20", b"2026-11-21")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=revised)
        )
    )
    monkeypatch.setattr(fresh, "fda_client", lambda: client)
    api = Mock()
    api.repo_info.return_value = types.SimpleNamespace(
        private=False, sha=COMMIT
    )
    hub = types.SimpleNamespace(HfApi=Mock(return_value=api))
    monkeypatch.setattr(fresh, "import_module", lambda _name: hub)
    fresh.plan_run(tmp_path, COMMIT, "")
    hub.HfApi.assert_called_once_with(token=False)
    assert (tmp_path / "candidate-index.json").read_bytes() == revised
    assert "eligible=false" in (tmp_path / "output").read_text()
    assert "Already verified" in (tmp_path / "summary").read_text()
    api.create_commit.assert_not_called()


def write_contract(tmp_path: Path, **overrides: object) -> Path:
    """Create a contract in the committed source-batch shape."""
    batch = tmp_path / "quality/source-batches/synthetic"
    batch.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "batch_id": "synthetic",
        "repository": "owner/synthetic",
        "publication_approved": True,
        "approval_reference": "Synthetic maintainer approval.",
        "snapshot_id": "synthetic-snapshot",
        "source_authority": "Synthetic authority",
        "source_url": "https://example.gov/data",
        "retrieval_date": "2026-01-01",
        "schema_version": "synthetic/v1",
        "pretty_name": "Synthetic archive",
        "description": "Synthetic description.",
        "fields_and_transformations": "Unmodified synthetic source bytes.",
        "payload_suffix": ".bin",
        "expected_payload_count": 2,
        "expected_payload_bytes": 6,
        "rights": {
            "licence": "Synthetic public domain",
            "terms": "https://example.gov/terms",
            "attribution": "Synthetic authority, https://example.gov/data",
            "redistribution": "Permitted for unmodified source bytes.",
        },
        "not_included": ["No derived tables."],
    }
    manifest.update(overrides)
    path = batch / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def write_archive(tmp_path: Path) -> Path:
    """Create a two-payload archive matching the default contract."""
    root = tmp_path / "archive"
    (root / "group").mkdir(parents=True)
    (root / "group" / "first.bin").write_bytes(b"abc")
    (root / "second.bin").write_bytes(b"def")
    return root


@pytest.fixture(autouse=True)
def committed_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        publisher, "BATCHES", tmp_path / "quality/source-batches"
    )
    monkeypatch.setattr(publisher, "require_hosted_main", lambda _c: None)


def test_local_invocation_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        publisher, "require_hosted_main", real_require_hosted_main
    )
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    manifest = write_contract(tmp_path)
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_unapproved_contract_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, publication_approved=False)
    with pytest.raises(ValueError, match="not approved"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_manifest_outside_source_batches_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    manifest = outside / "manifest.json"
    manifest.write_text(json.dumps({"publication_approved": True}))
    with pytest.raises(ValueError, match="committed source-batch"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_payload_count_drift_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, expected_payload_count=3)
    with pytest.raises(ValueError, match="payload count differs"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_payload_byte_drift_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, expected_payload_bytes=7)
    with pytest.raises(ValueError, match="payload bytes differ"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_recorded_digest_mismatch_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(
        tmp_path,
        recorded_payload_digests={"second.bin": "0" * 64},
    )
    with pytest.raises(ValueError, match="recorded payload digest differs"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_prepare_binds_every_file_without_upload(tmp_path: Path) -> None:
    archive = write_archive(tmp_path)
    output = tmp_path / "out"
    assert (
        publisher.publish_bulk_archive(
            write_contract(tmp_path), archive, output, COMMIT
        )
        == 0
    )
    plan = json.loads(
        (output / "publication-receipts" / "plan.json").read_text()
    )
    bound = [item["relative_path"] for item in plan["artifacts"]]
    assert bound == sorted(
        str(path.relative_to(archive))
        for path in archive.rglob("*")
        if path.is_file()
    )
    assert plan["target"]["repository"] == "owner/synthetic"
    assert "ARTIFACT-MANIFEST.json" in bound
    assert "allow_identical_content" not in plan


def test_prepared_bulk_archive_keeps_identical_files_at_distinct_paths(
    tmp_path: Path,
) -> None:
    archive = write_archive(tmp_path)
    (archive / "second.bin").write_bytes(b"abc")
    output = tmp_path / "out"
    manifest = write_contract(tmp_path, allow_identical_content=True)

    assert (
        publisher.publish_bulk_archive(manifest, archive, output, COMMIT) == 0
    )

    report = output / "publication-receipts" / "plan.json"
    plan = json.loads(report.read_text())
    assert plan["allow_identical_content"] is True
    payloads = [
        item
        for item in plan["artifacts"]
        if item["relative_path"].endswith(".bin")
    ]
    assert [item["relative_path"] for item in payloads] == [
        "group/first.bin",
        "second.bin",
    ]
    assert payloads[0]["sha256"] == payloads[1]["sha256"]


def test_card_records_rights_and_scope(tmp_path: Path) -> None:
    archive = write_archive(tmp_path)
    publisher.publish_bulk_archive(
        write_contract(tmp_path), archive, tmp_path / "out", COMMIT
    )
    card = (archive / "README.md").read_text()
    assert "Synthetic authority" in card
    assert "Permitted for unmodified source bytes." in card
    assert "## What this archive is not" in card
    assert "- No derived tables." in card


def test_publish_refuses_without_external_write_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GMA_PUBLICATION_ENVIRONMENT", raising=False)
    monkeypatch.delenv("GMA_MAINTAINER_PUBLICATION_APPROVED", raising=False)
    with pytest.raises(PermissionError, match="explicit maintainer approval"):
        publisher.publish_bulk_archive(
            write_contract(tmp_path),
            write_archive(tmp_path),
            tmp_path / "out",
            COMMIT,
            publish=True,
        )


class _CommitInfo:
    oid = "b" * 40


class _RecordingApi:
    """Record exactly how the hub is called by the uploader."""

    def __init__(self) -> None:
        self.token = ""
        self.created: list[dict[str, object]] = []
        self.uploaded: list[dict[str, object]] = []

    def create_repo(self, **kwargs: object) -> None:
        self.created.append(kwargs)

    def upload_folder(self, **kwargs: object) -> _CommitInfo:
        self.uploaded.append(kwargs)
        return _CommitInfo()


class _HfApiFactory:
    """Stand in for ``HfApi`` and hand every instance to the recorder."""

    def __init__(self, api: _RecordingApi) -> None:
        self._api = api

    def __call__(self, *, token: str) -> _RecordingApi:
        self._api.token = token
        return self._api


def test_uploader_calls_only_supported_hub_keywords(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard the hub call shape: an unsupported keyword fails only at runtime."""

    api = _RecordingApi()
    module = types.ModuleType("huggingface_hub")
    cast("Any", module).HfApi = _HfApiFactory(api)
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setenv("HF_TOKEN", SYNTHETIC_HF_TOKEN)
    folder = write_archive(tmp_path)

    revision = publisher.HuggingFaceFolderUploader(
        repository="owner/synthetic"
    ).upload_folder(
        repository="owner/synthetic",
        folder=folder,
        commit_message="Archive synthetic",
    )

    assert revision == "b" * 40
    assert api.token == SYNTHETIC_HF_TOKEN
    assert api.created == [
        {
            "repo_id": "owner/synthetic",
            "repo_type": "dataset",
            "private": False,
            "exist_ok": True,
        }
    ]
    assert api.uploaded == [
        {
            "repo_id": "owner/synthetic",
            "repo_type": "dataset",
            "folder_path": folder,
            "commit_message": "Archive synthetic",
        }
    ]


def test_uploader_refuses_a_different_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HF_TOKEN", SYNTHETIC_HF_TOKEN)
    with pytest.raises(ValueError, match="target differs"):
        publisher.HuggingFaceFolderUploader(
            repository="owner/synthetic"
        ).upload_folder(
            repository="owner/other",
            folder=write_archive(tmp_path),
            commit_message="Archive other",
        )


def test_archive_status_requires_pinned_inventory_and_reports_checksum_drift() -> (
    None
):
    entries = tuple(
        ArtifactBinding(relative_path=f"{name}.zip", size=100, sha256="a" * 64)
        for name in ("matching", "wrong", "missing")
    )
    repository = "maintainer/approved"
    revision = "b" * 40

    def serve(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.path
            == f"/api/datasets/{repository}/revision/{revision}"
        )
        assert request.url.params["blobs"] == "true"
        return httpx.Response(
            200,
            json={
                "private": False,
                "sha": revision,
                "siblings": [
                    {
                        "rfilename": item.relative_path,
                        "size": item.size,
                        "lfs": {"sha256": digest, "size": item.size},
                    }
                    for item, digest in zip(
                        entries[:2], ("a" * 64, "c" * 64), strict=True
                    )
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        info = archives.hub_info(client, repository, revision)
        assert archives.compare_inventory(info, entries) == {
            "revision": revision,
            "missing": ["missing.zip"],
            "drifted": ["wrong.zip"],
            "hub_digests_matched": 1,
        }


def test_archive_status_surfaces_nadac_candidate_from_official_metadata() -> (
    None
):
    candidate = "https://download.medicaid.gov/data/nadac-national-average-drug-acquisition-cost-11-25-2026.csv"

    def serve(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == archives.NADAC_INDEX
        return httpx.Response(
            200,
            json={
                "distribution": [{"downloadURL": candidate}],
                "modified": "2026-11-20T14:26:02Z",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        result = archives.nadac_status(client)
    assert result["state"] == "candidate"
    assert result["source_url"] == candidate
    assert result["baseline_url"].endswith("10-28-2026.csv")
