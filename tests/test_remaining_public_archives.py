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

import httpx
import pytest
import yaml
from scripts import public_draft_transport as transport
from scripts import publish_incremental_public_archives as incremental
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


@pytest.fixture
def draft_transport(monkeypatch):
    payload, item, _, _ = cohort()
    item["draft_transport"] = {
        "release_id": 10,
        "asset_id": 20,
        "asset_name": "public.csv",
        "tag_name": "temporary",
        "target_commitish": "reviewed",
    }
    asset = {
        "id": 20,
        "name": "public.csv",
        "size": len(payload),
        "digest": "sha256:" + item["sha256"],
        "state": "uploaded",
        "url": transport.API + "/releases/assets/20",
    }
    release = {
        "id": 10,
        "draft": True,
        "published_at": None,
        "tag_name": "temporary",
        "target_commitish": "reviewed",
        "author": {"login": "edithatogo"},
        "assets": [asset],
    }
    requests = []
    settings = {
        "redirect": True,
        "host": transport.ASSET_HOST,
        "body": payload,
        "status": 200,
        "network_error": False,
    }
    real_client = httpx.Client

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/releases/10"):
            return httpx.Response(200, json=release)
        if request.url.host == "api.github.com":
            if settings["redirect"]:
                return httpx.Response(
                    302,
                    headers={}
                    if settings.get("missing_location")
                    else {
                        "location": "https://"
                        + settings["host"]
                        + "/asset?token=synthetic"
                    },
                )
            return httpx.Response(settings["status"], content=settings["body"])
        if settings["network_error"]:
            raise httpx.ReadTimeout(
                "signed URL token=synthetic", request=request
            )
        return httpx.Response(settings["status"], content=settings["body"])

    monkeypatch.setenv("GH_TOKEN", "synthetic")
    monkeypatch.setattr(
        transport.httpx,
        "Client",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    return transport, payload, item, release, asset, requests, settings


@pytest.mark.parametrize("redirect", [True, False])
def test_draft_exact_read_and_bearer_boundary(draft_transport, redirect):
    t, payload, item, _, _, requests, settings = draft_transport
    settings["redirect"] = redirect
    assert t.read_draft_payload(item) == payload
    for request in requests:
        assert request.headers.get("authorization") == (
            "Bearer synthetic" if request.url.host == "api.github.com" else None
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("release_id", True),
        ("release_id", 0),
        ("asset_id", "20"),
        ("asset_id", -1),
    ],
)
def test_draft_identity_rejected_before_network(draft_transport, field, value):
    t, _, item, _, _, requests, _ = draft_transport
    item["draft_transport"][field] = value
    with pytest.raises(ValueError, match="identity"):
        t.read_draft_payload(item)
    assert not requests


@pytest.mark.parametrize("value", [0, 512 * 1024**2 + 1])
def test_draft_payload_bound_rejected(draft_transport, value):
    t, _, item, _, _, requests, _ = draft_transport
    item["bytes"] = value
    with pytest.raises(ValueError, match="identity"):
        t.read_draft_payload(item)
    assert not requests


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", 11),
        ("draft", False),
        ("published_at", "published"),
        ("tag_name", "other"),
        ("target_commitish", "other"),
        ("author", {"login": "other"}),
    ],
)
def test_draft_state_or_owner_change_rejected(draft_transport, field, value):
    t, _, item, release, _, requests, _ = draft_transport
    release[field] = value
    with pytest.raises(ValueError, match="ownership or state"):
        t.read_draft_payload(item)
    assert len(requests) == 1


@pytest.mark.parametrize("assets", [[], [20, 20]])
def test_draft_missing_or_ambiguous_asset_rejected(draft_transport, assets):
    t, _, item, release, asset, _, _ = draft_transport
    release["assets"] = [asset for _ in assets]
    with pytest.raises(ValueError, match="missing or ambiguous"):
        t.read_draft_payload(item)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "other"),
        ("state", "starter"),
        ("size", 1),
        ("digest", "sha256:wrong"),
        ("url", "https://untrusted.invalid/asset"),
    ],
)
def test_draft_metadata_substitution_rejected(draft_transport, field, value):
    t, _, item, _, asset, requests, _ = draft_transport
    asset[field] = value
    with pytest.raises(ValueError, match="metadata differs"):
        t.read_draft_payload(item)
    assert len(requests) == 1


def test_draft_redirect_and_response_boundaries(draft_transport):
    t, payload, item, _, _, requests, settings = draft_transport
    settings["host"] = "untrusted.invalid"
    with pytest.raises(ValueError, match="redirect target denied"):
        t.read_draft_payload(item)
    assert all(r.url.host == "api.github.com" for r in requests)
    settings["host"] = t.ASSET_HOST
    settings["status"] = 206
    with pytest.raises(ValueError, match="complete object"):
        t.read_draft_payload(item)
    settings["status"] = 200
    settings["body"] = payload + b"x"
    with pytest.raises(ValueError, match="byte bound"):
        t.read_draft_payload(item)
    settings["body"] = payload[:-1]
    with pytest.raises(ValueError, match="length differs"):
        t.read_draft_payload(item)
    settings["redirect"] = False
    settings["status"] = 404
    with pytest.raises(ValueError, match="unavailable; URL withheld"):
        t.read_draft_payload(item)


def test_draft_network_error_withholds_signed_url(draft_transport):
    t, _, item, _, _, _, settings = draft_transport
    settings["network_error"] = True
    with pytest.raises(RuntimeError, match="URLs withheld") as error:
        t.read_draft_payload(item)
    assert "token=" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.usefixtures("_hosted")
def test_draft_source_provenance_and_atomic_failure(tmp_path, monkeypatch):
    payload, item, existing, expected = cohort()
    item["draft_transport"] = {"release_id": 10, "asset_id": 20}
    monkeypatch.setattr(subject, "read_draft_payload", lambda _item: payload)
    stages, coverage = subject.stage_public_sources(
        expected, tmp_path / "stage", {f["path"]: f for f in existing["files"]}
    )
    receipt = json.loads(stages[0].staged_receipt_path.read_text())
    assert receipt["source_url"] == item["resource"]["url"]
    assert receipt["retrieved_at_role"] == "hosted public-copy materialization"
    assert receipt["transport"]["asset_id"] == 20
    assert coverage["coverage_status"] == "complete"
    monkeypatch.setattr(
        subject,
        "read_draft_payload",
        Mock(side_effect=ValueError("draft state changed")),
    )
    with pytest.raises(ValueError, match="state changed"):
        subject.stage_public_sources(expected, tmp_path / "failed", {})


@pytest.fixture
def incremental_setup(tmp_path, monkeypatch, _hosted):
    _, item, _, expected = cohort()
    item["draft_transport"] = {"release_id": 10, "asset_id": 20}
    archive = dict(
        expected,
        batches=[
            {"id": "mbs-01", "files": [item]},
            {"id": "mbs-02", "files": [item]},
        ],
    )
    archive.pop("files")
    archive["prior_verification_run"] = [123]
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps({
            "external_publication_authorized": True,
            "archives": {"mbs": archive},
        })
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PUBLIC_ARCHIVE_DESTINATION", "mbs")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "build/mbs-util-hf-home"))
    monkeypatch.setattr(incremental, "CONTRACT", contract)
    monkeypatch.setattr(incremental, "CHECKPOINTS", tmp_path / "checkpoints")
    result = {
        "dataset": archive["dataset"],
        "new_payloads": 1,
        "anonymous_digest_verification": "passed",
        "manifest_sha256": "digest",
        "revision": "next",
        "workflow_commit": "reviewed",
        "workflow_run": "123",
        "workflow_attempt": "1",
        "run_coverage": {"coverage_status": "complete", "failed_resources": []},
        "temporary_source_bytes_removed": False,
    }
    mock = Mock(side_effect=lambda *_args: dict(result))
    monkeypatch.setattr(incremental, "publish", mock)
    return incremental, archive, contract, result, mock


def test_incremental_parent_chain_and_cleanup(incremental_setup, tmp_path):
    inc, archive, _, _, publish_mock = incremental_setup
    for directory in ["build/harvest", "build/mbs-util-hf-home"]:
        q = tmp_path / directory
        q.mkdir(parents=True)
        (q / "public-source").write_bytes(b"synthetic")
    first = inc.execute_batch(None, 1)
    assert first["batch_id"] == "mbs-01"
    assert first["temporary_source_bytes_removed"] is True
    assert not (tmp_path / "build/harvest").exists()
    assert not (tmp_path / "build/mbs-util-hf-home").exists()
    second = inc.execute_batch(None, 2)
    expected = publish_mock.call_args.args[1]
    assert expected["parent_revision"] == first["revision"]
    assert expected["manifest_sha256"] == first["manifest_sha256"]
    assert expected["prior_verification_run"] == [123, 123]
    assert second["incremental_total_new_payloads"] == 2
    with pytest.raises(ValueError, match="substitute another parent"):
        inc.batch_expectation(archive, 1, first)
    assert inc.execute_batch(None, 6)["status"] == "not applicable"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("batch_id", "other"),
        ("dataset", "other"),
        ("workflow_commit", "other"),
        ("workflow_run", "other"),
        ("workflow_attempt", "2"),
        ("anonymous_digest_verification", "failed"),
        ("run_coverage", {"coverage_status": "partial"}),
        ("new_payloads", 0),
        ("temporary_source_bytes_removed", False),
        ("manifest_sha256", ""),
        ("revision", ""),
    ],
)
def test_incremental_wrong_prior_proof_rejected(
    incremental_setup, field, value
):
    inc, archive, _, _, _ = incremental_setup
    proof = inc.execute_batch(None, 1)
    proof[field] = value
    with pytest.raises(RuntimeError, match="proof missing or invalid"):
        inc.batch_expectation(archive, 2, proof)
    with pytest.raises(RuntimeError, match="proof missing or invalid"):
        inc.batch_expectation(archive, 2, None)


@pytest.mark.parametrize("mode", ["empty", "too_many", "no_transport", "large"])
def test_incremental_invalid_batch_rejected(incremental_setup, mode):
    inc, archive, _, _, _ = incremental_setup
    files = archive["batches"][0]["files"]
    if mode == "empty":
        files.clear()
    elif mode == "too_many":
        files *= 21
    elif mode == "no_transport":
        files[0].pop("draft_transport")
    else:
        files[0]["bytes"] = 64 * 1024**2
        files *= 2
    with pytest.raises(ValueError, match="incremental profile"):
        inc.batch_expectation(archive, 1, None)
    with pytest.raises(ValueError, match="outside committed"):
        inc.batch_expectation(archive, 0, None)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("new_payloads", 0),
        ("anonymous_digest_verification", "failed"),
        ("run_coverage", {"coverage_status": "partial"}),
        ("manifest_sha256", ""),
    ],
)
def test_incremental_failed_batch_cannot_cleanup(
    incremental_setup, field, value
):
    inc, _, _, result, _ = incremental_setup
    result[field] = value
    with pytest.raises(RuntimeError, match="exact cohort"):
        inc.execute_batch(None, 1)
    assert not inc.CHECKPOINTS.exists()


def test_incremental_authority_destination_and_cache_guard(
    incremental_setup, monkeypatch
):
    inc, _, path, _, mock = incremental_setup
    contract = json.loads(path.read_text())
    contract["external_publication_authorized"] = False
    path.write_text(json.dumps(contract))
    with pytest.raises(PermissionError, match="not authorized"):
        inc.execute_batch(None, 1)
    contract["external_publication_authorized"] = True
    contract["archives"]["mbs"]["dataset"] = "other"
    path.write_text(json.dumps(contract))
    with pytest.raises(ValueError, match="destination differs"):
        inc.execute_batch(None, 1)
    contract["archives"]["mbs"]["dataset"] = (
        "edithatogo/australian-mbs-utilisation-archive"
    )
    path.write_text(json.dumps(contract))
    monkeypatch.setenv("HF_HOME", "/outside-owned-cache")
    with pytest.raises(ValueError, match="cache differs"):
        inc.execute_batch(None, 1)
    assert not mock.called


@pytest.mark.parametrize(("index", "applied"), [(1, "true"), (6, "false")])
def test_incremental_main_outputs(
    incremental_setup, monkeypatch, tmp_path, index, applied
):
    inc, _, _, _, _ = incremental_setup
    output = tmp_path / "output"
    monkeypatch.setenv("PUBLIC_BATCH_INDEX", str(index))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(inc.importlib, "import_module", lambda _name: None)
    inc.main()
    assert output.read_text() == "applied=" + applied + "\n"
    monkeypatch.setenv("PUBLIC_BATCH_INDEX", "7")
    with pytest.raises(ValueError, match="fixed workflow"):
        inc.main()
    monkeypatch.delenv("GITHUB_ACTIONS")
    with pytest.raises(PermissionError, match="Actions main"):
        inc.main()
    with pytest.raises(PermissionError, match="Actions main"):
        inc.execute_batch(None, 1)


@pytest.mark.parametrize(
    "case",
    ["missing_assets", "invalid_json", "missing_location", "invalid_location"],
)
def test_draft_malformed_metadata_and_redirect_are_withheld(
    draft_transport, monkeypatch, case
):
    t, _, item, release, _, _, settings = draft_transport
    if case == "missing_assets":
        release.pop("assets")
    elif case == "invalid_json":
        monkeypatch.setattr(
            t.json,
            "loads",
            Mock(side_effect=json.JSONDecodeError("invalid", "synthetic", 0)),
        )
    elif case == "missing_location":
        settings["missing_location"] = True
    else:
        settings["host"] = "[invalid"
    expected = ValueError if case == "invalid_location" else RuntimeError
    with pytest.raises(expected) as error:
        t.read_draft_payload(item)
    assert "token=" not in str(error.value)
    assert error.value.__suppress_context__


def test_incremental_failure_diagnostic_is_not_success(incremental_setup):
    inc, _, _, _, mock = incremental_setup
    mock.side_effect = RuntimeError("synthetic transport failure")
    with pytest.raises(RuntimeError, match="transport failure"):
        inc.execute_batch(None, 1)
    failure = json.loads((inc.CHECKPOINTS / "failure-1.json").read_text())
    assert failure["error_type"] == "RuntimeError"
    assert "not inferred" in failure["hf_mutation"]
    assert not (inc.CHECKPOINTS / "verification-1.json").exists()


def test_incremental_pbs_matches_configured_workflow_cache(
    incremental_setup, monkeypatch, tmp_path
):
    inc, archive, path, result, mock = incremental_setup
    archive["dataset"] = "edithatogo/australian-pbs-utilisation-archive"
    for batch in archive["batches"]:
        batch["id"] = batch["id"].replace("mbs", "pbs")
    path.write_text(
        json.dumps({
            "external_publication_authorized": True,
            "archives": {"pbs": archive},
        })
    )
    result["dataset"] = archive["dataset"]
    monkeypatch.setenv("PUBLIC_ARCHIVE_DESTINATION", "pbs")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "build/pbs-hf-home"))
    receipt = inc.execute_batch(None, 1)
    assert receipt["batch_id"] == "pbs-01"
    assert mock.called
    assert (tmp_path / "build/pbs-utilisation-harvest-receipt.json").exists()


@pytest.mark.parametrize("destination", ["pbs", "mbs"])
def test_draft_access_role_is_manual_only(destination):
    workflow = yaml.safe_load(
        (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / f"australian-{destination}-utilisation-harvest.yml"
        ).read_text()
    )
    routine = workflow["jobs"]["harvest"]
    incremental_job = workflow["jobs"]["incremental"]
    assert routine["permissions"]["contents"] == "read"
    assert routine["if"] == "inputs.incremental_public != true"
    assert (
        incremental_job["if"]
        == "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && inputs.incremental_public == true"
    )
    assert incremental_job["permissions"] == {"contents": "write"}
    assert incremental_job["environment"] == "australian-hf-publication"
    assert incremental_job["steps"] is routine["steps"]
    assert incremental_job["env"] is routine["env"]
    assert workflow["permissions"] == {}


def test_draft_http_status_diagnostic_contains_no_url():
    with pytest.raises(ValueError, match="HTTP 404") as error:
        transport.bounded_body(httpx.Response(404), 100)
    assert "https:" not in str(error.value)


@pytest.mark.usefixtures("_hosted")
@pytest.mark.parametrize("destination", ["pbs", "mbs"])
def test_historical_atc2_uses_fixed_pbs_contract(
    monkeypatch, tmp_path, destination
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HISTORICAL_ATC2", "1")
    monkeypatch.setenv("PUBLIC_ARCHIVE_DESTINATION", destination)
    path = Path("quality/qualifications/historical-atc2-public-20261106.json")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "external_publication_authorized": True,
            "archives": {
                "pbs": {
                    "dataset": "edithatogo/australian-pbs-utilisation-archive",
                    "files": ["exact-reviewed-cohort"],
                }
            },
        }),
        encoding="utf-8",
    )
    Path("build").mkdir()
    publish = Mock(return_value={"anonymous_digest_verification": "passed"})
    monkeypatch.setattr(subject, "publish", publish)
    monkeypatch.setattr(subject.importlib, "import_module", lambda _: None)
    if destination == "mbs":
        with pytest.raises(ValueError, match="restricted to PBS"):
            subject.main()
        publish.assert_not_called()
    else:
        subject.main()
        assert publish.call_args.args[1]["files"] == ["exact-reviewed-cohort"]
        assert Path("build/pbs-utilisation-harvest-receipt.json").is_file()
