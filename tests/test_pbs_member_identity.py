"""Synthetic archive/member lineage, without acquisition or admission."""

from dataclasses import replace

import pytest
from pydantic import ValidationError
from test_au_pbs_v3 import (
    _xml,  # ruff: ignore[import-private-name] -- synthetic fixture
    _zip,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture
)

from global_medicines_atlas import pbs_member_identity as bridge
from global_medicines_atlas.adapters import au_pbs
from global_medicines_atlas.pbs_silver import iter_pbs_silver_batches
from global_medicines_atlas.receipts import AcquisitionStatus, PayloadEvidence

PATH = "release/SCH-fixture.xml"
SOURCE = "au-pbs-historical-xml"


def test_binding_preserves_parent_and_member_identities_without_relabel() -> (
    None
):
    xml = _xml()
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    binding = bridge.build_pbs_xml_member_binding(archive, parent)
    assert binding.source == parent.source
    assert binding.parent_receipt_sha256 == parent.digest()
    assert binding.archive_payload == parent.payload
    assert binding.member_path == PATH
    assert binding.member_payload == PayloadEvidence.from_bytes(xml)
    assert binding.derivation == "zip-member-extraction"
    assert binding.qualification == "candidate"
    assert (
        bridge.validate_pbs_xml_member_binding(binding, archive, xml, parent)
        == binding
    )
    assert (
        bridge.PbsXmlMemberBinding.model_validate_json(binding.canonical_json())
        == binding
    )
    assert (
        bridge.build_pbs_xml_member_binding(archive, parent).digest()
        == binding.digest()
    )
    assert parent.source.source_id == SOURCE
    assert b"fixtures.invalid" not in binding.canonical_json()
    with pytest.raises(ValueError, match="source"):
        list(iter_pbs_silver_batches(xml, parent))


@pytest.mark.parametrize("part", ["archive", "member", "parent"])
def test_mismatched_bytes_or_parent_receipt_rejected(part: str) -> None:
    xml = _xml()
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    binding = bridge.build_pbs_xml_member_binding(archive, parent)
    if part == "archive":
        archive = _zip([(PATH, xml + b" ")])
    elif part == "member":
        xml += b" "
    else:
        parent = parent.model_copy(update={"receipt_id": "different-parent"})
    with pytest.raises(ValueError, match="match"):
        bridge.validate_pbs_xml_member_binding(binding, archive, xml, parent)


@pytest.mark.parametrize("source", ["au-pbs", "au-mbs", "foreign"])
def test_wrong_source_not_aliased(source: str) -> None:
    archive = _zip([(PATH, _xml())])
    with pytest.raises(ValueError, match="source"):
        bridge.build_pbs_xml_member_binding(archive, _receipt(archive, source))


@pytest.mark.parametrize(
    "key",
    [
        "parent_receipt_sha256",
        "archive_payload",
        "member_path",
        "member_payload",
        "source",
    ],
)
def test_missing_lineage_rejected(key: str) -> None:
    archive = _zip([(PATH, _xml())])
    document = bridge.build_pbs_xml_member_binding(
        archive, _receipt(archive, SOURCE)
    ).model_dump()
    del document[key]
    with pytest.raises(ValidationError):
        bridge.PbsXmlMemberBinding.model_validate(document)


@pytest.mark.parametrize(
    "path",
    ["../SCH-fixture.xml", "/SCH-fixture.xml", "a/../../SCH-fixture.xml"],
)
def test_traversal_rejected(path: str) -> None:
    archive = _zip([(path, _xml())])
    with pytest.raises(ValueError, match="unsafe"):
        bridge.build_pbs_xml_member_binding(archive, _receipt(archive, SOURCE))


def test_duplicate_archive_members_rejected() -> None:
    with pytest.warns(UserWarning, match="Duplicate"):
        archive = _zip([(PATH, _xml()), (PATH, _xml())])
    with pytest.raises(ValueError, match="duplicate"):
        bridge.build_pbs_xml_member_binding(archive, _receipt(archive, SOURCE))


@pytest.mark.parametrize(
    "entries",
    [[("other.xml", _xml())], [("SCH-a.xml", _xml()), ("SCH-b.xml", _xml())]],
)
def test_requires_one_schedule_member(entries: list[tuple[str, bytes]]) -> None:
    archive = _zip(entries)
    with pytest.raises(ValueError, match="exactly one"):
        bridge.build_pbs_xml_member_binding(archive, _receipt(archive, SOURCE))


@pytest.mark.parametrize(
    "xml", [b"not XML", b'<x:root xmlns:x="urn:foreign"/>']
)
def test_wrong_xml_root_rejected(xml: bytes) -> None:
    archive = _zip([(PATH, xml)])
    with pytest.raises(ValueError, match=r"XML|root"):
        bridge.build_pbs_xml_member_binding(archive, _receipt(archive, SOURCE))


def test_duplicate_items_do_not_prevent_byte_identity_binding() -> None:
    xml = _xml()
    start = xml.index(b"<pbs:pharmaceutical-item")
    stop = xml.index(b"</pbs:pharmaceutical-item>") + len(
        b"</pbs:pharmaceutical-item>"
    )
    xml = xml[:stop] + xml[start:stop] + xml[stop:]
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    binding = bridge.build_pbs_xml_member_binding(archive, parent)
    assert (
        bridge.validate_pbs_xml_member_binding(binding, archive, xml, parent)
        == binding
    )
    with pytest.raises(ValueError, match="duplicate item"):
        au_pbs.parse_pbs_v3_archive(archive)


def test_archive_budget_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _zip([(PATH, _xml())])
    monkeypatch.setattr(
        au_pbs,
        "PBS_ARCHIVE_POLICY",
        replace(au_pbs.PBS_ARCHIVE_POLICY, max_archive_bytes=1),
    )
    with pytest.raises(ValueError, match="byte limit"):
        bridge.build_pbs_xml_member_binding(archive, _receipt(archive, SOURCE))


@pytest.mark.parametrize(
    "key",
    [
        "parent_receipt_sha256",
        "member_path",
        "member_payload",
        "archive_payload",
    ],
)
def test_forged_binding_revalidated(key: str) -> None:
    xml = _xml()
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    binding = bridge.build_pbs_xml_member_binding(archive, parent)
    value = {
        "parent_receipt_sha256": "f" * 64,
        "member_path": "SCH-other.xml",
        "member_payload": PayloadEvidence.from_bytes(b"other"),
        "archive_payload": PayloadEvidence.from_bytes(b"other"),
    }[key]
    binding = binding.model_copy(update={key: value})
    with pytest.raises(ValueError, match="match"):
        bridge.validate_pbs_xml_member_binding(binding, archive, xml, parent)


def test_wrong_jurisdiction_and_failed_parent_rejected() -> None:
    archive = _zip([(PATH, _xml())])
    parent = _receipt(archive, SOURCE)
    wrong = parent.model_copy(
        update={
            "source": parent.source.model_copy(update={"jurisdiction": "NZL"})
        }
    )
    with pytest.raises(ValueError, match="source"):
        bridge.build_pbs_xml_member_binding(archive, wrong)
    failed = parent.model_copy(
        update={
            "retrieval": parent.retrieval.model_copy(
                update={"status": AcquisitionStatus.FAILED}
            )
        }
    )
    with pytest.raises(ValueError, match="succeeded"):
        bridge.build_pbs_xml_member_binding(archive, failed)
