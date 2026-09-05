"""Configuration rejects candidate self-admission before any retrieval."""

import hashlib
import json
from dataclasses import asdict

import pytest
from test_platinum_query import SCHEMA, binding, contract, parquet_payload
from typer.testing import CliRunner

from global_medicines_atlas.cli import app
from global_medicines_atlas.platinum_configuration import load_benefits_resolver


def configuration(tmp_path):
    document = json.loads(contract(parquet_payload()))
    document["source"]["source_id"] = "au-mbs"
    document["cache"]["expires_at"] = "2099-01-01T00:00:00Z"
    raw = json.dumps(document).encode()
    bound = binding(raw)
    semantic = json.dumps({
        "version": "1.0",
        "resource_id": "au.mbs.items",
        "semantic_dimension": "service_benefit",
        "entity_granularity": "service_item",
        "contract_sha256": bound.contract_sha256,
    }).encode()
    trust = {
        "version": "1.0",
        "resources": [
            {
                "resource_id": "au.mbs.items",
                "semantic_dimension": "service_benefit",
                "entity_granularity": "service_item",
                "binding": asdict(bound),
                "semantic_sha256": hashlib.sha256(semantic).hexdigest(),
                "contract_path": "contract.json",
                "semantic_path": "semantic.json",
            }
        ],
    }
    (tmp_path / "trust.json").write_text(json.dumps(trust))
    (tmp_path / "contract.json").write_bytes(raw)
    (tmp_path / "semantic.json").write_bytes(semantic)
    (tmp_path / "schema.json").write_bytes(SCHEMA)
    return trust


def load(tmp_path):
    return load_benefits_resolver(
        trust_file=tmp_path / "trust.json",
        metadata_root=tmp_path,
        schema_file=tmp_path / "schema.json",
    )


def test_independent_expectations_load_without_payload_reads(tmp_path):
    configuration(tmp_path)
    assert load(tmp_path).resolve("au.mbs.items").source_id == "au-mbs"


@pytest.mark.parametrize("name", ["contract.json", "semantic.json"])
def test_candidate_mutation_does_not_self_admit(tmp_path, name):
    configuration(tmp_path)
    candidate = tmp_path / name
    candidate.write_bytes(candidate.read_bytes() + b" ")
    with pytest.raises(ValueError, match="operator trust"):
        load(tmp_path)


@pytest.mark.parametrize("path", ["../secret.json", "/outside/secret.json"])
def test_metadata_escape_is_rejected(tmp_path, path):
    trust = configuration(tmp_path)
    trust["resources"][0]["contract_path"] = path
    (tmp_path / "trust.json").write_text(json.dumps(trust))
    with pytest.raises(ValueError, match="inside root"):
        load(tmp_path)


def test_cli_offline_returns_provenance_and_typed_unavailability(tmp_path):
    configuration(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            "au.mbs.items",
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--offline",
        ],
        env={"GMA_CURSOR_SECRET": "k" * 32},
    )
    assert result.exit_code == 3, result.output
    page = json.loads(result.stdout)
    assert page["status"] == "unavailable"
    assert page["reason"] == "offline_cache_unavailable"
    assert page["identity"]["source_id"] == "au-mbs"
    assert page["identity"]["semantic_dimension"] == "service_benefit"


def test_empty_trust_is_not_an_admission_policy(tmp_path):
    trust = tmp_path / "trust.json"
    trust.write_text(json.dumps({"version": "1.0", "resources": []}))
    with pytest.raises(ValueError, match="resources"):
        load_benefits_resolver(
            trust_file=trust, metadata_root=tmp_path, schema_file=trust
        )


def test_symlink_escape_rejected(tmp_path):
    candidate_root = tmp_path / "metadata"
    candidate_root.mkdir()
    configuration(candidate_root)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    target = candidate_root / "contract.json"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="inside root"):
        load(candidate_root)


def test_nonregular_trust_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="regular file"):
        load_benefits_resolver(
            trust_file=tmp_path, metadata_root=tmp_path, schema_file=tmp_path
        )


def test_oversized_metadata_rejected(tmp_path):
    configuration(tmp_path)
    (tmp_path / "contract.json").write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="byte bound"):
        load(tmp_path)


def test_duplicate_resources_rejected(tmp_path):
    trust = configuration(tmp_path)
    trust["resources"] *= 2
    (tmp_path / "trust.json").write_text(json.dumps(trust))
    with pytest.raises(ValueError, match="duplicate resource"):
        load(tmp_path)


@pytest.mark.parametrize(
    ("resource", "extra", "secret", "error"),
    [
        ("au.mbs.items", [], "", "service_unavailable"),
        ("au.mbs.items", [], "short", "service_unavailable"),
        ("au.mbs.missing", [], "k" * 32, "not_found"),
        ("au.mbs.items", ["--filters-json", "{}"], "k" * 32, "invalid_request"),
        (
            "au.mbs.items",
            ["--column", "item; DROP TABLE"],
            "k" * 32,
            "invalid_request",
        ),
    ],
)
def test_cli_errors_are_typed_without_disclosing_operator_inputs(
    tmp_path, resource, extra, secret, error
):
    configuration(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "benefits",
            resource,
            "--trust-file",
            str(tmp_path / "trust.json"),
            "--metadata-root",
            str(tmp_path),
            "--schema-file",
            str(tmp_path / "schema.json"),
            "--column",
            "item_code",
            "--offline",
            *extra,
        ],
        env={"GMA_CURSOR_SECRET": secret},
    )
    assert result.exit_code == 2, result.output
    assert not result.stdout
    envelope = json.loads(result.stderr)
    assert envelope["error"] == error
    assert str(tmp_path) not in result.stderr
    if secret:
        assert secret not in result.stderr
