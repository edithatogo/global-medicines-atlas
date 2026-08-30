"""Synthetic hosted-only retrieval guards for the pinned public PBS corpus."""

import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import httpx
import pytest
from scripts import qualify_historical_pbs_public as cli
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_silver import XML

from global_medicines_atlas import pbs_hosted_qualification as hosted

SHA = "a" * 40


@pytest.fixture
def synthetic(monkeypatch: pytest.MonkeyPatch):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
    }.items():
        monkeypatch.setenv(key, value)
    archive = _zip([(PATH, XML)])
    receipt = _receipt(archive, SOURCE).model_dump_json().encode()

    def pin(path, data):
        return hosted.PinnedFile(
            path, hashlib.sha256(data).hexdigest(), len(data)
        )

    pins = {
        "ARCHIVE": pin("raw/fixture.zip", archive),
        "RECEIPT": pin("bronze/source-receipt.json", receipt),
        "MEMBER": pin("bronze/member.xml", XML),
    }
    manifest = json.dumps({
        "source_id": SOURCE,
        "destination_dataset": hosted.DATASET,
        "archive": {
            "path": pins["ARCHIVE"].path,
            "sha256": pins["ARCHIVE"].sha256,
            "size_bytes": len(archive),
        },
        "member": {
            "path": pins["MEMBER"].path,
            "source_path": PATH,
            "sha256": pins["MEMBER"].sha256,
            "size_bytes": len(XML),
        },
        "source_receipt": {
            "path": pins["RECEIPT"].path,
            "sha256": pins["RECEIPT"].sha256,
        },
    }).encode()
    pins["MANIFEST"] = pin("manifest.json", manifest)
    for key, value in pins.items():
        monkeypatch.setattr(hosted, key, value)
    monkeypatch.setattr(hosted, "MEMBER_SOURCE_PATH", PATH)
    info = {
        "id": hosted.DATASET,
        "sha": hosted.REVISION,
        "private": False,
        "gated": False,
    }
    responses = {
        hosted.INFO_URL: json.dumps(info).encode(),
        hosted.file_url(pins["ARCHIVE"]): archive,
        hosted.file_url(pins["RECEIPT"]): receipt,
        hosted.file_url(pins["MANIFEST"]): manifest,
    }
    calls = []

    def handler(request):
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        calls.append(str(request.url))
        value = responses[str(request.url)]
        if isinstance(value, httpx.Response):
            return value
        return httpx.Response(200, content=value)

    return responses, calls, httpx.MockTransport(handler)


def test_pinned_public_inputs_and_aggregate_report(synthetic) -> None:
    _, calls, transport = synthetic
    report = hosted.run_hosted_qualification(SHA, transport=transport)
    assert report["status"] == "passed"
    assert report["revision"] == hosted.REVISION
    assert report["qualification"]["date_profile"] == "not-selected"
    assert report["qualification"]["source_id"] == SOURCE
    assert " Before " not in json.dumps(report)
    assert calls.count(hosted.INFO_URL) == 2
    assert hosted.file_url(hosted.MEMBER) not in calls
    assert report["member_retrieval"] == "extracted-from-verified-archive"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("GITHUB_ACTIONS", "false"),
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_REF", "refs/heads/preview"),
        ("GITHUB_SHA", "b" * 40),
        ("GITHUB_RUN_ID", "bad"),
    ],
)
def test_local_or_wrong_context_rejected_before_http(
    synthetic, monkeypatch, key, value
) -> None:
    _, calls, transport = synthetic
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="context/validation"):
        hosted.run_hosted_qualification(SHA, transport=transport)
    assert calls == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("private", True),
        ("gated", "auto"),
        ("sha", "main"),
        ("id", "other/data"),
    ],
)
def test_nonpublic_or_mutable_identity_rejected(synthetic, key, value) -> None:
    responses, _, transport = synthetic
    info = json.loads(responses[hosted.INFO_URL])
    info[key] = value
    responses[hosted.INFO_URL] = json.dumps(info).encode()
    with pytest.raises(ValueError, match="public-before/validation"):
        hosted.run_hosted_qualification(SHA, transport=transport)


@pytest.mark.parametrize(
    "case",
    [
        "digest",
        "oversize",
        "http",
        "encoding",
        "redirect",
        "credentials",
        "mutable",
    ],
)
def test_bad_retrieval_rejected(synthetic, case) -> None:
    responses, calls, transport = synthetic
    url = hosted.file_url(hosted.ARCHIVE)
    if case == "digest":
        responses[url] = b"x" * hosted.ARCHIVE.byte_count
    elif case == "oversize":
        responses[url] += b"x"
    elif case == "http":
        responses[url] = httpx.Response(403)
    elif case == "encoding":
        responses[url] = httpx.Response(
            200, headers={"Content-Encoding": "unsupported"}
        )
    elif case == "redirect":
        responses[url] = httpx.Response(
            302, headers={"Location": "https://example.com/raw"}
        )
    elif case == "credentials":
        responses[url] = httpx.Response(
            302, headers={"Location": "https://user:secret@huggingface.co/raw"}
        )
    else:
        responses[url] = httpx.Response(
            302, headers={"Location": url.replace(hosted.REVISION, "main")}
        )
    categories = {
        "digest": "pin-mismatch",
        "oversize": "byte-limit",
        "http": "http-status",
        "encoding": "encoding",
        "redirect": "destination-policy",
        "credentials": "destination-policy",
        "mutable": "redirect",
    }
    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(SHA, transport=transport)
    assert caught.value.stage == "archive-read"
    assert caught.value.category == categories[case]
    assert caught.value.retry_event is None
    assert calls.count(url) == 1


def test_allowed_cdn_redirect_is_anonymous(synthetic) -> None:
    responses, _, transport = synthetic
    url = hosted.file_url(hosted.ARCHIVE)
    destination = "https://us.aws.cdn.hf.co/fixture?signature=synthetic"
    responses[destination] = responses[url]
    responses[url] = httpx.Response(
        302,
        headers={"Location": destination, "Set-Cookie": "secret=not-forwarded"},
    )
    assert (
        hosted.run_hosted_qualification(SHA, transport=transport)["status"]
        == "passed"
    )


@pytest.mark.parametrize("case", ["missing", "loop", "cache", "query"])
def test_redirect_contracts(synthetic, case) -> None:
    responses, _, transport = synthetic
    url = hosted.file_url(hosted.MANIFEST)
    if case == "missing":
        responses[url] = httpx.Response(302)
    elif case == "loop":
        responses[url] = httpx.Response(302, headers={"Location": url})
    elif case == "query":
        responses[url] = httpx.Response(
            302, headers={"Location": url + "?token=synthetic"}
        )
    else:
        target = (
            url.replace("/datasets/", "/api/resolve-cache/datasets/").replace(
                "/resolve/", "/"
            )
            + "?download=false"
        )
        responses[target] = responses[url]
        responses[url] = httpx.Response(302, headers={"Location": target})
        assert (
            hosted.run_hosted_qualification(SHA, transport=transport)["status"]
            == "passed"
        )
        return
    with pytest.raises(ValueError, match=r"redirect|destination"):
        hosted.run_hosted_qualification(SHA, transport=transport)


def test_deadline_rejected_before_http(synthetic, monkeypatch) -> None:
    _, calls, transport = synthetic
    moments = iter([0, 301])
    original_clock = time.monotonic
    monkeypatch.setattr(
        hosted, "time", SimpleNamespace(monotonic=lambda: next(moments))
    )
    assert time.monotonic is original_clock
    with pytest.raises(ValueError, match="public-before/timeout"):
        hosted.run_hosted_qualification(SHA, transport=transport)
    assert not calls


def test_non_object_metadata(synthetic) -> None:
    responses, _, transport = synthetic
    responses[hosted.INFO_URL] = b"[]"
    with pytest.raises(ValueError, match="public-before/structure"):
        hosted.run_hosted_qualification(SHA, transport=transport)


def test_http_errors_do_not_expose_urls(synthetic) -> None:
    assert not synthetic[1]

    def fail(request):
        raise httpx.ConnectError("synthetic-secret-url", request=request)

    with pytest.raises(ValueError, match="public-before/transport") as error:
        hosted.run_hosted_qualification(
            SHA, transport=httpx.MockTransport(fail)
        )
    assert "synthetic-secret-url" not in str(error.value)


@pytest.mark.parametrize("case", ["path", "source", "member"])
def test_revalidated_manifest_and_member_pins(
    synthetic, monkeypatch, case
) -> None:
    responses, _, transport = synthetic
    url = hosted.file_url(hosted.MANIFEST)
    manifest = json.loads(responses[url])
    if case == "path":
        manifest["archive"]["path"] = "wrong"
    elif case == "source":
        manifest["source_id"] = "au-pbs"
    else:
        manifest["member"]["source_path"] = "wrong.xml"
        monkeypatch.setattr(hosted, "MEMBER_SOURCE_PATH", "wrong.xml")
    data = json.dumps(manifest).encode()
    responses[url] = data
    monkeypatch.setattr(
        hosted,
        "MANIFEST",
        hosted.PinnedFile(
            "manifest.json", hashlib.sha256(data).hexdigest(), len(data)
        ),
    )
    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(SHA, transport=transport)
    assert caught.value.stage == (
        "member-extraction" if case == "member" else "manifest-validation"
    )
    assert caught.value.category == "pin-mismatch"


def test_aggregate_report_bound(synthetic, monkeypatch) -> None:
    _, _, transport = synthetic
    monkeypatch.setattr(hosted, "MAX_REPORT_BYTES", 1)
    with pytest.raises(ValueError, match="report/byte-limit"):
        hosted.run_hosted_qualification(SHA, transport=transport)


def test_cli_failure_receipt_excludes_error_text(tmp_path, monkeypatch) -> None:
    def fail(_commit):
        raise ValueError("synthetic-sensitive-source-text")

    monkeypatch.setattr(cli, "run_hosted_qualification", fail)
    output = tmp_path / "receipt.json"
    assert cli.main(["--exact-commit", SHA, "--output", str(output)]) == 1
    raw = output.read_text()
    assert "synthetic-sensitive-source-text" not in raw
    envelope = json.loads(raw)
    assert envelope["report"]["status"] == "failed"
    canonical = json.dumps(
        envelope["report"], sort_keys=True, separators=(",", ":")
    ).encode()
    assert envelope["report_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert (
        cli.main([
            "--exact-commit",
            SHA,
            "--output",
            str(output),
            "--failure-only",
        ])
        == 0
    )


def test_cli_success_and_size_bound(synthetic, tmp_path, monkeypatch) -> None:
    _, _, transport = synthetic
    monkeypatch.setattr(
        cli,
        "run_hosted_qualification",
        lambda commit: hosted.run_hosted_qualification(
            commit, transport=transport
        ),
    )
    output = tmp_path / "receipt.json"
    assert cli.main(["--exact-commit", SHA, "--output", str(output)]) == 0
    monkeypatch.setattr(cli, "MAX_REPORT_BYTES", 1)
    assert cli.main(["--exact-commit", SHA, "--output", str(output)]) == 1
    assert json.loads(output.read_text())["report"]["status"] == "failed"


def test_workflow_has_durable_receipt_and_no_dataset_write() -> None:
    workflow = Path(
        ".github/workflows/pbs-historical-qualification.yml"
    ).read_text(encoding="utf-8")
    assert "gh issue comment 341" in workflow
    assert "if: always()" in workflow
    assert "--failure-only" in workflow
    assert "persist-credentials: false" in workflow
    assert "HF_TOKEN" not in workflow
    assert "upload_folder" not in workflow
    assert "exact_commit" in workflow


def test_context_failure_has_safe_diagnostics(synthetic, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REF", "refs/heads/not-main")
    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(SHA, transport=synthetic[2])
    report = hosted.failure_report(caught.value)
    assert report["failure_stage"] == "context"
    assert report["failure_category"] == "validation"
    assert not synthetic[1]


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (httpx.ConnectError("secret-url"), "transport-connect"),
        (httpx.ReadTimeout("secret-url"), "timeout"),
        (ValueError("secret-value"), "validation"),
        (KeyError("secret-field"), "structure"),
        (TypeError("secret-type"), "structure"),
        (RuntimeError("secret-runtime"), "unexpected"),
    ],
)
def test_stage_category_and_cli_redaction(
    synthetic, monkeypatch, tmp_path, error, category
) -> None:
    def fail(*_args):
        raise error

    monkeypatch.setattr(hosted, "_public", fail)
    monkeypatch.setattr(
        cli,
        "run_hosted_qualification",
        lambda commit: hosted.run_hosted_qualification(
            commit, transport=synthetic[2]
        ),
    )
    output = tmp_path / "diagnostic.json"
    assert cli.main(["--exact-commit", SHA, "--output", str(output)]) == 1
    raw = output.read_text()
    assert "secret" not in raw
    report = json.loads(raw)["report"]
    assert report["failure_stage"] == "public-before"
    assert report["failure_category"] == category


@pytest.mark.parametrize(
    ("target", "stage"),
    [
        ("AcquisitionPolicy", "transport-setup"),
        ("read_pbs_v3_member", "member-extraction"),
        ("build_pbs_xml_member_binding", "member-binding"),
        ("qualify_pbs_historical_projections", "projection-qualification"),
    ],
)
def test_processing_stage_is_retained(
    synthetic, monkeypatch, target, stage
) -> None:
    def fail(*_args, **_kwargs):
        raise ValueError("synthetic-source-secret")

    monkeypatch.setattr(hosted, target, fail)
    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(SHA, transport=synthetic[2])
    assert hosted.failure_report(caught.value)["failure_stage"] == stage
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize(
    ("pin_name", "stage"),
    [
        ("MANIFEST", "manifest-read"),
        ("RECEIPT", "receipt-read"),
        ("ARCHIVE", "archive-read"),
    ],
)
def test_file_failure_stage(synthetic, pin_name, stage) -> None:
    responses, _, transport = synthetic
    responses[hosted.file_url(getattr(hosted, pin_name))] = b""
    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(SHA, transport=transport)
    report = hosted.failure_report(caught.value)
    assert report["failure_stage"] == stage
    assert report["failure_category"] == "pin-mismatch"


def test_second_public_check_has_distinct_stage(synthetic, monkeypatch) -> None:
    count = 0
    original = hosted._public

    def check(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("secret")
        return original(*args)

    monkeypatch.setattr(hosted, "_public", check)
    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(SHA, transport=synthetic[2])
    assert caught.value.stage == "public-after"


def test_receipt_validation_stage(synthetic, monkeypatch) -> None:
    def fail(_data):
        raise ValueError("secret-receipt")

    monkeypatch.setattr(
        hosted, "SourceReceipt", SimpleNamespace(model_validate_json=fail)
    )
    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(SHA, transport=synthetic[2])
    assert caught.value.stage == "receipt-validation"


def test_failure_codes_revalidated_and_unknown_errors_not_inspected() -> None:
    error = hosted.QualificationError("secret-stage", "secret-category")
    assert "secret" not in str(error)
    error.stage = "secret-mutated-stage"
    error.category = "secret-mutated-category"
    report = hosted.failure_report(error)
    assert report["failure_stage"] == "unavailable"
    assert report["failure_category"] == "unexpected"
    assert "secret" not in json.dumps(report)

    class SensitiveError(Exception):
        def __str__(self) -> str:
            raise AssertionError("Do not inspect exception text")

    report = hosted.failure_report(SensitiveError())
    assert report["failure_stage"] == "unavailable"
    assert report["failure_category"] == "unavailable"


def test_dns_policy_failure_category(synthetic) -> None:
    assert not synthetic[1]

    def fail(_request):
        raise hosted.DestinationPolicyError("secret-code", "secret-dns-detail")

    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(
            SHA, transport=httpx.MockTransport(fail)
        )
    assert caught.value.category == "destination-policy"
    assert caught.value.stage == "public-before"


@pytest.mark.parametrize("pin_name", ["MANIFEST", "RECEIPT"])
@pytest.mark.parametrize("empty_assignment", [False, True])
def test_observed_hub_cache_redirect(
    synthetic, pin_name, empty_assignment
) -> None:
    responses, _, transport = synthetic
    pin = getattr(hosted, pin_name)
    url = hosted.file_url(pin)
    original_path = url.split("huggingface.co", 1)[1]
    target = (
        f"https://huggingface.co/api/resolve-cache/datasets/{hosted.DATASET}/"
        f"{hosted.REVISION}/{quote(pin.path, safe='')}"
        f"?{quote(original_path, safe='')}{'=' if empty_assignment else ''}&etag=synthetic"
    )
    responses[target] = responses[url]
    responses[url] = httpx.Response(302, headers={"Location": target})
    assert (
        hosted.run_hosted_qualification(SHA, transport=transport)["status"]
        == "passed"
    )


@pytest.mark.parametrize(
    "case",
    [
        "unrelated",
        "mutable",
        "double-path",
        "double-query",
        "traversal",
        "unknown",
        "duplicate",
        "bare-on-initial",
        "nonempty-original",
    ],
)
def test_cache_redirect_remains_exact(synthetic, case) -> None:
    responses, _, transport = synthetic
    pin = hosted.RECEIPT
    url = hosted.file_url(pin)
    original_path = url.split("huggingface.co", 1)[1]
    path = (
        f"/api/resolve-cache/datasets/{hosted.DATASET}/{hosted.REVISION}/"
        f"{quote(pin.path, safe='')}"
    )
    query = quote(original_path, safe="")
    if case == "unrelated":
        query = quote(original_path + "/other", safe="")
    elif case == "mutable":
        path = path.replace(hosted.REVISION, "main")
    elif case == "double-path":
        path = path.replace("%2F", "%252F")
    elif case == "double-query":
        query = quote(query, safe="")
    elif case == "traversal":
        path = path.replace(quote(pin.path, safe=""), "%2E%2E%2Fother")
    elif case == "unknown":
        query += "&token=secret"
    elif case == "duplicate":
        query += "&" + query
    elif case == "nonempty-original":
        query += "=other"
    else:
        path = original_path
    responses[url] = httpx.Response(
        302, headers={"Location": f"https://huggingface.co{path}?{query}"}
    )
    with pytest.raises(
        hosted.QualificationError, match="receipt-read/redirect"
    ):
        hosted.run_hosted_qualification(SHA, transport=transport)


@pytest.mark.parametrize(
    ("error_type", "expected_category"),
    [
        (httpx.ConnectError, "transport-connect"),
        (httpx.ReadError, "transport-read"),
        (httpx.RemoteProtocolError, "transport-remote-protocol"),
    ],
)
def test_one_transient_receipt_retry_is_recorded(
    synthetic, monkeypatch, error_type, expected_category
) -> None:
    _, _, delegate = synthetic
    attempts = 0
    sleeps = []
    monkeypatch.setattr(
        hosted,
        "time",
        SimpleNamespace(monotonic=time.monotonic, sleep=sleeps.append),
    )

    def handler(request):
        nonlocal attempts
        if str(request.url) == hosted.file_url(hosted.RECEIPT):
            attempts += 1
            if attempts == 1:
                raise error_type("secret-source-url")
        return delegate.handle_request(request)

    report = hosted.run_hosted_qualification(
        SHA, transport=httpx.MockTransport(handler)
    )
    assert report["status"] == "passed"
    assert attempts == 2
    assert sleeps == [1]
    assert report["transport_retry"]["stage"] == "receipt-read"
    assert report["transport_retry"]["category"] == expected_category
    assert "secret" not in json.dumps(report)


def test_retry_budget_is_global_and_failure_retains_first_event(
    synthetic, monkeypatch
) -> None:
    _, _, delegate = synthetic
    counts = {}
    monkeypatch.setattr(
        hosted,
        "time",
        SimpleNamespace(monotonic=time.monotonic, sleep=lambda _seconds: None),
    )

    def handler(request):
        url = str(request.url)
        counts[url] = counts.get(url, 0) + 1
        if (
            url
            in {
                hosted.file_url(hosted.MANIFEST),
                hosted.file_url(hosted.RECEIPT),
            }
            and counts[url] == 1
        ):
            raise httpx.ReadError("secret-response")
        return delegate.handle_request(request)

    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(
            SHA, transport=httpx.MockTransport(handler)
        )
    report = hosted.failure_report(caught.value)
    assert report["failure_stage"] == "receipt-read"
    assert report["failure_category"] == "transport-read"
    assert report["transport_retry"] == {
        "stage": "manifest-read",
        "category": "transport-read",
    }
    assert counts[hosted.file_url(hosted.RECEIPT)] == 1
    assert "secret" not in json.dumps(report)


@pytest.mark.parametrize(
    ("error_type", "category"),
    [
        (httpx.ConnectTimeout, "timeout"),
        (httpx.ReadTimeout, "timeout"),
        (httpx.WriteTimeout, "timeout"),
        (httpx.PoolTimeout, "timeout"),
        (httpx.DecodingError, "transport-decoding"),
        (httpx.LocalProtocolError, "transport-local-protocol"),
        (httpx.WriteError, "transport"),
    ],
)
def test_nontransient_transport_failures_are_not_retried(
    synthetic, error_type, category
) -> None:
    _, _, delegate = synthetic
    attempts = 0

    def handler(request):
        nonlocal attempts
        if str(request.url) == hosted.file_url(hosted.RECEIPT):
            attempts += 1
            raise error_type("secret")
        return delegate.handle_request(request)

    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_qualification(
            SHA, transport=httpx.MockTransport(handler)
        )
    assert attempts == 1
    report = hosted.failure_report(caught.value)
    assert report["failure_category"] == category
    assert report["transport_retry"] is None


def test_partial_response_closed_discarded_and_restart_guarded(
    synthetic, monkeypatch
) -> None:
    responses, _, delegate = synthetic
    url = hosted.file_url(hosted.MANIFEST)
    manifest = json.loads(responses[url])
    manifest["synthetic_padding"] = "x" * 70_000
    payload = json.dumps(manifest).encode()
    responses[url] = payload
    monkeypatch.setattr(
        hosted,
        "MANIFEST",
        hosted.PinnedFile(
            "manifest.json", hashlib.sha256(payload).hexdigest(), len(payload)
        ),
    )
    target = "https://us.aws.cdn.hf.co/fixture?signature=synthetic"
    responses[target] = responses[url]
    responses[url] = httpx.Response(302, headers={"Location": target})
    calls = []
    monkeypatch.setattr(
        hosted,
        "time",
        SimpleNamespace(monotonic=time.monotonic, sleep=lambda _seconds: None),
    )

    class Partial(httpx.SyncByteStream):
        closed = False

        def __iter__(self):
            yield b"x" * (64 * 1024)
            raise httpx.ReadError("secret-stream-error")

        def close(self):
            self.closed = True

    partial = Partial()

    def handler(request):
        calls.append(str(request.url))
        if str(request.url) == target and calls.count(target) == 1:
            return httpx.Response(200, stream=partial)
        if str(request.url) == url and calls.count(url) == 2:
            assert partial.closed
        return delegate.handle_request(request)

    report = hosted.run_hosted_qualification(
        SHA, transport=httpx.MockTransport(handler)
    )
    assert report["status"] == "passed"
    assert calls.count(url) == calls.count(target) == 2
    assert report["transport_retry"] == {
        "stage": "manifest-read",
        "category": "transport-read",
    }


@pytest.mark.parametrize("oversleep", [False, True])
def test_retry_never_resets_deadline(monkeypatch, oversleep) -> None:
    clock = 299.5 if not oversleep else 298
    calls = 0
    sleeps = []

    def fail():
        nonlocal calls
        calls += 1
        raise httpx.ReadError("secret")

    def sleep(seconds):
        nonlocal clock
        sleeps.append(seconds)
        clock = 301

    monkeypatch.setattr(
        hosted, "time", SimpleNamespace(monotonic=lambda: clock, sleep=sleep)
    )
    budget = hosted._RetryBudget()
    with pytest.raises(hosted.QualificationError, match="receipt-read/timeout"):
        hosted._fetch("receipt-read", budget, 300, fail)
    assert calls == 1
    assert sleeps == ([1] if oversleep else [])


def test_retry_record_is_allowlisted() -> None:
    error = hosted.QualificationError("receipt-read", "transport-read")
    error.retry_event = ("secret-stage", "secret-category")
    report = hosted.failure_report(error)
    assert report["transport_retry"] is None
    assert "secret" not in json.dumps(report)
