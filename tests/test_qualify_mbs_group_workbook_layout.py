"""Protected group layout discovery must fail closed outside exact main."""

import json
import sys

import pytest
from scripts import qualify_mbs_group_workbook_layout as module


def hosted(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)


def test_local_stops_before_network(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify("a" * 40)


def test_exact_hosted_read_binds_frozen_reference(monkeypatch):
    hosted(monkeypatch)
    bound = module.load_reference(module.ROOT)

    def fetch(_client, reference):
        assert reference == bound
        return b"synthetic only"

    def inspect(payload, reference):
        assert payload == b"synthetic only"
        assert reference == bound
        return {"semantic_roles_assigned": False}

    monkeypatch.setattr(
        module.qualifier.source_reader, "fetch_exact_source_bytes", fetch
    )
    monkeypatch.setattr(module, "inspect_layout", inspect)
    report = module.qualify("a" * 40)
    assert (
        report["new_sources"]
        == report["new_admissions"]
        == report["publications"]
        == 0
    )
    assert report["rights_conclusion_changed"] is False


def test_cli_withholds_source_error(tmp_path, monkeypatch):
    def fail(*_args):
        raise ValueError("SYNTHETIC SOURCE")

    monkeypatch.setattr(module, "qualify", fail)
    output = tmp_path / "layout.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify", "--exact-commit", "a" * 40, "--output", str(output)],
    )
    with pytest.raises(SystemExit, match="source details withheld"):
        module.main()
    assert not output.exists()


def test_transport_identity_mismatch(monkeypatch):
    hosted(monkeypatch)
    monkeypatch.setattr(
        module, "load_reference", lambda _: {"dataset": "wrong"}
    )
    with pytest.raises(ValueError, match="transport identity"):
        module.qualify("a" * 40)


def test_cli_writes_receipt(tmp_path, monkeypatch):

    monkeypatch.setattr(module, "qualify", lambda _: {"new_admissions": 0})
    output = tmp_path / "layout.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify", "--exact-commit", "a" * 40, "--output", str(output)],
    )
    module.main()
    assert json.loads(output.read_text()) == {"new_admissions": 0}
