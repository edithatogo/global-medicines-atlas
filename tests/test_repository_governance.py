# ruff: file-ignore[subprocess-without-shell-equals-true]

from __future__ import annotations

import configparser
import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tomllib
from argparse import Namespace
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import build_dependency_snapshot as dependency_snapshot
from scripts import deploy_hf_space

from global_medicines_atlas import hosted_service as hosted
from global_medicines_atlas import orange_book_events as source
from global_medicines_atlas.hosted_service import DATASET, PAYLOAD_SHA, REVISION
from global_medicines_atlas.submission_events import project_submission_events

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
CONDUCTOR_PLUGIN = ".agents/plugins/conductor"
CONDUCTOR_PLUGIN_URL = "https://github.com/gemini-cli-extensions/conductor.git"
CONDUCTOR_SKILLS = (
    "conductor-setup",
    "conductor-new-track",
    "conductor-implement",
    "conductor-status",
    "conductor-review",
    "conductor-revert",
)


def test_space_candidate_cannot_upload_source_or_private_members(tmp_path):
    for name in [
        "Dockerfile",
        "LICENSE",
        "cacert.pem",
        "requirements.txt",
        "global_medicines_atlas-1.whl",
    ]:
        (tmp_path / name).write_bytes(b"synthetic-code")
    (tmp_path / "README.md").write_text(deploy_hf_space.OWNER_MARKER)
    assert len(deploy_hf_space.candidate_files(tmp_path)) == 6
    (tmp_path / "source.duckdb").write_bytes(b"forbidden")
    with pytest.raises(ValueError, match=r"hosted main|exact main|candidate"):
        deploy_hf_space.candidate_files(tmp_path)


def test_space_workflow_has_no_pr_mutation_or_unpinned_runtime():
    document = yaml.safe_load(
        (ROOT / ".github/workflows/hf-space-service.yml").read_text()
    )
    assert "deploy" not in document["jobs"]
    assert "HF_TOKEN" not in json.dumps(document)
    verify = document["jobs"]["verify_native"]
    assert "workflow_dispatch" in verify["if"]
    assert "refs/heads/main" in verify["if"]
    assert verify["permissions"] == {"contents": "read"}
    candidate = json.dumps(document["jobs"]["candidate"])
    assert "secrets." not in candidate
    assert "docker restart" in candidate
    assert "3.15.1" in candidate


def test_render_blueprint_is_free_single_service_without_a_paid_fallback():
    document = yaml.safe_load((ROOT / "render.yaml").read_text())
    assert set(document) == {"services"}
    assert len(document["services"]) == 1
    service = document["services"][0]
    assert service["type"] == "web"
    assert service["runtime"] == "python"
    assert service["plan"] == "free"
    assert service["autoDeployTrigger"] == "off"
    assert "disk" not in service
    assert "scaling" not in service
    environment = {item["key"]: item for item in service["envVars"]}
    assert environment["PYTHON_VERSION"]["value"] == "3.15.1"
    assert environment["UV_VERSION"]["value"] == "0.13.6"
    assert environment["GMA_CURSOR_SECRET"] == {
        "key": "GMA_CURSOR_SECRET",
        "generateValue": True,
    }


@pytest.mark.parametrize(
    "event", ["local", "pull_request", "workflow_dispatch"]
)
def test_retired_docker_deployment_never_loads_a_credential(
    tmp_path, monkeypatch, event
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)

    def reject(*_args, **_kwargs):
        raise AssertionError("must not contact the retired provider")

    monkeypatch.setattr(deploy_hf_space, "import_module", reject)
    receipt = {}
    deploy_hf_space.deploy(
        "a" * 40, tmp_path, receipt, tmp_path / "journal.json"
    )
    assert receipt["phase"] == "free_only_policy"
    assert receipt["result"] == "blocked"


def test_hosted_verification_waits_for_the_expected_application(monkeypatch):
    monkeypatch.setattr(
        deploy_hf_space, "verify_approval_events", lambda *_args: None
    )
    monkeypatch.setattr(
        deploy_hf_space, "verify_submission_events", lambda *_args: None
    )
    monkeypatch.setattr(
        deploy_hf_space, "verify_reviewed_product_actions", lambda *_args: None
    )
    exact = "c" * 40
    pending = [
        {"application_commit": "old"},
        {
            "application_commit": exact,
            "python_version": "3.15.1",
            "dataset": DATASET,
            "revision": REVISION,
            "source_sha256": PAYLOAD_SHA,
        },
    ]
    monkeypatch.setattr(
        deploy_hf_space, "ready_metadata", lambda _: pending.pop(0)
    )
    monkeypatch.setattr(deploy_hf_space.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        deploy_hf_space.httpx,
        "get",
        lambda *_a, **_k: type(
            "Response", (), {"raise_for_status": lambda _: None}
        )(),
    )
    result = deploy_hf_space.http_metadata("http://127.0.0.1:7860", exact)
    assert result["application_commit"] == exact
    assert not pending
    monkeypatch.setattr(deploy_hf_space, "ready_metadata", lambda _: result)
    assert (
        deploy_hf_space.http_metadata(
            "https://global-medicines-atlas-test.onrender.com", exact
        )
        == result
    )
    with pytest.raises(ValueError, match="unapproved"):
        deploy_hf_space.http_metadata("https://unrelated.invalid", exact)


def test_single_canonical_renovate_configuration() -> None:
    assert not (ROOT / "renovate.json5").exists()
    config = json.loads((ROOT / "renovate.json").read_text(encoding="utf-8"))
    assert "github>edithatogo/renovate-config" in config["extends"]
    enabled_managers = set(config["enabledManagers"])
    assert {
        "pep621",
        "pixi",
        "github-actions",
        "custom.regex",
    } <= enabled_managers
    assert "uv" not in enabled_managers
    assert any(
        "pep621" in rule.get("matchManagers", [])
        for rule in config["packageRules"]
    )
    assert "pep621" in enabled_managers, (
        "Renovate's pep621 manager owns pyproject.toml and uv.lock"
    )
    assert config["minimumReleaseAge"] == "7 days"
    assert config["automerge"] is False
    github_rules = [
        rule
        for rule in config["packageRules"]
        if "github-actions" in rule.get("matchManagers", [])
    ]
    assert github_rules
    assert github_rules[0]["pinDigests"] is True


def test_required_community_health_files_exist() -> None:
    for filename in (
        "SECURITY.md",
        "CONTRIBUTING.md",
        "SUPPORT.md",
        "CODE_OF_CONDUCT.md",
        "CITATION.cff",
        "CHANGELOG.md",
        "NOTICE",
        "LICENSE",
        "DATA_LICENSE.md",
        "docs/governance/licensing-decision.md",
        "docs/data-sources/SOURCE_RIGHTS.md",
    ):
        assert (ROOT / filename).is_file()
    assert "Apache License" in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_licence_decision_is_explicit_and_data_rights_remain_bounded() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    follow_ups = (ROOT / ".github/EXTERNAL_FOLLOW_UPS.md").read_text(
        encoding="utf-8"
    )
    source_rights = (ROOT / "docs/data-sources/SOURCE_RIGHTS.md").read_text(
        encoding="utf-8"
    )

    data_licence = (ROOT / "DATA_LICENSE.md").read_text(encoding="utf-8")
    decision = (ROOT / "docs/governance/licensing-decision.md").read_text(
        encoding="utf-8"
    )

    assert '\nlicense = "Apache-2.0"' in pyproject
    assert "\nlicense: Apache-2.0" in citation
    assert '\nversion: "1.0.0"' in citation
    assert '\ndate-released: "2026-11-14"' in citation
    assert 'doi: "10.5281/zenodo.21734811"' not in citation
    assert "third-party" in data_licence.lower()
    assert "cc-by-4.0" in decision.lower()
    assert "licence detection" in follow_ups.lower()
    assert "does not grant" in source_rights.lower()


def test_workflow_actions_are_immutable_and_permissions_are_explicit() -> None:
    yaml = pytest.importorskip("yaml")
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        assert "permissions" in document, workflow
        for line in workflow.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith("- uses:"):
                continue
            revision = stripped.split("@", 1)[1].split()[0]
            assert FULL_SHA.fullmatch(revision), f"{workflow}: {revision}"


def test_issue_forms_and_labels_are_machine_readable() -> None:
    yaml = pytest.importorskip("yaml")
    for filename in (
        "source-onboarding.yml",
        "data-incident.yml",
        "config.yml",
    ):
        payload = yaml.safe_load(
            (ROOT / ".github/ISSUE_TEMPLATE" / filename).read_text(
                encoding="utf-8"
            )
        )
        assert isinstance(payload, dict)
    labels = yaml.safe_load(
        (ROOT / ".github/labels.yml").read_text(encoding="utf-8")
    )
    names = {label["name"] for label in labels}
    assert {
        "type:data-source",
        "type:data-incident",
        "status:external-gate",
    } <= names


def test_conductor_plugin_is_pinned_git_submodule() -> None:
    modules = configparser.ConfigParser()
    parsed = modules.read(ROOT / ".gitmodules")
    assert parsed, "missing .gitmodules"
    section = f'submodule "{CONDUCTOR_PLUGIN}"'
    assert modules.has_section(section)
    assert modules.get(section, "path") == CONDUCTOR_PLUGIN
    assert modules.get(section, "url") == CONDUCTOR_PLUGIN_URL
    assert modules.get(section, "branch") == "main"

    git = shutil.which("git")
    if git is None:
        pytest.skip("git is unavailable")
    recorded = subprocess.run(
        [git, "ls-tree", "HEAD", CONDUCTOR_PLUGIN],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    mode, object_type, rest = recorded.stdout.split(maxsplit=2)
    sha = rest.split("\t", 1)[0]
    assert mode == "160000"
    assert object_type == "commit"
    assert FULL_SHA.fullmatch(sha)


def test_cursor_skills_delegate_to_pinned_conductor_plugin() -> None:
    for name in CONDUCTOR_SKILLS:
        skill = ROOT / ".cursor" / "skills" / name / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        relative = f"{CONDUCTOR_PLUGIN}/skills/{name}/SKILL.md"
        assert f"name: {name}" in text
        assert relative in text
        assert "git submodule update --init --recursive" in text


def test_dependency_snapshot_covers_the_entire_lock_deterministically() -> None:
    raw = (ROOT / "uv.lock").read_bytes()
    locked = tomllib.loads(raw.decode())
    snapshot = dependency_snapshot.build_snapshot(
        raw, "a" * 40, "123", "2026-11-03T00:00:00Z"
    )
    assert snapshot == dependency_snapshot.build_snapshot(
        raw, "a" * 40, "123", "2026-11-03T00:00:00Z"
    )
    resolved = snapshot["manifests"]["uv.lock"]["resolved"]
    registry = [p for p in locked["package"] if "registry" in p["source"]]
    assert set(resolved) == {
        dependency_snapshot.package_url(p) for p in registry
    }
    assert "pkg:pypi/filelock@4.2.4" in resolved
    assert "pkg:pypi/msgpack@1.2.3" in resolved
    for name in ("lancedb", "pyiceberg", "pip-audit", "colorama"):
        assert any(key.startswith(f"pkg:pypi/{name}@") for key in resolved)
    assert all(
        set(row["dependencies"]) <= set(resolved) for row in resolved.values()
    )
    assert snapshot["job"]["correlator"] == "gma-uv-lock-main"


def test_dependency_snapshot_rejects_ambiguous_and_unsupported_identities() -> (
    None
):
    root = {
        "name": "project",
        "source": {"editable": "."},
        "dependencies": [{"name": "example"}],
    }
    first = {
        "name": "example",
        "version": "1.0",
        "source": {"registry": "https://pypi.org/simple"},
    }
    second = {**first, "version": "2.0"}
    document = {"package": [root, first, second]}
    with pytest.raises(ValueError, match="ambiguous"):
        dependency_snapshot.resolved_inventory(document)
    root["dependencies"] = [{"name": "example", "version": "1.0"}]
    assert len(dependency_snapshot.resolved_inventory(document)) == 2
    with pytest.raises(ValueError, match="duplicate"):
        dependency_snapshot.resolved_inventory({
            "package": [root, first, first]
        })
    with pytest.raises(ValueError, match="unsupported"):
        dependency_snapshot.resolved_inventory({
            "package": [
                root,
                {**first, "source": {"git": "https://example.invalid/private"}},
            ]
        })


@pytest.mark.parametrize(
    "change",
    [
        {"GITHUB_ACTIONS": "false"},
        {"GITHUB_EVENT_NAME": "pull_request"},
        {"GITHUB_REF": "refs/heads/feature"},
        {"GITHUB_SHA": "b" * 40},
        {"GITHUB_REPOSITORY": "example/other"},
    ],
)
def test_dependency_submission_requires_exact_trusted_main(change) -> None:
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
    }
    dependency_snapshot.require_trusted_main(env, "a" * 40)
    with pytest.raises(ValueError, match="exact trusted main"):
        dependency_snapshot.require_trusted_main({**env, **change}, "a" * 40)


def test_dependency_submission_workflow_keeps_write_scope_off_prs() -> None:
    document = yaml.safe_load(
        (ROOT / ".github/workflows/security-context.yml").read_text()
    )
    assert document["permissions"] == {"contents": "read"}
    job = document["jobs"]["dependency-submission"]
    assert job["needs"] == "supply-chain"
    assert job["permissions"] == {"contents": "write"}
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.event_name == 'push'" in job["if"]
    assert "github.event_name == 'workflow_dispatch'" in job["if"]
    assert "pull_request" not in job["if"]


@pytest.mark.parametrize(
    "tamper", [None, "digest", "continuing", "date", "count"]
)
def test_approval_event_verifier_preserves_qualification(monkeypatch, tamper):
    event = {
        "concept_id": "us-drugsfda:NDA000001:001",
        "source_sha256": source.SHA256,
        "source_revision": source.REVISION,
        "source_uri": source.URI,
        "continuing_approval_established": False,
        "validity_interval": None,
        "qualification": "exact_product_approval_date",
        "approval_date": "2001-01-02",
    }
    metadata = {
        "product_count": 1,
        "approval_event_coverage": {"exact_product_approval_date": 1},
        "approval_event_summary": {
            "matched_exact_date_count": 1,
            "effective_rights_state": "permitted",
        },
    }
    if tamper == "digest":
        event["source_sha256"] = "wrong"
    if tamper == "continuing":
        event["continuing_approval_established"] = True
    if tamper == "date":
        event["approval_date"] = None
    if tamper == "count":
        metadata["product_count"] = 2
    document = {"application_commit": "c" * 40, "events": [event]}
    monkeypatch.setattr(
        deploy_hf_space.httpx,
        "get",
        lambda *_a, **_k: type(
            "Response",
            (),
            {"raise_for_status": lambda _: None, "json": lambda _: document},
        )(),
    )
    if tamper:
        with pytest.raises(ValueError, match=r"approval|event"):
            deploy_hf_space.verify_approval_events(
                "http://127.0.0.1:7860", "c" * 40, metadata
            )
    else:
        deploy_hf_space.verify_approval_events(
            "http://127.0.0.1:7860", "c" * 40, metadata
        )


def test_native_http_only_verification_does_not_run_browser(monkeypatch):
    expected = {"application_commit": "c" * 40}
    monkeypatch.setattr(
        deploy_hf_space, "http_metadata", lambda _url, _commit: expected
    )

    def reject(*_args):
        raise AssertionError("browser verification is excluded")

    monkeypatch.setattr(deploy_hf_space, "verify", reject)
    receipt = {}
    deploy_hf_space.execute(
        Namespace(
            url="https://global-medicines-atlas.onrender.com",
            exact_commit="c" * 40,
            http_only=True,
        ),
        receipt,
    )
    assert receipt["data"] == expected
    assert receipt["verification_scope"] == "http_only"
    assert receipt["issue_61_complete"] is False


@pytest.mark.parametrize("bound", ["1981-01-01", "1982-01-02"])
def test_approval_bound_verifier_rejects_invented_bounds(bound):
    event = {
        "approval_before_date": bound,
        "qualification": "non_exact_native_date",
        "native_approval_dates": ["Approved Prior to Jan 1, 1982"],
    }
    with pytest.raises(ValueError, match="bound lacks source evidence"):
        deploy_hf_space.verify_approval_bound(event)


def test_approval_bound_verifier_accepts_exact_source_phrase():
    event = {
        "approval_before_date": "1982-01-01",
        "qualification": "non_exact_native_date",
        "native_approval_dates": ["Approved Prior to Jan 1, 1982"],
    }
    deploy_hf_space.verify_approval_bound(event)


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "source",
        "product",
        "date",
        "native",
        "path",
        "duplicate",
        "pagination",
        "coverage",
        "date_count",
    ],
)
def test_submission_event_verifier_checks_pages_scope_and_provenance(
    monkeypatch, tamper
):
    payload = json.dumps({
        "results": [
            {
                "application_number": "NDA000001",
                "submissions": [
                    {
                        "submission_type": "ORIG",
                        "submission_number": "1",
                        "submission_status": "AP",
                        "submission_status_date": "20010102",
                    },
                    {
                        "submission_type": "SUPPL",
                        "submission_number": "2",
                        "submission_status": "TA",
                        "submission_status_date": "20200230",
                    },
                    {
                        "submission_type": "SUPPL",
                        "submission_number": "3",
                        "submission_status": None,
                    },
                ],
            },
            {"application_number": "ANDA000002", "submissions": []},
        ]
    }).encode()
    events, summary = project_submission_events(
        payload,
        source_uri=hosted.BASE + "data/us-openfda-drugsfda.json",
        source_revision=hosted.REVISION,
        source_sha256=hosted.PAYLOAD_SHA,
    )
    metadata = {"application_count": 2, "submission_event_summary": summary}
    if tamper == "source":
        events[0]["source_sha256"] = "wrong"
    elif tamper == "product":
        events[0]["product_status_inferred"] = True
    elif tamper == "date":
        events[0]["submission_status_date"] = "2001-01-03"
    elif tamper == "native":
        events[0]["submission_status"] = "TA"
    elif tamper == "path":
        events[0]["source_path"] = "/results/1/submissions/0"
    elif tamper == "duplicate":
        events[1] = events[0]
    elif tamper == "coverage":
        summary["applications_without_submissions"] = 0
    elif tamper == "date_count":
        summary["exact_date_count"] = 3
    monkeypatch.setattr(hosted, "MAX_SUBMISSION_PAGE", 2)

    def get(_url, *, params, timeout):
        del timeout
        offset = params["offset"]
        subset = events[offset : offset + 2]
        next_offset = (
            offset + len(subset) if offset + len(subset) < len(events) else None
        )
        if tamper == "pagination" and next_offset is not None:
            next_offset = 99
        page = {
            "application_commit": "c" * 40,
            "offset": offset,
            "total": len(events),
            "next_offset": next_offset,
            "events": subset,
        }
        return type(
            "Response",
            (),
            {"raise_for_status": lambda _: None, "json": lambda _: page},
        )()

    monkeypatch.setattr(deploy_hf_space.httpx, "get", get)
    if tamper:
        with pytest.raises(ValueError, match="submission"):
            deploy_hf_space.verify_submission_events(
                "http://127.0.0.1:7860", "c" * 40, metadata
            )
    else:
        deploy_hf_space.verify_submission_events(
            "http://127.0.0.1:7860", "c" * 40, metadata
        )


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "commit",
        "count",
        "duplicate",
        "status",
        "interval",
        "digest",
        "size",
    ],
)
def test_reviewed_action_verifier_checks_provenance_and_receipts(
    monkeypatch, tmp_path, tamper
):
    data = b"%PDF-1.7 synthetic letter"
    digest = hashlib.sha256(data).hexdigest()
    review = {
        "application_number": "NDA000001",
        "submission_status": "AP",
        "submission_status_date": "20200102",
        "letter_sha256": digest,
        "letter_url": "https://example.test/letter.pdf",
        "letter_bytes": len(data),
        "letter_pages": [1],
        "withdrawal": {
            "source_uri": "https://example.test/notice.pdf",
            "source_sha256": digest,
            "source_bytes": len(data),
            "effective_date": "2021-01-01",
            "continuity_between_actions_verified": False,
            "document_number": "05-9624",
        },
        "product_strengths": {"001": "10MG"},
    }
    monkeypatch.setattr(deploy_hf_space, "REVIEWS", (review,))
    event = {
        "concept_id": "us-drugsfda:NDA000001:001",
        "action_status": "AP",
        "action_date": "20200102",
        "letter_sha256": digest,
        "letter_url": review["letter_url"],
        "product_strength_native": "10MG",
        "application_number": "NDA000001",
        "submission_type": "ORIG",
        "submission_number": "1",
        "letter_bytes": len(data),
        "letter_pages": [1],
        "withdrawal": dict(review["withdrawal"]),
        "continuing_status_established": False,
        "validity_interval": None,
    }
    document = {"application_commit": "a" * 40, "events": [event]}
    metadata = {"reviewed_action_mapping_count": 1}
    if tamper == "commit":
        document["application_commit"] = "b" * 40
    if tamper == "count":
        metadata["reviewed_action_mapping_count"] = 2
    if tamper == "duplicate":
        document["events"] = [event, event]
    if tamper == "status":
        event["action_status"] = "TA"
    if tamper == "interval":
        event["validity_interval"] = {"start": "2020-01-02"}
    letter = {
        "url": review["letter_url"],
        "state": "acquired",
        "sha256": digest,
        "bytes": len(data),
    }
    if tamper == "digest":
        letter["sha256"] = "0" * 64
    if tamper == "size":
        letter["bytes"] += 1
    (tmp_path / "fda-action-letter-acquisition-20261103.json").write_text(
        json.dumps({"records": [letter]})
    )
    notice = {
        "document_number": "05-9624",
        "source_uri": review["withdrawal"]["source_uri"],
        "sha256": digest,
        "byte_count": len(data),
        "effective_date": "2021-01-01",
        "continuity_between_approval_and_withdrawal_verified": False,
    }
    (tmp_path / "fda-withdrawal-05-9624-receipt.json").write_text(
        json.dumps(notice)
    )
    real_receipt_check = deploy_hf_space.verify_source_receipts
    monkeypatch.setattr(
        deploy_hf_space,
        "verify_source_receipts",
        lambda reviews: real_receipt_check(reviews, tmp_path),
    )
    monkeypatch.setattr(
        deploy_hf_space.httpx,
        "get",
        lambda *_args, **_kwargs: httpx.Response(
            200,
            json=document,
            request=httpx.Request("GET", "https://example.test"),
        ),
    )
    if tamper:
        with pytest.raises(ValueError, match=r"reviewed action|FDA letter"):
            deploy_hf_space.verify_reviewed_product_actions(
                "https://example.test", "a" * 40, metadata
            )
    else:
        deploy_hf_space.verify_reviewed_product_actions(
            "https://example.test", "a" * 40, metadata
        )


def test_hosted_verifier_receipt_reports_only_safe_http_failure(
    tmp_path, monkeypatch
):
    receipt = tmp_path / "receipt.json"
    request = httpx.Request(
        "GET", "https://www.accessdata.fda.gov/private?token=secret"
    )
    response = httpx.Response(
        302,
        request=request,
        headers={
            "location": "https://www.accessdata.fda.gov/challenge?token=secret"
        },
    )

    def fail(*_args):
        raise httpx.HTTPStatusError(
            "redacted", request=request, response=response
        )

    monkeypatch.setattr(deploy_hf_space, "execute", fail)
    monkeypatch.setattr(
        "sys.argv", ["deploy_hf_space.py", "--receipt", str(receipt)]
    )
    assert deploy_hf_space.main() == 1
    data = json.loads(receipt.read_text())
    assert data["http_host"] == "www.accessdata.fda.gov"
    assert data["http_status"] == 302
    assert data["redirect_same_host"] is True
    assert data["redirect_same_path"] is False
    assert data["redirect_challenge_indicator"] is True
    assert "secret" not in receipt.read_text()


@pytest.mark.parametrize(
    "tamper", [None, "changed_receipt", "same_application"]
)
def test_withdrawal_correction_must_be_retained_and_not_reverse_product(
    tmp_path, tamper
):
    from global_medicines_atlas.fda_action_evidence import REVIEWS  # ruff: ignore[import-outside-top-level]

    original = next(
        x for x in REVIEWS if x["application_number"] == "ANDA074723"
    )
    review = json.loads(json.dumps(original))
    source = ROOT / "docs/qualification"
    shutil.copy(
        source / "fda-action-letter-acquisition-20261103.json", tmp_path
    )
    receipt_path = tmp_path / "fda-withdrawal-2021-13593-receipt.json"
    receipt = json.loads((source / receipt_path.name).read_text())
    if tamper == "changed_receipt":
        receipt["correction"]["source_sha256"] = "0" * 64
    if tamper == "same_application":
        review["withdrawal"]["correction"]["corrected_application"] = (
            "ANDA074723"
        )
        receipt["correction"]["corrected_application"] = "ANDA074723"
    receipt_path.write_text(json.dumps(receipt))
    if tamper:
        with pytest.raises(ValueError, match="withdrawal"):
            deploy_hf_space.verify_source_receipts((review,), tmp_path)
    else:
        deploy_hf_space.verify_source_receipts((review,), tmp_path)


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "selected_date",
        "single_candidate",
        "same_date",
        "qualification",
        "wrong_digest",
    ],
)
def test_conflicting_withdrawals_remain_unresolved_and_receipted(
    tmp_path, tamper
):
    from global_medicines_atlas.fda_action_evidence import REVIEWS  # ruff: ignore[import-outside-top-level]

    source = ROOT / "docs/qualification"
    for name in (
        "fda-action-letter-acquisition-20261103.json",
        "fda-withdrawal-04-10194-receipt.json",
        "fda-withdrawal-05-9624-receipt.json",
    ):
        shutil.copy(source / name, tmp_path)
    review = json.loads(
        json.dumps(
            next(x for x in REVIEWS if x["application_number"] == "NDA050744")
        )
    )
    withdrawal = review["withdrawal"]
    if tamper == "selected_date":
        withdrawal["effective_date"] = "2005-06-15"
    if tamper == "single_candidate":
        withdrawal["candidates"].pop()
    if tamper == "same_date":
        withdrawal["candidates"][0]["effective_date"] = "2005-06-15"
    if tamper == "qualification":
        withdrawal["qualification"] = "confirmed"
    if tamper == "wrong_digest":
        withdrawal["candidates"][0]["source_sha256"] = "0" * 64
    if tamper:
        with pytest.raises(ValueError, match="withdrawal"):
            deploy_hf_space.verify_source_receipts((review,), tmp_path)
    else:
        deploy_hf_space.verify_source_receipts((review,), tmp_path)
