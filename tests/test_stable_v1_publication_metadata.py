from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from global_medicines_atlas import publication_metadata_qualification as pmq
from global_medicines_atlas.publication_contracts import (
    PublicationIdentityRegistry,
    PublicationPackage,
    PublicationVerificationReceipt,
)
from global_medicines_atlas.publication_metadata_qualification import (
    GateEvidence,
    GateState,
    PublicationMetadataQualificationError,
    PublicationMetadataQualificationReceipt,
    canonical_receipt_bytes,
    qualify_publication_metadata,
    verify_publication_metadata_receipt,
)
from global_medicines_atlas.publication_package import (
    GeneratedFile,
    GeneratedPublicationPackage,
    generate_publication_package,
)

ROOT = Path(__file__).resolve().parents[1]


def test_content_binding_is_checkout_newline_portable(tmp_path: Path) -> None:
    path = tmp_path / "input.jsonl"
    path.write_bytes(b'{"id": 1}\r\n')

    binding = pmq._binding(tmp_path, "input.jsonl")

    assert binding.size == len(b'{"id": 1}\n')
    assert binding.sha256 == pmq.hashlib.sha256(b'{"id": 1}\n').hexdigest()


SCHEMA = (
    ROOT / "schemas" / "stable-v1-publication-metadata-qualification-v1.json"
)
RECEIPT = (
    ROOT / "quality" / "qualifications" / "stable-v1-publication-metadata.json"
)


def _json(path: Path) -> dict[str, Any]:
    payload = cast("object", json.loads(path.read_text(encoding="utf-8")))
    assert isinstance(payload, dict)
    return cast("dict[str, Any]", payload)


def _copy_inputs(tmp_path: Path) -> Path:
    paths = (
        "release-inputs/publication-contract.json",
        "release-inputs/publication-qualification.json",
        "release-inputs/reviewed-rows.jsonl",
        "quality/qualifications/publication-identities.json",
        "schemas/publication-identity-registry-v1.json",
        "schemas/stable-v1-publication-metadata-qualification-v1.json",
        "scripts/qualify_stable_v1_publication_metadata.py",
        "src/global_medicines_atlas/publication_contracts.py",
        "src/global_medicines_atlas/publication_package.py",
        "src/global_medicines_atlas/publication_metadata_qualification.py",
        "uv.lock",
    )
    for relative in paths:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return tmp_path


def _generated_package() -> tuple[
    GeneratedPublicationPackage,
    PublicationPackage,
    PublicationVerificationReceipt,
]:
    contract = PublicationPackage.model_validate_json(
        (ROOT / "release-inputs/publication-contract.json").read_text()
    )
    qualification = PublicationVerificationReceipt.model_validate_json(
        (ROOT / "release-inputs/publication-qualification.json").read_text()
    )
    rows = tuple(
        json.loads(line)
        for line in (ROOT / "release-inputs/reviewed-rows.jsonl")
        .read_text()
        .splitlines()
    )
    return (
        generate_publication_package(contract, qualification, rows),
        contract,
        qualification,
    )


def _replace_member(
    package: GeneratedPublicationPackage, path: str, content: bytes | None
) -> GeneratedPublicationPackage:
    files = [item for item in package.files if item.path != path]
    if content is not None:
        files.append(GeneratedFile(path=path, content=content))
    return GeneratedPublicationPackage(
        files=tuple(sorted(files, key=lambda item: item.path))
    )


@pytest.mark.integration
def test_committed_receipt_is_exact_deterministic_and_schema_valid() -> None:
    first = qualify_publication_metadata(ROOT)
    second = qualify_publication_metadata(ROOT)
    assert first == second
    assert canonical_receipt_bytes(first) == RECEIPT.read_bytes()

    schema = _json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first.model_dump(mode="json"))
    assert verify_publication_metadata_receipt(ROOT, RECEIPT) == first


def test_receipt_passes_metadata_but_blocks_every_external_gate() -> None:
    receipt = qualify_publication_metadata(ROOT)
    gates = {item.gate_id: item for item in receipt.gates}
    assert receipt.result == "metadata_qualified_external_gates_blocked"
    assert {name for name, gate in gates.items() if gate.state == "passed"} == {
        "checksums",
        "croissant",
        "dataset-card",
        "identifier-links",
        "restricted-data-boundary",
    }
    assert {
        name for name, gate in gates.items() if gate.state == "blocked"
    } == {"external-identifiers", "licences", "publication"}
    assert receipt.external_actions.model_dump() == {
        "credentials_used": False,
        "publication_performed": False,
        "release_created": False,
        "remote_write_attempted": False,
        "signature_created": False,
    }
    assert receipt.package.fixture_only is True
    assert receipt.package.restricted_data_included is False
    assert receipt.package.dataset_version == "0.7.0"
    assert receipt.ready_for_publication is False


def test_identity_states_and_links_are_complete_and_non_overlapping() -> None:
    receipt = qualify_publication_metadata(ROOT)
    identities = {item.system: item for item in receipt.identities}
    assert set(identities) == {"github", "hugging_face", "zenodo", "osf"}
    assert identities["github"].identifier_state == "verified"
    assert identities["github"].licence_state == "approved"
    assert identities["github"].licence_expression == "Apache-2.0"
    for system in ("hugging_face", "zenodo"):
        assert identities[system].identifier_state == "verified"
        assert identities[system].licence_state == "approved"
        assert identities[system].licence_expression == "Apache-2.0"
    assert identities["osf"].licence_state == "unresolved"
    assert identities["osf"].identifier is None
    assert len({item.object_role for item in identities.values()}) == 4
    links = {
        (item.object_id, related)
        for item in identities.values()
        for related in item.related_object_ids
    }
    assert all((target, source) in links for source, target in links)


@pytest.mark.parametrize(
    ("relative", "mutation", "message"),
    [
        (
            "release-inputs/publication-contract.json",
            lambda payload: payload["dataset_card"]["rights"][0].update(
                disposition="restricted"
            ),
            "non-publishable source rights",
        ),
        (
            "release-inputs/publication-contract.json",
            lambda payload: payload["croissant"].update(name="Other name"),
            "must agree",
        ),
        (
            "release-inputs/publication-qualification.json",
            lambda payload: payload.update(package_sha256="f" * 64),
            "bound to the package",
        ),
    ],
)
def test_candidate_metadata_tampering_fails_closed(
    tmp_path: Path,
    relative: str,
    mutation: Any,
    message: str,
) -> None:
    root = _copy_inputs(tmp_path)
    path = root / relative
    payload = _json(path)
    mutation(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        (PublicationMetadataQualificationError, ValueError), match=message
    ):
        qualify_publication_metadata(root)


@pytest.mark.parametrize(
    ("system", "identifier"),
    [
        ("github", "https://huggingface.co/edithatogo/example"),
        ("hugging_face", "https://github.com/edithatogo/example"),
        ("zenodo", "https://osf.io/abc12"),
        ("osf", "https://zenodo.org/records/123"),
    ],
)
def test_cross_surface_identifier_hosts_fail_closed(
    tmp_path: Path, system: str, identifier: str
) -> None:
    root = _copy_inputs(tmp_path)
    path = root / "quality/qualifications/publication-identities.json"
    payload = _json(path)
    row = next(
        item for item in payload["identities"] if item["system"] == system
    )
    row.update(identifier=identifier, identifier_state="configured")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        PublicationMetadataQualificationError, match="identifier host"
    ):
        qualify_publication_metadata(root)


def test_normalized_duplicate_identifiers_fail_closed(tmp_path: Path) -> None:
    root = _copy_inputs(tmp_path)
    path = root / "quality/qualifications/publication-identities.json"
    payload = _json(path)
    payload["identities"][0].update(
        identifier="https://github.com/edithatogo/global-medicines-atlas/",
        identifier_state="configured",
    )
    payload["identities"][1].update(
        identifier="HTTPS://GITHUB.COM/edithatogo/global-medicines-atlas",
        identifier_state="configured",
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        PublicationMetadataQualificationError,
        match=r"identifier host|overlap after normalization",
    ):
        qualify_publication_metadata(root)


def test_non_reciprocal_identifier_link_fails_closed(tmp_path: Path) -> None:
    root = _copy_inputs(tmp_path)
    path = root / "quality/qualifications/publication-identities.json"
    payload = _json(path)
    payload["identities"][1]["related_object_ids"].remove(
        "software-source-release"
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        PublicationMetadataQualificationError, match="must be reciprocal"
    ):
        qualify_publication_metadata(root)


def test_receipt_tampering_fails_closed(tmp_path: Path) -> None:
    payload = _json(RECEIPT)
    payload["external_actions"]["publication_performed"] = True
    tampered = tmp_path / "receipt.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PydanticValidationError, match="publication_performed"):
        verify_publication_metadata_receipt(ROOT, tampered)


@given(st.sampled_from(["identifier_state", "licence_state"]))
@pytest.mark.property
def test_approval_words_without_durable_evidence_never_open_gate(
    field: str,
) -> None:
    payload = _json(ROOT / "quality/qualifications/publication-identities.json")
    row = payload["identities"][0]
    if field == "identifier_state":
        row["identifier_state"] = "verified"
        row["identifier_evidence"] = None
    else:
        row["licence_state"] = "approved"
        row["licence_expression"] = "TEST-ONLY"
        row["licence_decision_evidence"] = None
    with pytest.raises(PydanticValidationError):
        PublicationIdentityRegistry.model_validate(payload)


def test_schema_forbids_external_action_claims() -> None:
    schema = _json(SCHEMA)
    payload = _json(RECEIPT)
    payload["external_actions"]["release_created"] = True
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(schema).validate(payload)


@pytest.mark.parametrize(
    ("state", "blockers", "message"),
    [
        (GateState.PASSED, ("unexpected",), "passed metadata gate"),
        (GateState.BLOCKED, (), "blocked metadata gate"),
        (GateState.BLOCKED, ("b", "a"), "sorted and unique"),
    ],
)
def test_gate_state_contradictions_fail_closed(
    state: GateState, blockers: tuple[str, ...], message: str
) -> None:
    with pytest.raises(PydanticValidationError, match=message):
        GateEvidence(
            gate_id="test",
            state=state,
            evidence=("test",),
            blockers=blockers,
        )


@pytest.mark.parametrize(
    ("field", "mutation", "message"),
    [
        (
            "gates",
            lambda payload: list(reversed(payload["gates"])),
            "incomplete or unordered",
        ),
        (
            "gates",
            lambda payload: [
                {**payload["gates"][0], "state": "blocked", "blockers": ["x"]},
                *payload["gates"][1:],
            ],
            "states are not fail-closed",
        ),
        (
            "blockers",
            lambda _payload: ["not-the-gate-union"],
            "blocker union",
        ),
        (
            "inputs",
            lambda payload: list(reversed(payload["inputs"])),
            "sorted unique paths",
        ),
    ],
)
def test_receipt_structure_mutations_fail_closed(
    field: str, mutation: Any, message: str
) -> None:
    payload = qualify_publication_metadata(ROOT).model_dump(mode="json")
    payload[field] = mutation(payload)
    with pytest.raises(PydanticValidationError, match=message):
        PublicationMetadataQualificationReceipt.model_validate(payload)


def test_invalid_self_hash_and_stale_valid_receipt_fail_closed(
    tmp_path: Path,
) -> None:
    receipt = qualify_publication_metadata(ROOT)
    with pytest.raises(
        PublicationMetadataQualificationError, match="self-hash"
    ):
        canonical_receipt_bytes(
            receipt.model_copy(update={"receipt_sha256": "f" * 64})
        )

    changed_package = receipt.package.model_copy(
        update={"dataset_title": "Different synthetic title"}
    )
    changed = receipt.model_copy(update={"package": changed_package})
    changed = changed.model_copy(
        update={"receipt_sha256": pmq._receipt_digest(changed)}
    )
    path = tmp_path / "stale.json"
    path.write_bytes(pmq._canonical_json(changed.model_dump(mode="json")))
    with pytest.raises(
        PublicationMetadataQualificationError, match="current inputs"
    ):
        verify_publication_metadata_receipt(ROOT, path)


def test_input_path_and_row_boundaries_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(
        PublicationMetadataQualificationError, match="unsafe qualification"
    ):
        pmq._contained_file(ROOT, "../outside")
    with pytest.raises(
        PublicationMetadataQualificationError, match="absent or escapes"
    ):
        pmq._contained_file(ROOT, "missing.json")
    with pytest.raises(
        PublicationMetadataQualificationError, match="not a regular file"
    ):
        pmq._contained_file(ROOT, "release-inputs")

    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(
        PublicationMetadataQualificationError, match="invalid JSON"
    ):
        pmq._load_rows(invalid)
    invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(
        PublicationMetadataQualificationError, match="must be an object"
    ):
        pmq._load_rows(invalid)
    invalid.write_text("\n", encoding="utf-8")
    with pytest.raises(
        PublicationMetadataQualificationError, match="must not be empty"
    ):
        pmq._load_rows(invalid)


def test_package_member_json_and_checksum_failures_are_rejected() -> None:
    package, contract, qualification = _generated_package()
    with pytest.raises(
        PublicationMetadataQualificationError, match="missing required metadata"
    ):
        pmq._member(
            _replace_member(package, "metadata/dataset-card.json", None),
            "metadata/dataset-card.json",
        )
    with pytest.raises(
        PublicationMetadataQualificationError, match="valid UTF-8 JSON"
    ):
        pmq._load_object(b"\xff", "test")
    with pytest.raises(
        PublicationMetadataQualificationError, match="must be a JSON object"
    ):
        pmq._load_object(b"[]", "test")

    for content, message in (
        (b"\xff", "valid UTF-8"),
        (b"malformed\n", "malformed entry"),
        (
            b"f" * 64 + b"  z\n" + b"e" * 64 + b"  a\n",
            "sorted unique paths",
        ),
        (b"f" * 64 + b"  metadata/citations.json\n", "every exact"),
    ):
        altered = _replace_member(package, "SHA256SUMS", content)
        with pytest.raises(
            PublicationMetadataQualificationError, match=message
        ):
            pmq._verify_checksums(altered)

    altered_manifest = _replace_member(
        package, "package-manifest.json", b"{}\n"
    )
    with pytest.raises(
        PublicationMetadataQualificationError, match="manifest does not bind"
    ):
        pmq._verify_manifest(altered_manifest, contract, qualification)


@pytest.mark.parametrize(
    "identifier",
    [
        "https://user:secret@github.com/edithatogo/global-medicines-atlas",
        "https://github.com/edithatogo/global-medicines-atlas?token=x",
        "https://github.com/#fragment",
    ],
)
def test_unsafe_github_identifier_shapes_fail_closed(
    identifier: str,
) -> None:
    registry = PublicationIdentityRegistry.model_validate(
        _json(ROOT / "quality/qualifications/publication-identities.json")
    )
    identity = registry.identities[0].model_copy(
        update={"identifier": identifier}
    )
    with pytest.raises(
        PublicationMetadataQualificationError, match="URL shape"
    ):
        pmq._normalized_identifier(identity)


def test_documentation_states_exact_scope_and_blockers() -> None:
    text = " ".join(
        (ROOT / "docs/qualification/stable-v1-publication-metadata.md")
        .read_text(encoding="utf-8")
        .casefold()
        .split()
    )
    for claim in (
        "metadata_qualified_external_gates_blocked",
        "no restricted data",
        "no external publication",
        "no release",
        "no signature",
        "github",
        "hugging face",
        "zenodo",
        "osf",
        "licence",
    ):
        assert claim in text
