"""Exact public-byte and parent preservation controls; all data are synthetic."""

import base64
import hashlib
import io
import json
import lzma
import urllib.error
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from scripts import publish_remaining_public_archives as subject


@pytest.fixture
def _hosted(monkeypatch):
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "HF_TOKEN": "synthetic",
        "GITHUB_SHA": "reviewed",
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(name, value)


def cohort():
    payload = b"Year,Services\n2025,12\n"
    digest = hashlib.sha256(payload).hexdigest()
    item = {
        "bytes": len(payload),
        "sha256": digest,
        "resource": {
            "source_id": "au-data-gov-medicare-statistics",
            "category": "medicare_mbs_item_statistics",
            "url": "https://data.gov.au/public.csv",
            "filename": "public.csv",
            "archive_path": f"raw/mbs/medicare/{digest}/public.csv",
            "period_label": "synthetic 2025",
        },
    }
    existing = {
        "dataset": "edithatogo/australian-mbs-utilisation-archive",
        "files": [{"path": "raw/old.csv", "bytes": 3, "sha256": "0" * 64}],
        "file_count": 1,
    }
    expected = {
        "dataset": existing["dataset"],
        "parent_revision": "parent",
        "manifest_sha256": subject.digest_json(existing),
        "files": [item],
        "prior_verification_run": 123,
    }
    return payload, item, existing, expected


def sdk_fixture(tmp_path, _existing, *, bad_manifest=False, bad_payload=False):
    remote = {}

    def add(**kwargs):
        return kwargs

    def commit(**kwargs):
        assert kwargs["parent_commit"] == "parent"
        for op in kwargs["operations"]:
            remote[op["path_in_repo"]] = Path(
                op["path_or_fileobj"]
            ).read_bytes()
        return SimpleNamespace(oid="new")

    def download(**kwargs):
        assert kwargs["token"] is False
        assert kwargs["revision"] == "new"
        name = kwargs["filename"]
        data = remote[name]
        if bad_manifest and name == "manifest.json":
            data = b"{}"
        if bad_payload and name != "manifest.json":
            data = b"corrupted"
        p = tmp_path / "download"
        p.write_bytes(data)
        return str(p)

    api = SimpleNamespace(create_commit=Mock(side_effect=commit))
    sdk = SimpleNamespace(
        HfApi=lambda **_kwargs: api,
        CommitOperationAdd=add,
        hf_hub_download=download,
    )
    return sdk, api


def test_local_publication_rejected_before_any_input(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(PermissionError, match="Actions main"):
        subject.main()
    with pytest.raises(PermissionError, match="Actions main"):
        subject.publish(None, {}, Path())


@pytest.mark.parametrize(
    "change", ["revision", "manifest", "missing", "duplicate"]
)
def test_snapshot_rejects_drift(monkeypatch, change):
    _, _, existing, expected = cohort()
    parent = "parent"
    if change == "revision":
        parent = "other"
    elif change == "manifest":
        existing["dataset"] = "other"
    elif change == "missing":
        existing = None
    else:
        existing["files"] *= 2
        expected["manifest_sha256"] = subject.digest_json(existing)
    monkeypatch.setattr(
        subject,
        "fetch_existing_harvest_manifest",
        lambda *_args: (parent, existing),
    )
    with pytest.raises(RuntimeError):
        subject.snapshot(
            SimpleNamespace(HfApi=lambda **_kwargs: None), expected
        )


@pytest.mark.parametrize(
    "failure", ["none", "manifest", "payload", "collision"]
)
@pytest.mark.usefixtures("_hosted")
def test_exact_append_preserves_prior_and_verifies_new(
    monkeypatch, tmp_path, failure
):
    payload, item, existing, expected = cohort()
    if failure == "collision":
        existing["files"][0]["path"] = item["resource"]["archive_path"]
    monkeypatch.setattr(
        subject, "snapshot", lambda *_args: ("parent", existing)
    )
    monkeypatch.setattr(
        subject,
        "read_public_payload",
        lambda *_args: (payload, item["resource"]["url"]),
    )
    sdk, api = sdk_fixture(
        tmp_path,
        existing,
        bad_manifest=failure == "manifest",
        bad_payload=failure == "payload",
    )
    if failure != "none":
        with pytest.raises(RuntimeError):
            subject.publish(sdk, expected, tmp_path / "stage")
        if failure == "collision":
            api.create_commit.assert_not_called()
        return
    result = subject.publish(sdk, expected, tmp_path / "stage")
    assert result["verified_file_count"] == 2
    assert result["prior_manifest_objects_preserved"] == 1
    assert result["archive_file_count"] == 3
    assert result["anonymous_digest_verification"] == "passed"
    api.create_commit.assert_called_once()


@pytest.mark.usefixtures("_hosted")
def test_exact_digest_reuse_performs_no_mutation(monkeypatch, tmp_path):
    _, item, existing, expected = cohort()
    existing["files"][0].update(sha256=item["sha256"], bytes=item["bytes"])
    monkeypatch.setattr(
        subject, "snapshot", lambda *_args: ("parent", existing)
    )
    sdk, api = sdk_fixture(tmp_path, existing)
    receipt = subject.publish(sdk, expected, tmp_path)
    assert receipt["new_payloads"] == 0
    assert receipt["anonymous_digest_verification"] == "passed"
    assert receipt["verified_file_count"] == 0
    assert receipt["prior_anonymous_verification_run"] == 123
    assert "proof reused" in receipt["verification_scope"]
    api.create_commit.assert_not_called()


@pytest.mark.parametrize("case", ["digest", "length", "zip", "validzip"])
def test_payload_validation(case):
    payload, item, _, _ = cohort()
    if case == "digest":
        payload = b"x" * len(payload)
    elif case == "length":
        payload += b"x"
    else:
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("table.csv", payload)
        payload = b.getvalue()
        item["resource"]["filename"] = "tables.zip"
        item.update(
            bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest()
        )
        if case == "zip":
            # Two distinct members are valid, but a mocked metadata limit rejects.
            old = subject.MAX_MEMBERS
            subject.MAX_MEMBERS = 0
            try:
                with pytest.raises(ValueError, match="metadata"):
                    subject.validate_payload(payload, item)
            finally:
                subject.MAX_MEMBERS = old
            return
    if case == "validzip":
        subject.validate_payload(payload, item)
    else:
        with pytest.raises(ValueError, match="reviewed digest"):
            subject.validate_payload(payload, item)


@pytest.mark.parametrize(
    ("url", "limit"),
    [
        ("http://data.gov.au/a", 1),
        ("https://private.example/a", 1),
        ("https://data.gov.au/a", 0),
        ("https://data.gov.au/a", subject.MAX_BYTES + 1),
    ],
)
def test_unapproved_url_or_bound_rejected(url, limit):
    with pytest.raises(ValueError, match=r"public|Public|HTTP|HTML"):
        subject.read_public_payload(url, limit)


@pytest.mark.parametrize(
    "case", ["ok", "status", "range", "length", "html", "truncated"]
)
def test_bounded_public_get(monkeypatch, case):
    headers = {}
    body = b"abc"
    status = 200
    if case == "status":
        status = 206
    elif case == "range":
        headers["Content-Range"] = "bytes 0-2/10"
    elif case == "length":
        headers["Content-Length"] = "4"
    elif case == "html":
        headers["Content-Type"] = "text/html"
    elif case == "truncated":
        body = b"ab"
    response = Mock(status=status, headers=headers, url="https://data.gov.au/a")
    response.read.return_value = body
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(
        subject.urllib.request,
        "build_opener",
        lambda *_args: SimpleNamespace(open=lambda *_args, **_kwargs: response),
    )
    if case == "ok":
        assert subject.read_public_payload("https://data.gov.au/a", 3) == (
            b"abc",
            "https://data.gov.au/a",
        )
    else:
        with pytest.raises(ValueError, match=r"public|Public|HTTP|HTML"):
            subject.read_public_payload("https://data.gov.au/a", 3)


@pytest.mark.parametrize("case", ["ok", "unauthorized", "destination"])
@pytest.mark.usefixtures("_hosted")
def test_main_uses_only_committed_contract(monkeypatch, tmp_path, case):
    monkeypatch.chdir(tmp_path)
    Path("build").mkdir()
    _, _, _, expected = cohort()
    if case == "destination":
        expected["dataset"] = "other"
    contract = {
        "external_publication_authorized": case != "unauthorized",
        "archives": {"mbs": expected},
    }
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract))
    monkeypatch.setattr(subject, "CONTRACT", path)
    monkeypatch.setenv("PUBLIC_ARCHIVE_DESTINATION", "mbs")
    monkeypatch.setattr(subject.importlib, "import_module", lambda _name: None)
    monkeypatch.setattr(
        subject,
        "publish",
        lambda *_args: {"anonymous_digest_verification": "passed"},
    )
    if case == "ok":
        subject.main()
        assert (
            json.loads(
                Path("build/mbs-utilisation-harvest-receipt.json").read_text(
                    encoding="utf-8"
                )
            )["anonymous_digest_verification"]
            == "passed"
        )
    else:
        with pytest.raises((ValueError, PermissionError)):
            subject.main()


@pytest.mark.usefixtures("_hosted")
@pytest.mark.parametrize(
    "case", ["ok", "digest", "file_set", "duplicate", "bounds", "trailing"]
)
def test_custodial_requires_reviewed_original_bytes(
    monkeypatch, tmp_path, case
):

    payload, item, _, expected = cohort()
    item["resource"]["filename"] = "public.xls"
    item["resource"]["archive_path"] = "raw/mbs/custodial/public.xls"
    document = {"public.xls": payload.decode("latin1")}
    if case == "file_set":
        document = {"other.xls": payload.decode("latin1")}
    raw = json.dumps(document).encode()
    if case == "duplicate":
        raw = b'{"public.xls":"a","public.xls":"a"}'
    compressed = lzma.compress(raw)
    expected["custodial"] = {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "files": {"public.xls": item},
        "provenance": "Synthetic public custodial report",
        "segments": {},
    }
    if case == "digest":
        expected["custodial"]["input_sha256"] = "0" * 64
    if case == "bounds":
        monkeypatch.setattr(subject, "MAX_CUSTODIAL_INPUT", 1)
    if case == "trailing":
        compressed += b"extra"
    monkeypatch.setattr(
        subject,
        "collect_segments",
        lambda _contract: base64.b64encode(compressed).decode(),
    )
    if case != "ok":
        with pytest.raises(ValueError, match="Custodial public"):
            subject.stage_custodial(expected, tmp_path)
        return
    stages = subject.stage_custodial(expected, tmp_path)
    assert stages[0].staged_payload_path.read_bytes() == payload
    receipt = json.loads(
        stages[0].staged_receipt_path.read_text(encoding="utf-8")
    )
    assert receipt["source_url_role"] == "publisher landing page only"


@pytest.mark.usefixtures("_hosted")
def test_main_stages_only_exact_approved_segment(monkeypatch, tmp_path):
    _, _, _, expected = cohort()
    expected["custodial"] = {"segments": {"stage-remaining-0000": {}}}
    path = tmp_path / "contract.json"
    path.write_text(
        json.dumps({
            "external_publication_authorized": True,
            "archives": {"mbs": expected},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(subject, "CONTRACT", path)
    monkeypatch.setenv("PUBLIC_ARCHIVE_DESTINATION", "mbs")
    monkeypatch.setenv("MBS_PUBLIC_BATCH", "stage-remaining-0000")
    stage = Mock()
    monkeypatch.setattr(subject, "stage_segment", stage)
    subject.main()
    stage.assert_called_once_with("stage-remaining-0000", expected["custodial"])


@pytest.mark.parametrize(
    "case",
    [
        "complete_range",
        "ignored_range",
        "short_range",
        "second_403",
        "second_403_no_url",
        "other_host",
        "other_status",
    ],
)
def test_aihw_media_range_recovery_is_bounded_and_exact(monkeypatch, case):
    url = "https://www.aihw.gov.au/getmedia/synthetic/public.zip"
    if case == "other_host":
        url = "https://data.gov.au/public.zip"
    first_code = 401 if case == "other_status" else 403
    first = urllib.error.HTTPError(
        url, first_code, "synthetic refusal", None, None
    )
    response = Mock(
        status=206,
        headers={"Content-Range": "bytes 0-2/3", "Content-Length": "3"},
        url=url,
    )
    response.read.return_value = b"abc"
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    if case == "ignored_range":
        response.status = 200
        response.headers = {"Content-Length": "3"}
    if case == "short_range":
        response.headers["Content-Range"] = "bytes 0-1/3"
    calls = []

    def open_request(request, **_kwargs):
        calls.append(dict(request.header_items()))
        if len(calls) == 1:
            raise first
        assert request.get_header("Range") == "bytes=0-2"
        if case in {"second_403", "second_403_no_url"}:
            raise urllib.error.HTTPError(
                None if case == "second_403_no_url" else url,
                403,
                "synthetic refusal",
                None,
                None,
            )
        return response

    monkeypatch.setattr(
        subject.urllib.request,
        "build_opener",
        lambda *_args: SimpleNamespace(open=open_request),
    )
    monkeypatch.setattr(
        subject,
        "read_aihw_with_curl",
        Mock(side_effect=urllib.error.URLError("synthetic system refusal")),
    )
    if case in {"complete_range", "ignored_range"}:
        assert subject.read_public_payload(url, 3) == (b"abc", url)
    elif case == "short_range":
        with pytest.raises(ValueError, match="Full public"):
            subject.read_public_payload(url, 3)
    else:
        with pytest.raises(urllib.error.URLError):
            subject.read_public_payload(url, 3)
    assert len(calls) == (1 if case in {"other_host", "other_status"} else 2)


@pytest.mark.usefixtures("_hosted")
@pytest.mark.parametrize("all_unavailable", [False, True])
def test_public_transport_failure_preserves_independent_successes(
    monkeypatch, tmp_path, all_unavailable
):
    payload, item, existing, expected = cohort()
    missing = json.loads(json.dumps(item))
    missing["resource"]["filename"] = "unavailable.csv"
    missing["resource"]["url"] = "https://data.gov.au/unavailable.csv"
    missing["sha256"] = "f" * 64
    expected["files"] = [item, missing]
    monkeypatch.setattr(
        subject, "snapshot", lambda *_args: ("parent", existing)
    )

    def read(url, _limit):
        if all_unavailable or "unavailable" in url:
            raise urllib.error.HTTPError(
                url, 403, "synthetic public transport refusal", None, None
            )
        return payload, url

    monkeypatch.setattr(subject, "read_public_payload", read)
    sdk, api = sdk_fixture(tmp_path, existing)
    if all_unavailable:
        with pytest.raises(RuntimeError, match="HF unchanged"):
            subject.publish(sdk, expected, tmp_path / "stage")
        api.create_commit.assert_not_called()
    else:
        result = subject.publish(sdk, expected, tmp_path / "stage")
        assert result["new_payloads"] == 1
        assert result["run_coverage"]["coverage_status"] == "partial"
        assert (
            result["run_coverage"]["failed_resources"][0]["filename"]
            == "unavailable.csv"
        )
        api.create_commit.assert_called_once()
    audit = json.loads(
        (tmp_path / "stage" / "acquisition.json").read_text(encoding="utf-8")
    )
    assert audit["coverage_status"] == "partial"
    assert all(r["http_status"] == 403 for r in audit["failed_resources"])


@pytest.mark.parametrize(
    "case",
    [
        "ok",
        "missing",
        "old",
        "bad_version",
        "version_failure",
        "version_timeout",
        "http_failure",
        "transfer_timeout",
        "wrong_length",
    ],
)
def test_system_aihw_client_is_size_bounded_and_has_no_auth_or_redirects(
    monkeypatch, tmp_path, case
):
    url = "https://www.aihw.gov.au/getmedia/synthetic/public.zip"
    if case == "missing":
        monkeypatch.setattr(
            subject, "CURL_EXECUTABLE", str(tmp_path / "missing-curl")
        )
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == "/usr/bin/curl"
        assert argv[1] == "--disable"
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        if "--version" in argv:
            if case == "version_timeout":
                raise subject.subprocess.TimeoutExpired(argv, 10)
            version = (
                b"curl 8.3.0"
                if case == "old"
                else b"unknown"
                if case == "bad_version"
                else b"curl 8.7.1 qualified"
            )
            return SimpleNamespace(
                returncode=1 if case == "version_failure" else 0, stdout=version
            )
        assert "--location" not in argv
        assert "--insecure" not in argv
        assert "--proto" in argv
        assert "=https" in argv
        assert argv[argv.index("--max-filesize") + 1] == "3"
        assert argv[argv.index("--range") + 1] == "0-2"
        if case == "transfer_timeout":
            raise subject.subprocess.TimeoutExpired(argv, 190)
        return SimpleNamespace(
            returncode=22 if case == "http_failure" else 0,
            stdout=b"ab" if case == "wrong_length" else b"abc",
        )

    monkeypatch.setattr(subject.subprocess, "run", run)
    if case == "ok":
        assert subject.read_aihw_with_curl(url, 3) == (b"abc", url)
    else:
        with pytest.raises((urllib.error.URLError, ValueError)):
            subject.read_aihw_with_curl(url, 3)
    assert len(calls) == (
        0
        if case == "missing"
        else 1
        if case in {"old", "bad_version", "version_failure", "version_timeout"}
        else 2
    )


@pytest.mark.parametrize(
    ("url", "limit"),
    [
        ("http://www.aihw.gov.au/a", 3),
        ("https://data.gov.au/a", 3),
        ("https://www.aihw.gov.au/a", 0),
    ],
)
def test_system_client_refuses_other_destinations(url, limit):
    with pytest.raises(ValueError, match="Unapproved AIHW"):
        subject.read_aihw_with_curl(url, limit)


@pytest.mark.usefixtures("_hosted")
def test_observed_canonical_url_keeps_original_source_provenance(
    monkeypatch, tmp_path
):
    payload, item, existing, expected = cohort()
    item["resolved_public_url"] = "https://data.gov.au/canonical.csv"
    calls = []

    def read(url, _limit):
        calls.append(url)
        return payload, url

    monkeypatch.setattr(subject, "read_public_payload", read)
    stages, coverage = subject.stage_public_sources(
        expected, tmp_path, {r["path"]: r for r in existing["files"]}
    )
    assert calls == ["https://data.gov.au/canonical.csv"]
    receipt = json.loads(
        stages[0].staged_receipt_path.read_text(encoding="utf-8")
    )
    assert receipt["source_url"] == "https://data.gov.au/public.csv"
    assert receipt["final_url"] == "https://data.gov.au/canonical.csv"
    assert coverage["coverage_status"] == "complete"


@pytest.mark.usefixtures("_hosted")
def test_noop_without_prior_anonymous_proof_fails_closed(monkeypatch, tmp_path):
    _, item, existing, expected = cohort()
    existing["files"][0].update(sha256=item["sha256"], bytes=item["bytes"])
    expected.pop("prior_verification_run")
    monkeypatch.setattr(
        subject, "snapshot", lambda *_args: ("parent", existing)
    )
    sdk, api = sdk_fixture(tmp_path, existing)
    with pytest.raises(RuntimeError, match="No prior anonymous proof"):
        subject.publish(sdk, expected, tmp_path)
    api.create_commit.assert_not_called()
