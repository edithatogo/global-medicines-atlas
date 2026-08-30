"""Candidate parent-B1/archive-B2/XML-member identity, not acquisition."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .adapters.au_pbs import (
    PBS_V3_NAMESPACE,
    inspect_pbs_v3_tags,
    read_pbs_v3_member,
)
from .receipts import (
    SHA256_PATTERN,
    DeterministicReceipt,
    PayloadEvidence,
    SourceIdentity,
    SourceReceipt,
)


class PbsXmlMemberBinding(DeterministicReceipt):
    """Rebuildable member lineage requiring validation against exact inputs.

    Deserialization alone does not verify bytes, establish admission or grant
    a source alias. The original archive remains evidentiary B2 truth.
    """

    schema_name: Literal["global-medicines-atlas.pbs-xml-member-binding"] = (
        "global-medicines-atlas.pbs-xml-member-binding"
    )
    schema_version: Literal["1.0"] = "1.0"
    qualification: Literal["candidate"] = "candidate"
    derivation: Literal["zip-member-extraction"] = "zip-member-extraction"
    source: SourceIdentity
    parent_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    archive_payload: PayloadEvidence
    member_path: str = Field(min_length=1, max_length=4096)
    member_payload: PayloadEvidence


def build_pbs_xml_member_binding(
    archive_payload: bytes, parent: SourceReceipt
) -> PbsXmlMemberBinding:
    """Bind one safe PBS XML member to its unchanged historical parent.

    Only au-pbs-historical-xml/AUS parents with successful retrieval and exact
    archive payload evidence are accepted. Existing finite ZIP/XML policies
    apply; bytes are processed in memory, not acquired or persisted. Duplicate
    item identifiers do not defeat byte identity. Full source qualification,
    rights, source aliases, table admission and date profiles remain separate.
    """
    parent = SourceReceipt.model_validate(parent.model_dump())
    if (
        parent.source.source_id != "au-pbs-historical-xml"
        or parent.source.jurisdiction != "AUS"
    ):
        raise ValueError("PBS historical archive source identity required")
    if not parent.payload.matches(archive_payload):
        raise ValueError("PBS archive bytes do not match parent receipt")
    member, xml_payload = read_pbs_v3_member(archive_payload)
    root_name = inspect_pbs_v3_tags(xml_payload, max_tags=1)[0]
    if root_name not in {
        f"{{{PBS_V3_NAMESPACE}}}root",
        f"{{{PBS_V3_NAMESPACE}}}schedule",
    }:
        raise ValueError("PBS member namespace/root does not match contract")
    return PbsXmlMemberBinding(
        source=parent.source,
        parent_receipt_sha256=parent.digest(),
        archive_payload=parent.payload,
        member_path=member.path,
        member_payload=PayloadEvidence(
            sha256=member.sha256, byte_count=member.size_bytes
        ),
    )


def validate_pbs_xml_member_binding(
    binding: PbsXmlMemberBinding,
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
) -> PbsXmlMemberBinding:
    """Recompute lineage and reject any parent/archive/member mismatch.

    A caller must supply all exact inputs; metadata alone is insufficient.
    Validation does not replace a SourceReceipt or relax any adapter gate.
    No source relabeling, date conversion, network or filesystem writes occur.
    """
    binding = PbsXmlMemberBinding.model_validate(binding.model_dump())
    expected = build_pbs_xml_member_binding(archive_payload, parent)
    if binding != expected:
        raise ValueError("PBS member binding does not match parent/archive")
    if not binding.member_payload.matches(member_payload):
        raise ValueError("PBS member bytes do not match binding")
    return binding
