"""Real synthetic Git bundles and fail-closed hosted runner entry points."""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from global_medicines_atlas import donor_delta, donor_history_publication
from global_medicines_atlas.federation_metadata_append import ObjectDigest
from global_medicines_atlas.federation_metadata_hosted import PublicSnapshot


@pytest.fixture
def publisher(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    return importlib.import_module("publish_donor_history")


def test_incremental_bundle_restores_only_with_baseline(publisher, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    git = publisher.git
    git(source, "init", "--quiet")
    (source / "example.txt").write_text("synthetic baseline\n")
    git(source, "add", "example.txt")
    git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "baseline",
    )
    baseline = git(source, "rev-parse", "HEAD")
    git(source, "update-ref", "refs/archive/pinned", baseline)
    baseline_bundle = tmp_path / "baseline.bundle"
    git(
        source,
        "bundle",
        "create",
        "--version=2",
        str(baseline_bundle),
        "refs/archive/pinned",
    )
    (source / "example.txt").write_text("synthetic extension\n")
    git(source, "add", "example.txt")
    git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "extension",
    )
    head = git(source, "rev-parse", "HEAD")
    git(source, "update-ref", "refs/archive/extension", head)
    extension = tmp_path / "extension.bundle"
    git(
        source,
        "bundle",
        "create",
        "--version=2",
        str(extension),
        "refs/archive/extension",
        f"^{baseline}",
    )
    assert publisher.prerequisites(extension) == (baseline,)
    assert publisher.prerequisites(baseline_bundle) == ()
    restore = tmp_path / "restore"
    restore.mkdir()
    git(restore, "init", "--bare", "--quiet")
    with pytest.raises(ValueError, match="Git operation failed"):
        git(restore, "bundle", "verify", str(extension))
    git(
        restore,
        "fetch",
        str(baseline_bundle),
        "refs/archive/pinned:refs/archive/baseline",
    )
    git(restore, "bundle", "verify", str(extension))
    git(
        restore,
        "fetch",
        str(extension),
        "refs/archive/extension:refs/archive/extension",
    )
    assert git(restore, "rev-parse", "refs/archive/extension") == head
    git(restore, "merge-base", "--is-ancestor", baseline, head)
    git(restore, "update-ref", "--no-deref", "HEAD", head)
    git(restore, "fsck", "--full", "--strict")


@pytest.mark.parametrize(
    "payload",
    [
        b"bad\n",
        b"# v2 git bundle\n",
        b"# v2 git bundle\n" + b"a" * 4096,
        b"# v2 git bundle\n" + b"a\n" * 256,
    ],
)
def test_malformed_bundle_headers_fail(publisher, tmp_path, payload):
    path = tmp_path / "bad.bundle"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="bundle"):
        publisher.prerequisites(path)


def test_history_cli_refuses_local_before_network(publisher, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(
        "sys.argv", ["publish_donor_history.py", "--exact-commit", "a" * 40]
    )

    def forbidden(*_):
        pytest.fail("network or temporary workspace before authority")

    monkeypatch.setattr(publisher, "gh", forbidden)
    monkeypatch.setattr(publisher.tempfile, "mkdtemp", forbidden)
    with pytest.raises(ValueError, match="Actions dispatch"):
        publisher.main()


def test_history_cli_refuses_inert_contract_before_network(
    publisher, monkeypatch
):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        "sys.argv", ["publish_donor_history.py", "--exact-commit", "a" * 40]
    )

    def forbidden(*_):
        pytest.fail("network before explicit authorization")

    monkeypatch.setattr(publisher, "gh", forbidden)
    with pytest.raises(ValueError, match="not authorized"):
        publisher.main()


def test_retained_local_patch_and_fixture_have_exact_digests(publisher):
    root = Path(__file__).parents[1] / "docs/migrations/scraper-local-20260906"
    inventory = json.loads((root / "inventory.json").read_text())
    patch = inventory["preserved_patch"]
    assert (
        publisher.object_info(patch["path"], root / patch["path"]).sha256
        == patch["sha256"]
    )
    fixture = next(
        item
        for item in inventory["local_entries"]
        if item["disposition"] == "retain-synthetic-legacy"
    )
    observed = publisher.object_info(
        "sample_pbs.json", root / "sample_pbs.json"
    )
    assert observed.sha256 == fixture["sha256"]
    assert observed.byte_count == fixture["bytes"]


def test_complete_hosted_transport_with_synthetic_git(  # ruff: ignore[too-many-statements, too-many-locals] -- keep the synthetic transaction visible
    publisher, monkeypatch, tmp_path
):

    real_git = publisher.git
    sources = {}
    heads = []
    baselines = {}
    observations = {}
    storage = {}
    for repository, _ in publisher.EXACT_HEADS:
        name = repository.split("/")[1]
        source = tmp_path / name
        source.mkdir()
        real_git(source, "init", "--quiet")
        (source / "README.md").write_text("synthetic baseline\n")
        real_git(source, "add", "README.md")
        real_git(
            source,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "baseline",
        )
        baseline = real_git(source, "rev-parse", "HEAD")
        real_git(source, "update-ref", "refs/archive/pinned", baseline)
        bundle = tmp_path / f"{name}.bundle"
        real_git(
            source,
            "bundle",
            "create",
            "--version=2",
            str(bundle),
            "refs/archive/pinned",
        )
        storage[f"history/{name}-{baseline}.bundle"] = bundle.read_bytes()
        (source / "README.md").write_text("synthetic extension\n")
        real_git(source, "add", "README.md")
        real_git(
            source,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "extension",
        )
        head = real_git(source, "rev-parse", "HEAD")
        heads.append((repository, head))
        baselines[repository] = baseline
        sources[repository] = source
        observations[repository] = {
            "status": "ahead",
            "files": [
                {
                    "filename": "README.md",
                    "sha": real_git(source, "rev-parse", "HEAD:README.md"),
                    "status": "modified",
                }
            ],
        }
    storage["unrelated-retained.txt"] = b"unrelated public object"
    monkeypatch.setattr(donor_delta, "BASELINES", baselines)
    monkeypatch.setattr(donor_history_publication, "EXACT_HEADS", tuple(heads))
    monkeypatch.setattr(publisher, "BASELINES", baselines)
    monkeypatch.setattr(publisher, "EXACT_HEADS", tuple(heads))

    def git(directory, *args):
        if args[0] == "clone":
            repository = (
                args[-2]
                .removeprefix("https://github.com/")
                .removesuffix(".git")
            )
            args = (*args[:-2], str(sources[repository]), args[-1])
        return real_git(directory, *args)

    def gh(endpoint):
        repository = "/".join(endpoint.split("/")[1:3])
        return (
            {"sha": dict(heads)[repository]}
            if endpoint.endswith("commits/main")
            else observations[repository]
        )

    class Hub:
        current = "d" * 40

        def __init__(self, cache):
            self.cache = cache

        def head(self, dataset):
            assert dataset == publisher.DATASET
            return self.current

        def snapshot(self, dataset, revision):
            assert revision == self.current
            objects = []
            for name in storage:
                path = self._download(dataset, revision, name)
                obj = publisher.object_info(name, path)
                objects.append(
                    ObjectDigest(obj.path, obj.byte_count, obj.sha256)
                )
            return PublicSnapshot(
                revision=revision,
                private=False,
                gated=False,
                objects=tuple(objects),
            )

        def _download(self, dataset, revision, name):
            assert dataset == publisher.DATASET
            assert revision == self.current
            path = self.cache / name.replace("/", "-")
            path.write_bytes(storage[name])
            return path

    def create_commit(**kwargs):
        assert kwargs["parent_commit"] == "d" * 40
        assert kwargs["repo_id"] == publisher.DATASET
        assert len(kwargs["operations"]) == 4
        for addition in kwargs["operations"]:
            assert addition.path_in_repo not in storage
            storage[addition.path_in_repo] = Path(
                addition.path_or_fileobj
            ).read_bytes()
        transport.hub.current = "e" * 40
        return SimpleNamespace(oid="e" * 40)

    sdk = SimpleNamespace(
        CommitOperationAdd=SimpleNamespace,
        HfApi=lambda **_: SimpleNamespace(create_commit=create_commit),
    )
    monkeypatch.setattr(publisher, "git", git)
    monkeypatch.setattr(publisher, "gh", gh)
    monkeypatch.setattr(publisher, "HubTransport", Hub)
    monkeypatch.setattr(
        publisher, "importlib", SimpleNamespace(import_module=lambda _: sdk)
    )
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "f" * 40,
        "GITHUB_RUN_ID": "123",
        "HF_TOKEN": "synthetic-test-only",
    }.items():
        monkeypatch.setenv(key, value)
    contract = publisher.DonorHistoryPublicationContract(
        dataset=publisher.DATASET,
        heads=tuple(heads),
        publication_authorized=True,
        authorization_reference="https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-123",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    transport = publisher.DonorTransport(workspace, contract)
    receipts = []

    def persist(document):
        receipts.append(document)
        return "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-123"

    result = publisher.execute_history_append(
        contract, exact_commit="f" * 40, transport=transport, persist=persist
    )
    assert result["status"] == "anonymously_verified"
    assert len(result["verification"]["restored"]) == 2
    assert storage["unrelated-retained.txt"] == b"unrelated public object"
    assert len(storage) == 7
