"""Reconcile each pinned PBS native field to one bounded meaning state."""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_domain_field_semantics import (
    DATE_PROFILE,
    qualify_pbs_domain_fields,
)
from global_medicines_atlas.pbs_observed_domain import load_observed_profile

PACKAGE = (
    "quality/qualifications/"
    "pbs-native-value-package-v2-20261022-39721534876.json"
)
SCREEN = (
    "quality/qualifications/"
    "pbs-native-reference-screen-20261022-39730665004.json"
)
REFERENCE_SCREEN = (
    "quality/qualifications/"
    "pbs-native-reference-screen-20261025-40103169910.json"
)
CONTEXT_SCREEN = (
    "quality/qualifications/"
    "pbs-native-reference-screen-20261025-40103169910.json"
)
DOMAIN = "quality/qualifications/pbs-domain-field-semantics-20261025-v2.json"
FIELD_STATE = (
    "quality/qualifications/pbs-native-silver-field-state-20261023.json"
)
REFERENCE_REVIEW = (
    "quality/qualifications/"
    "pbs-native-reference-meaning-review-20261025-40103169910.json"
)
REFERENCE_PACKET = (
    "quality/qualifications/"
    "pbs-native-reference-review-packet-20261025-40103169910.json"
)
PACKAGE_SHA256 = (
    "769a1d88ab52d6ed9ab08d07ce7d7b433dd7f9034e6b501ad30198a9b6e59202"
)
SCREEN_SHA256 = (
    "a1adda4e946365b98bf3febc03b9ae51acdae6db1569c7fc6606f8892c7ae48e"
)
REFERENCE_SCREEN_SHA256 = (
    "62a01d660dc8e59bcef39768f64a9deda10bc5a58ae899e3f138ec2816862722"
)
CONTEXT_SCREEN_SHA256 = (
    "7f223a138a89064c4dbdaad375174f5584cd0de1871dc34735167a3d670fe688"
)
CONTEXT_SCREEN_FILE_SHA256 = (
    "62a01d660dc8e59bcef39768f64a9deda10bc5a58ae899e3f138ec2816862722"
)
FIELD_STATE_SHA256 = (
    "2f35eebe45c0326dc80e76c461b0a8af23585923479cec8b74dcb9de5019120d"
)
REFERENCE_REVIEW_SHA256 = (
    "f8fd02dfdb1212ab35f8e60d7c449243398bdd0a706e5e96f08733293a79218d"
)
REFERENCE_PACKET_SHA256 = (
    "c38840116e821dffe5b06e5df14b1d7140f9e4446fbf8c14ea009a9e8b732829"
)
REFERENCE_PACKET_REPORT_SHA256 = (
    "885960352dcee9e70f12ac3aa843d5129b75a2c44b16263835ff5bc7b57a5c6b"
)
DATE_PROFILE_SHA256 = (
    "383f69a7e69e62527b07d45d0833ce21ccaea07e2d7a0b7fbc3d1b9a0f97ecfb"
)
DATE_OCCURRENCE_CROSSWALK = (
    "quality/qualifications/"
    "pbs-date-occurrence-crosswalk-20261025-40121732132.json"
)
DATE_OCCURRENCE_CROSSWALK_SHA256 = (
    "8eb6fee47f50b61ed93963d6261f5b1b7cbb366cdb5de9e8c4da3bac013cf592"
)
DATE_OCCURRENCE_CROSSWALK_REPORT_SHA256 = (
    "47b3806c8b28e5b38b3df8ad52fc91e86dc1d12d537a1a3496435d2f18c705c3"
)
SUPERSEDED_REPORT = (
    "quality/qualifications/"
    "pbs-native-silver-field-reconciliation-20261025-r10.json"
)
SUPERSEDED_REPORT_SHA256 = (
    "70980d3d10449e04bb57d602d12866fcbb0536bae88b2adb445b829c7d3c75a4"
)
SCREEN_RUN_ID = "40103169910"
SCREEN_WORKFLOW_COMMIT = "83465c87d5952e123cedd93a02b1ec9b4daa4eb4"
CONTEXT_SCREEN_RUN_ID = "40103169910"
CONTEXT_SCREEN_WORKFLOW_COMMIT = "83465c87d5952e123cedd93a02b1ec9b4daa4eb4"
CONTEXT_SCREEN_SOURCE_RECEIPT_SHA256 = (
    "a5eb06cf7e655eb0e0d8fe5d244297721ebede51e96c237333f7dffd76e1ccd1"
)
REFERENCE_FIELDS = 2_160_066
REFERENCE_KIND_COUNTS = {"rdf_resource": 1_167_610, "xlink_href": 992_456}
REFERENCE_STATUS_COUNTS = {
    "no_exact_literal": 73_577,
    "unique_exact_literal": 2_086_489,
}
REFERENCE_CONTEXT_SCHEMA_VERSION = 3
REFERENCE_CONTEXT_EXAMPLES_EMITTED = 46
REFERENCE_CONTEXT_EXAMPLE_POLICY = (
    "up_to_five_value_free_examples_per_structural_stratum"
)
REFERENCE_CONTEXT_EXAMPLE_POLICIES = {
    REFERENCE_CONTEXT_EXAMPLE_POLICY,
    "up_to_five_value_free_examples_per_stratum_with_equal_kind_budgets",
    "up_to_five_examples_per_stratum_with_equal_kind_status_budgets",
    "one_example_per_stratum_round_robin_by_kind_status",
}
DOMAIN_REPORT_SHA256 = (
    "9233d8d93126c929bde3e8b59486b4865f45c89f0d8370405cf6988cbfa0b5db"
)
SOURCE_FIELDS = 18_208_758
SOURCE_PATHS = 5_163
ITEM_DATE_FIELDS = 2_798
PATH_INVENTORY = (
    "quality/qualifications/pbs-schema-paths-20261022-39667604237.json"
)
CURRENT_RECONCILIATION = "quality/qualifications/pbs-native-silver-field-reconciliation-20261025-r11.json"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entity_path(schema_path: str) -> str:
    if "/attributes/" in schema_path:
        return schema_path.split("/attributes/", maxsplit=1)[0]
    if schema_path.endswith(("/text", "/tail")):
        return schema_path.rsplit("/", maxsplit=1)[0]
    raise ValueError("PBS schema path does not identify a native field")


PBS_QNAME = "{http://schema.pbs.gov.au/}"
XML_ID_QNAME = "{http://www.w3.org/XML/1998/namespace}id"
RDF_RESOURCE_QNAME = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"


def _path_qnames(schema_path: str) -> tuple[str, ...]:
    """Decode inventory JSON-pointer segments without inspecting source values."""
    return tuple(
        segment.replace("~1", "/").replace("~0", "~")
        for segment in schema_path.split("/")[1:]
    )


def _semantic_adjudication(schema_path: str) -> dict[str, str | None]:  # ruff: ignore[too-many-branches,too-many-return-statements] -- ordered path/QName allowlist keeps each adjudication independently auditable
    """Apply only exact PBS path/QName decisions supported by the contract."""
    names = _path_qnames(schema_path)
    entity = names[:-2] if names[-2] == "attributes" else names[:-1]
    slot = names[-1]
    item_path = (
        PBS_QNAME + "root",
        PBS_QNAME + "pharmaceutical-items-list",
        PBS_QNAME + "pharmaceutical-item",
    )
    if names[:3] == item_path and names[3:5] == ("attributes", XML_ID_QNAME):
        return {
            "state": "interpreted",
            "domain": "item_identity_literal",
            "meaning": "source pharmaceutical-item XML identifier literal",
            "rule": "exact pinned item QName ancestry plus xml:id attribute QName",
        }
    if names == (
        *item_path,
        PBS_QNAME + "effective",
        PBS_QNAME + "date",
        "text",
    ):
        return {
            "state": "interpreted",
            "domain": "item_effective_date_literal",
            "meaning": "source PBS item effective-date literal; temporal role only",
            "rule": "exact pinned pharmaceutical-item/effective/date/text QName path and qualified v3 date-role receipt",
        }
    if (
        names[:2] == (PBS_QNAME + "root", PBS_QNAME + "drugs-list")
        and slot == "text"
        and (
            entity[-2:]
            in {
                (PBS_QNAME + "tpp", PBS_QNAME + "brand-name"),
                (PBS_QNAME + "tpuu", PBS_QNAME + "brand-name"),
            }
            or entity[-3:]
            in {
                (
                    PBS_QNAME + "tpp",
                    PBS_QNAME + "brand-name",
                    PBS_QNAME + "value",
                ),
                (
                    PBS_QNAME + "tpuu",
                    PBS_QNAME + "brand-name",
                    PBS_QNAME + "value",
                ),
            }
        )
    ):
        return {
            "state": "interpreted",
            "domain": "product_presentation_label",
            "meaning": "source brand-name presentation label text",
            "rule": "exact PBS drugs-list tpp/tpuu brand-name QName ancestry",
        }
    reference_path = (
        PBS_QNAME + "drug-references-list",
        PBS_QNAME + "mp-reference",
        PBS_QNAME + "code",
    )
    is_current_reference_path = (
        len(entity) >= len(reference_path)
        and entity[-len(reference_path) :] == reference_path
        and names[0] == PBS_QNAME + "root"
        and PBS_QNAME + "previous-list" not in entity
        and (
            PBS_QNAME + "pharmaceutical-item" in entity
            or PBS_QNAME + "drugs-list" in entity
        )
    )
    if slot == "text" and is_current_reference_path:
        return {
            "state": "interpreted",
            "domain": "amt_literal_reference",
            "meaning": "source-local AMT reference code literal",
            "rule": "exact drug-references-list/mp-reference/code text QName path",
        }
    if slot == RDF_RESOURCE_QNAME and is_current_reference_path:
        return {
            "state": "interpreted",
            "domain": "amt_literal_reference_resource",
            "meaning": "source-local RDF resource literal attached to an AMT reference",
            "rule": "exact AMT code element plus RDF resource attribute QName",
        }
    if slot == "text" and entity[-1:] == (PBS_QNAME + "amount",):
        if PBS_QNAME + "contribution" in entity:
            return {
                "state": "interpreted",
                "domain": "pbs_patient_contribution_dollar_amount",
                "meaning": (
                    "source PBS dollar amount nested under a contribution "
                    "element defined for patient contributions to drug and "
                    "brand prices; source role only"
                ),
                "rule": (
                    "exact PBS amount/text QName and contribution ancestry; "
                    "official PBS XML v3.1.9 amount and contribution definitions"
                ),
            }
        if PBS_QNAME + "price" in entity:
            return {
                "state": "interpreted",
                "domain": "pbs_product_price_dollar_amount",
                "meaning": (
                    "source PBS dollar amount within a product price "
                    "structure; source role only"
                ),
                "rule": (
                    "exact PBS amount/text QName and price ancestry; official "
                    "PBS XML v3.1.9 price and amount definitions"
                ),
            }
        return {
            "state": "interpreted",
            "domain": "pbs_dollar_amount",
            "meaning": (
                "source PBS amount element content defined as a dollar "
                "value; source role only"
            ),
            "rule": "exact PBS amount/text QName and official PBS XML v3.1.9 amount definition",
        }
    if (
        PBS_QNAME + "classification" in entity
        and entity[-1:] == (PBS_QNAME + "code",)
        and slot == "text"
    ):
        return {
            "state": "native_unresolved",
            "domain": "classification_code_candidate",
            "meaning": None,
            "rule": "classification/code path is visible, but this value-free inventory cannot bind its unqualified type attribute value ATC",
        }
    restriction_entity = (
        PBS_QNAME + "root",
        PBS_QNAME + "prescribing-texts-list",
        PBS_QNAME + "restriction",
    )
    restriction_index = (
        entity.index(PBS_QNAME + "restriction")
        if PBS_QNAME + "restriction" in entity
        else None
    )
    if entity == restriction_entity and slot in {"text", "tail"}:
        return {
            "state": "interpreted",
            "domain": "restriction_text",
            "meaning": (
                "native text within the source PBS restriction, defined as "
                "the reason for subsidisation including indications and "
                "criteria; source role only"
            ),
            "rule": (
                "exact direct text or tail slot on the pinned PBS "
                "prescribing-texts restriction QName path and official "
                "PBS XML v3.1.9 restriction definition"
            ),
        }
    if (
        restriction_index is not None
        and PBS_QNAME + "previous-list" not in entity
    ):
        if (
            slot == "text"
            and entity[-3:]
            == (
                PBS_QNAME + "restriction",
                PBS_QNAME + "effective",
                PBS_QNAME + "date",
            )
            and restriction_index == len(entity) - 3
        ):
            return {
                "state": "interpreted",
                "domain": "restriction_effective_date_literal",
                "meaning": "source date literal attached beneath this restriction's effective element",
                "rule": "exact direct PBS restriction/effective/date/text QName path; reference-nested dates excluded",
            }
        if (
            names[-2:] == ("attributes", "effective-date")
            and entity == names[: restriction_index + 1]
        ):
            return {
                "state": "interpreted",
                "domain": "restriction_effective_date_literal",
                "meaning": "date literal attached to this source restriction",
                "rule": "effective-date attribute on an exact non-historical PBS restriction QName",
            }
    if names == (
        PBS_QNAME + "root",
        PBS_QNAME + "schedule",
        "attributes",
        "effective-date",
    ):
        return {
            "state": "interpreted",
            "domain": "schedule_effective_date_literal",
            "meaning": "PBS schedule-level effective-date literal",
            "rule": "exact root/schedule/effective-date attribute QName path",
        }
    if names == (
        PBS_QNAME + "root",
        PBS_QNAME + "info",
        "{http://purl.org/dc/terms/}valid",
        "text",
    ):
        return {
            "state": "interpreted",
            "domain": "schedule_metadata_valid_date_literal",
            "meaning": "source document-level dcterms:valid date literal",
            "rule": "exact root/info/DCTERMS valid text QName path; distinct from schedule effective date",
        }
    return {
        "state": "native_unresolved",
        "domain": None,
        "meaning": None,
        "rule": "no exact path/QName semantic rule established",
    }


def _context_screen_matches(
    context_screen: dict[str, Any], *, schema_version: int
) -> bool:
    diagnostic_flags = (
        "uri_resolution_performed",
        "literal_values_emitted",
        "raw_source_emitted",
        "semantic_relationships_qualified",
    )
    return (
        context_screen["schema_version"] == schema_version
        and context_screen["example_selection_policy"]
        in REFERENCE_CONTEXT_EXAMPLE_POLICIES
        and context_screen["reference_occurrences"] == REFERENCE_FIELDS
        and all(context_screen[flag] is False for flag in diagnostic_flags)
        and context_screen["external_targets_fetched"] == 0
    )


def _context_payload(context_report: dict[str, Any]) -> dict[str, Any]:
    """Decode the workflow's explicitly value-free structural context."""
    context = context_report["qualification"]["reference_context"]
    return json.loads(
        zlib.decompress(base64.b64decode(context["payload"], validate=True))
    )


def _context_sample_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize only value-free structural diagnostics from the bounded sample."""
    examples = [
        example
        for stratum in payload["strata"]
        for example in stratum["examples"]
    ]
    qnames = {example["predicate_element"]["qname"] for example in examples}
    sampled_kinds = {
        "rdf_resource": sum(
            example["reference_occurrence"].endswith(
                "/attributes/"
                "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
            )
            for example in examples
        ),
        "xlink_href": sum(
            example["reference_occurrence"].endswith(
                "/attributes/{http:~1~1www.w3.org~11999~1xlink}href"
            )
            for example in examples
        ),
    }
    return {
        "examples_emitted": len(examples),
        "no_exact_literal": sum(
            example["target_multiplicity"] == 0 for example in examples
        ),
        "unique_exact_literal": sum(
            example["target_multiplicity"] == 1 for example in examples
        ),
        "sampled_reference_kind_counts": {
            kind: count for kind, count in sampled_kinds.items() if count
        },
        "distinct_predicate_qname_count": len(qnames),
        "nearest_subject_elements": sum(
            example["nearest_subject_element"] is not None
            for example in examples
        ),
    }


def reconcile_pbs_field_states(root: Path) -> dict[str, Any]:  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- exact receipt bindings and path-level partition are auditable together
    """Assign every field occurrence once; retain unqualified values as native."""
    package_path = root / PACKAGE
    date_profile_path = root / DATE_PROFILE
    date_occurrence_crosswalk_path = root / DATE_OCCURRENCE_CROSSWALK
    screen_path = root / SCREEN
    reference_screen_path = root / REFERENCE_SCREEN
    context_screen_path = root / CONTEXT_SCREEN
    field_state_path = root / FIELD_STATE
    reference_review_path = root / REFERENCE_REVIEW
    reference_packet_path = root / REFERENCE_PACKET
    domain_path = root / DOMAIN
    package_sha = _file_sha256(package_path)
    date_profile_sha = _file_sha256(date_profile_path)
    date_occurrence_crosswalk_sha = _file_sha256(date_occurrence_crosswalk_path)
    screen_sha = _file_sha256(screen_path)
    reference_screen_sha = _file_sha256(reference_screen_path)
    context_screen_file_sha = _file_sha256(context_screen_path)
    field_state_sha = _file_sha256(field_state_path)
    reference_review_sha = _file_sha256(reference_review_path)
    reference_packet_sha = _file_sha256(reference_packet_path)
    superseded_report_sha = _file_sha256(root / SUPERSEDED_REPORT)
    digest_pairs = (
        (package_sha, PACKAGE_SHA256),
        (screen_sha, SCREEN_SHA256),
        (reference_screen_sha, REFERENCE_SCREEN_SHA256),
        (field_state_sha, FIELD_STATE_SHA256),
        (reference_review_sha, REFERENCE_REVIEW_SHA256),
        (reference_packet_sha, REFERENCE_PACKET_SHA256),
        (superseded_report_sha, SUPERSEDED_REPORT_SHA256),
    )
    if any(actual != expected for actual, expected in digest_pairs):
        raise ValueError("PBS field evidence receipt digest differs")
    if date_profile_sha != DATE_PROFILE_SHA256:
        raise ValueError("PBS exact-source date-profile receipt differs")
    if date_occurrence_crosswalk_sha != DATE_OCCURRENCE_CROSSWALK_SHA256:
        raise ValueError("PBS exact-source date occurrence crosswalk differs")
    date_profile = json.loads(date_profile_path.read_bytes())
    date_source = date_profile["source"]
    date_roles = date_profile["date_profile"]["role_counts"]
    date_profile_binding = (
        date_profile["status"],
        date_profile["date_profile"]["profile_id"],
        date_profile["date_profile"]["format"],
        date_source["member_sha256"],
        date_source["native_digest"],
        date_roles.get("pbs_effective_date"),
    )
    if date_profile_binding != (
        "exact_source_date_profile_qualified",
        "pbs-v3-pinned-2026-04-01-v1",
        "XSD YYYY-MM-DD",
        "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
        "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25",
        ITEM_DATE_FIELDS,
    ):
        raise ValueError("PBS exact-source item date role differs")
    date_crosswalk_envelope = json.loads(
        date_occurrence_crosswalk_path.read_bytes()
    )
    date_crosswalk_report = date_crosswalk_envelope["report"]
    date_crosswalk = date_crosswalk_report["crosswalk"]
    date_crosswalk_join = date_crosswalk["join"]
    date_crosswalk_binding = (
        date_crosswalk_report["status"],
        date_crosswalk_report["run_id"],
        date_crosswalk_report["workflow_commit"],
        date_crosswalk_envelope["report_sha256"],
        date_crosswalk_report["source"]["member_sha256"],
        date_crosswalk_report["source"]["native_digest"],
        date_crosswalk_join["identity"],
        date_crosswalk_join["item_profile_only_fields"],
        date_crosswalk_join["restriction_only_fields"],
        date_crosswalk_join["overlap_fields"],
        date_crosswalk["date_role_slots_without_source_field"],
    )
    if date_crosswalk_binding != (
        "passed",
        "40121732132",
        "a91ce7f994391a6d7aae182618c92049fcf088d2",
        DATE_OCCURRENCE_CROSSWALK_REPORT_SHA256,
        "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
        "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25",
        "source_field_id_exact_match",
        ITEM_DATE_FIELDS,
        3_028,
        0,
        0,
    ):
        raise ValueError("PBS exact-source date occurrence crosswalk differs")
    context_envelope = json.loads(context_screen_path.read_bytes())
    context_report = context_envelope["report"]
    context_canonical = json.dumps(
        context_report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    context_qualification = context_report["qualification"]
    context_reference = context_qualification["reference_context"]
    context_payload = _context_payload(context_report)
    context_screen_flags_valid = (
        context_qualification["domain_semantics_qualified"] is False
        and context_qualification["semantic_relationships_qualified"] is False
        and context_qualification["native_values_emitted"] is False
        and context_qualification["external_targets_fetched"] == 0
        and context_qualification["new_sources"] == 0
        and context_qualification["new_admissions"] == 0
        and context_qualification["publications"] == 0
        and context_qualification["reference_fields"] == REFERENCE_FIELDS
        and context_report["status"] == "passed"
        and context_report["run_id"] == CONTEXT_SCREEN_RUN_ID
        and context_report["workflow_commit"] == CONTEXT_SCREEN_WORKFLOW_COMMIT
        and context_report["source_receipt_file_sha256"]
        == CONTEXT_SCREEN_SOURCE_RECEIPT_SHA256
        and context_report["revision"]
        == "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
        and context_qualification["member_sha256"]
        == "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
        and context_qualification["native_fields"] == SOURCE_FIELDS
        and context_qualification["archive_sha256"]
        == "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
        and context_payload["schema_version"]
        == REFERENCE_CONTEXT_SCHEMA_VERSION
        and context_reference["payload_sha256"]
        == "8aa9c594b881c478a177e803a886ad591ae93ec9d965f4ba629ac58dd5902e34"
        and _context_screen_matches(
            context_payload, schema_version=REFERENCE_CONTEXT_SCHEMA_VERSION
        )
        and context_payload["literal_values_emitted"] is False
        and context_payload["raw_source_emitted"] is False
        and context_payload["semantic_relationships_qualified"] is False
        and context_payload["uri_resolution_performed"] is False
        and context_payload["uri_resolution_screen_performed"] is True
    )
    if (
        context_screen_file_sha != CONTEXT_SCREEN_FILE_SHA256
        or hashlib.sha256(context_canonical).hexdigest()
        != CONTEXT_SCREEN_SHA256
        or context_envelope["report_sha256"] != CONTEXT_SCREEN_SHA256
        or not context_screen_flags_valid
    ):
        raise ValueError("PBS source-context screen receipt differs")
    context_sample = _context_sample_summary(context_payload)
    if context_sample != {
        "examples_emitted": 46,
        "no_exact_literal": 11,
        "unique_exact_literal": 35,
        "sampled_reference_kind_counts": {
            "rdf_resource": 29,
            "xlink_href": 17,
        },
        "distinct_predicate_qname_count": 17,
        "nearest_subject_elements": 8,
    }:
        raise ValueError("PBS source-context sample summary differs")
    native = json.loads(field_state_path.read_bytes())
    if (
        native["status"] != "passed"
        or native["field_state_coverage"]["source_fields"] != SOURCE_FIELDS
        or native["package_receipt_sha256"] != package_sha
        or native["screen_receipt_sha256"] != screen_sha
    ):
        raise ValueError("PBS native field-state receipt differs")

    domain_envelope = json.loads(domain_path.read_bytes())
    domain_report = domain_envelope["report"]
    canonical = json.dumps(
        domain_report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if (
        hashlib.sha256(canonical).hexdigest()
        != domain_envelope["report_sha256"]
        or domain_envelope["report_sha256"] != DOMAIN_REPORT_SHA256
    ):
        raise ValueError("PBS field-meaning evidence digest differs")
    if qualify_pbs_domain_fields(root) != domain_report:
        raise ValueError(
            "PBS field-meaning report differs from its source evidence"
        )

    screen_envelope = json.loads(reference_screen_path.read_bytes())
    screen_report = screen_envelope["report"]
    screen_qualification = screen_report["qualification"]
    reference_envelope = json.loads(reference_review_path.read_bytes())
    reference_review = reference_envelope["report"]
    packet_envelope = json.loads(reference_packet_path.read_bytes())
    reference_packet = packet_envelope["report"]
    packet_canonical = json.dumps(
        reference_packet,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    screen_kind_counts = screen_qualification["reference_kind_counts"]
    screen_kind_status_counts = screen_qualification[
        "reference_kind_status_counts"
    ]
    review_kind_counts = reference_review["exact_source_screen"]["per_kind"]
    reference_canonical = json.dumps(
        reference_review,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    screen_source_matches = (
        screen_qualification["member_sha256"]
        == domain_report["source"]["member_sha256"]
        and screen_qualification["native_fields"] == SOURCE_FIELDS
        and screen_qualification["semantic_relationships_qualified"] is False
        and screen_report["run_id"] == SCREEN_RUN_ID
        and screen_report["workflow_commit"] == SCREEN_WORKFLOW_COMMIT
    )
    context_source_matches = (
        context_report["dataset"] == native["dataset"]
        and context_report["revision"] == native["revision"]
        and context_report["source_receipt_file_sha256"]
        == screen_report["source_receipt_file_sha256"]
        and context_qualification["archive_sha256"]
        == native["candidate_output"]["archive_sha256"]
        and context_qualification["member_sha256"]
        == native["candidate_output"]["member_sha256"]
        and context_qualification["native_fields"] == SOURCE_FIELDS
    )
    screen_denominators_match = (
        screen_qualification["reference_fields"] == REFERENCE_FIELDS
        and screen_qualification["reference_kind_counts"]
        == REFERENCE_KIND_COUNTS
        and screen_qualification["reference_status_counts"]
        == REFERENCE_STATUS_COUNTS
    )
    reference_digest_matches = (
        hashlib.sha256(reference_canonical).hexdigest()
        == reference_envelope["report_sha256"]
    )
    reference_source_matches = (
        reference_review["source"]["member_sha256"]
        == domain_report["source"]["member_sha256"]
        and reference_review["source"]["native_digest"]
        == domain_report["source"]["native_digest"]
        and reference_review["source"]["native_fields"] == SOURCE_FIELDS
        and reference_review["source"]["screen_receipt_sha256"]
        == reference_screen_sha
        and reference_review["source"]["screen_run_id"] == SCREEN_RUN_ID
        and reference_review["source"]["screen_workflow_commit"]
        == SCREEN_WORKFLOW_COMMIT
        and reference_review["source"]["screen_source_receipt_sha256"]
        == screen_report["source_receipt_file_sha256"]
    )
    reference_kinds_match = (
        reference_review["exact_source_screen"][
            "per_kind_match_counts_available"
        ]
        and set(review_kind_counts) == set(screen_kind_counts)
        and all(
            review_kind_counts[kind]["reference_fields"]
            == screen_kind_counts[kind]
            and review_kind_counts[kind]["semantic_links_qualified"] is False
            and review_kind_counts[kind]["status_counts"]
            == screen_kind_status_counts[kind]
            for kind in screen_kind_counts
        )
    )
    review_context_screen = reference_review["source_context_screen"]
    if not all((
        screen_source_matches,
        context_source_matches,
        screen_denominators_match,
        reference_digest_matches,
        reference_source_matches,
        reference_kinds_match,
        reference_review["scope"]["semantic_relationships_qualified"] is False,
        isinstance(review_context_screen, dict)
        and _context_screen_matches(
            cast("dict[str, Any]", review_context_screen),
            schema_version=REFERENCE_CONTEXT_SCHEMA_VERSION,
        ),
        hashlib.sha256(packet_canonical).hexdigest()
        == packet_envelope["report_sha256"]
        == REFERENCE_PACKET_REPORT_SHA256,
        reference_packet["source"]["screen_receipt_sha256"]
        == reference_screen_sha,
        reference_packet["source"]["screen_run_id"] == SCREEN_RUN_ID,
        reference_packet["source"]["screen_workflow_commit"]
        == SCREEN_WORKFLOW_COMMIT,
        reference_packet["screen_denominator"] == REFERENCE_FIELDS,
        reference_packet["status"]
        == "source_context_examples_unreviewed_semantic_links_unqualified",
        reference_packet["sampling_method"]
        == "deterministic source-order examples within context strata; not a probability sample",
        reference_packet["context_examples_emitted"]
        == REFERENCE_CONTEXT_EXAMPLES_EMITTED,
        reference_packet["context_examples_omitted"]
        == REFERENCE_FIELDS - REFERENCE_CONTEXT_EXAMPLES_EMITTED,
        len(reference_packet["cases"]) == REFERENCE_CONTEXT_EXAMPLES_EMITTED,
        reference_packet["candidate_occurrences_by_category"]
        == {
            "no_target_negative_control": 73_577,
            "unique_fragment_literal_candidate": 992_456,
            "unique_literal_candidate_requires_uri_review": 1_094_033,
        },
        reference_packet["scope"]["new_sources"] == 0,
        reference_packet["scope"]["new_admissions"] == 0,
        reference_packet["scope"]["publications"] == 0,
        reference_packet["scope"]["consumer_canaries"] == 0,
        reference_packet["scope"]["raw_source_emitted"] is False,
        reference_packet["scope"]["source_values_emitted"] is False,
        all(
            case["adjudication"] == "unreviewed"
            and case["semantic_relationship_qualified"] is False
            for case in reference_packet["cases"]
        ),
        reference_packet["scope"]["semantic_relationships_qualified"] is False,
    )):
        raise ValueError("PBS source-local reference review differs")

    observed_path = (
        root
        / "quality/qualifications/pbs-observed-domain-values-qualification-20261022-39672588063.json"
    )
    observed_envelope = json.loads(observed_path.read_bytes())
    observed_report = observed_envelope["report"]
    observed_canonical = json.dumps(
        observed_report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if (
        hashlib.sha256(observed_canonical).hexdigest()
        != observed_envelope["report_sha256"]
    ):
        raise ValueError("PBS observed-role receipt digest differs")
    observed_qualification = observed_report["qualification"]
    role_counts = observed_qualification["role_field_counts"]
    profile = load_observed_profile(root)
    roles = {
        "items": "interpreted",
        "products": "interpreted",
        "restrictions": "interpreted",
        "prescribing_rules": "interpreted",
        "prices": "interpreted",
        "pricing_components": "interpreted",
        "historical_records": "native_unresolved",
        "organisations": "native_unresolved",
        "references": "native_unresolved",
        "schedules": "native_unresolved",
        "vocabulary_metadata": "native_unresolved",
    }
    if (
        set(role_counts) != set(roles)
        or sum(role_counts.values()) != SOURCE_FIELDS
    ):
        raise ValueError("PBS source role partition does not close")

    meanings = domain_report["domains"]
    expected = {
        "items": meanings["item"]["field_count"],
        "products": meanings["product"]["field_count"],
        "restrictions": role_counts["restrictions"],
        "prescribing_rules": role_counts["prescribing_rules"],
        "prices": role_counts["prices"],
        "pricing_components": role_counts["pricing_components"],
    }
    if (
        expected["items"] != role_counts["items"]
        or expected["products"] != role_counts["products"]
        or meanings["restriction"]["field_count"]
        != role_counts["restrictions"] + role_counts["prescribing_rules"]
        or meanings["price"]["field_count"]
        != role_counts["prices"] + role_counts["pricing_components"]
    ):
        raise ValueError(
            "PBS interpreted role counts differ from meaning evidence"
        )

    # Structural role destinations are useful table routing metadata, not
    # semantic interpretations. Recount the actual source fields only after
    # exact path/QName adjudication below.
    interpreted = 0
    unresolved = 0
    unavailable = 0

    meaning_for_role = {
        "items": "item",
        "products": "product",
        "restrictions": "restriction",
        "prescribing_rules": "restriction",
        "prices": "price",
        "pricing_components": "price",
    }
    state_rows = {}
    for name, state in roles.items():
        evidence_key = meaning_for_role.get(name)
        meaning = meanings[evidence_key] if evidence_key is not None else None
        reference_evidence = (
            {
                "profile": reference_review["profile_id"],
                "status": reference_review["status"],
                "source": reference_review["source"],
                "reference_kinds": reference_review["reference_kinds"],
                "exact_source_screen": reference_review["exact_source_screen"],
                "calibration": reference_review["calibration"],
                "semantic_relationships_qualified": False,
            }
            if name == "references"
            else None
        )
        state_rows[name] = {
            "field_count": role_counts[name],
            "structural_state": (
                "structural_destination_mapped"
                if state == "interpreted"
                else "unmapped_native"
            ),
            "structural_meaning": (
                meaning["meaning"]
                if meaning is not None
                else (
                    "source-local reference literals; target relationships unresolved"
                    if name == "references"
                    else None
                )
            ),
            "structural_evidence": (
                {
                    "evidence_kind": "structural_destination_only",
                    "profile": "pbs-v3-pinned-2026-04-01-domain-fields-v1",
                    "domain": evidence_key,
                    "status": meaning["status"],
                    "source": domain_report["source"],
                    "basis": domain_report["meaning_basis"],
                    "limits": meaning["limits"],
                    "value_interpretation": False,
                }
                if meaning is not None
                else reference_evidence
            ),
        }
    path_inventory = json.loads((root / PATH_INVENTORY).read_bytes())
    path_reconciliation: list[dict[str, Any]] = []
    path_role_counts: dict[str, int] = {}
    for path_row in path_inventory["paths"]:
        role = profile.roles.get(
            _entity_path(path_row["schema_path"]), "unmapped"
        )
        state = roles.get(role, "native_unresolved")
        adjudication = _semantic_adjudication(path_row["schema_path"])
        if adjudication["state"] == "interpreted":
            interpreted += path_row["native_fields"]
        else:
            unresolved += path_row["native_fields"]
        path_reconciliation.append({
            "schema_path": path_row["schema_path"],
            "field_count": path_row["native_fields"],
            "role": role,
            "structural_state": (
                "structural_destination_mapped"
                if state == "interpreted"
                else "unmapped_native"
            ),
            "semantic_state": adjudication["state"],
            "semantic_interpretation": adjudication,
        })
        path_role_counts[role] = (
            path_role_counts.get(role, 0) + path_row["native_fields"]
        )
    if (
        len(path_reconciliation) != SOURCE_PATHS
        or path_role_counts != role_counts
        or sum(row["field_count"] for row in path_reconciliation)
        != SOURCE_FIELDS
        or sum(
            row["field_count"]
            for row in path_reconciliation
            if row["semantic_interpretation"]["domain"]
            == "item_effective_date_literal"
        )
        != ITEM_DATE_FIELDS
    ):
        raise ValueError("PBS schema-path field-state partition does not close")
    return {
        "schema_id": "global-medicines-atlas.pbs-field-state-reconciliation",
        "schema_version": 1,
        "profile_id": "pbs-v3-2026-04-01-field-state-v2",
        "status": "complete_field_denominator_path_adjudication_with_unresolved_semantics",
        "domain_semantics_qualified": False,
        "rights_conclusion_changed": False,
        "source": {
            "dataset": native["dataset"],
            "revision": native["revision"],
            "member_sha256": native["candidate_output"]["member_sha256"],
            "native_digest": native["candidate_output"]["native_core_sha256"],
            "source_fields": SOURCE_FIELDS,
            "package_receipt_sha256": package_sha,
            "screen_receipt_sha256": screen_sha,
            "reference_screen_receipt_sha256": reference_screen_sha,
            "reference_screen_run_id": SCREEN_RUN_ID,
            "reference_screen_workflow_commit": SCREEN_WORKFLOW_COMMIT,
            "reference_context_screen_receipt_sha256": CONTEXT_SCREEN_SHA256,
            "reference_context_screen_file_sha256": context_screen_file_sha,
            "reference_context_screen_run_id": CONTEXT_SCREEN_RUN_ID,
            "reference_context_screen_workflow_commit": (
                CONTEXT_SCREEN_WORKFLOW_COMMIT
            ),
            "reference_context_screen_source_receipt_sha256": (
                CONTEXT_SCREEN_SOURCE_RECEIPT_SHA256
            ),
            "prior_field_state_receipt_sha256": field_state_sha,
            "domain_semantics_report_sha256": domain_envelope["report_sha256"],
            "reference_meaning_report_sha256": reference_envelope[
                "report_sha256"
            ],
            "observed_roles_report_sha256": observed_envelope["report_sha256"],
        },
        "field_state_coverage": {
            "interpreted": interpreted,
            "native_unresolved": unresolved,
            "unavailable": unavailable,
            "source_fields": SOURCE_FIELDS,
            "denominator_closed": True,
            "all_native_values_remain_unresolved": True,
            "semantic_field_states_distinct_from_structural_destinations": True,
        },
        "role_reconciliation": state_rows,
        "path_reconciliation": path_reconciliation,
        "semantic_adjudication": {
            "profile_id": "pbs-v3-pinned-2026-04-01-path-qname-adjudication-v3",
            "inventory_sha256": "6da85f3e3526a52dca7b0f41206b5ec1afde854f89d858ae659867827219408b",
            "date_profile_sha256": date_profile_sha,
            "date_profile_item_effective_date_fields": date_roles[
                "pbs_effective_date"
            ],
            "date_occurrence_crosswalk": {
                "path": DATE_OCCURRENCE_CROSSWALK,
                "file_sha256": date_occurrence_crosswalk_sha,
                "report_sha256": date_crosswalk_envelope["report_sha256"],
                "workflow_run_id": date_crosswalk_report["run_id"],
                "workflow_commit": date_crosswalk_report["workflow_commit"],
                "identity": date_crosswalk_join["identity"],
                "item_profile_only_fields": date_crosswalk_join[
                    "item_profile_only_fields"
                ],
                "restriction_only_fields": date_crosswalk_join[
                    "restriction_only_fields"
                ],
                "overlap_fields": date_crosswalk_join["overlap_fields"],
                "date_role_slots_without_source_field": date_crosswalk[
                    "date_role_slots_without_source_field"
                ],
                "source_values_emitted": False,
            },
            "source_values_read": False,
            "source_values_emitted": False,
            "field_count_conserved": interpreted + unresolved == SOURCE_FIELDS,
            "interpreted_fields": interpreted,
            "native_unresolved_fields": unresolved,
            "unavailable_fields": unavailable,
            "interpretations": {
                domain: sum(
                    row["field_count"]
                    for row in path_reconciliation
                    if row["semantic_interpretation"]["domain"] == domain
                )
                for domain in sorted({
                    row["semantic_interpretation"]["domain"]
                    for row in path_reconciliation
                    if row["semantic_interpretation"]["domain"] is not None
                })
            },
            "explicit_non_claims": [
                "AMT and RDF resource literals are not resolved to terminology concepts",
                "classification code is unresolved unless the exact unqualified type value ATC is evidenced; current path inventory does not preserve that attribute value",
                "native price values, explicit currency, units, status/currentness, and cross-era date effects remain unresolved",
                "item effective-date literals identify a source role only; they do not establish intervals, precedence, listing status, currentness, or cross-era equivalence",
                "the schedule effective-date path is not present in the pinned schema-path inventory; dcterms:valid is a separate document-level date",
                "the pinned inventory contains no classification/code text path, so fixture-level ATC typing is not a source-level assertion",
                "unknown wrappers and codes remain native_unresolved",
                "structural table destinations do not count as semantic interpretations",
            ],
        },
        "date_role_overlay": {
            "field_count": meanings["effective_date"]["field_count"]
            + meanings["document_valid_date"]["field_count"],
            "evidence_profile": "pbs-v3-pinned-2026-04-01-date-profile-v1",
            "item_effective_date_fields_in_semantic_partition": True,
            "counted_in_role_partition": True,
            "additive_to_denominator": False,
            "limits": meanings["effective_date"]["limits"]
            + meanings["document_valid_date"]["limits"],
        },
        "interpretation_evidence": {
            key: {
                "meaning": meanings[key]["meaning"],
                "field_count": meanings[key]["field_count"],
                "status": meanings[key]["status"],
                "limits": meanings[key]["limits"],
                "evidence": domain_report["meaning_basis"],
            }
            for key in ("item", "product", "restriction", "price")
        },
        "source_local_reference_review": {
            "report_sha256": reference_envelope["report_sha256"],
            "review_packet": {
                "path": REFERENCE_PACKET,
                "file_sha256": reference_packet_sha,
                "report_sha256": packet_envelope["report_sha256"],
                "cases": len(reference_packet["cases"]),
                "adjudicated_cases": 0,
                "semantic_relationships_qualified": False,
            },
            "reference_role_field_count": role_counts["references"],
            "screen_reference_denominator": reference_review[
                "exact_source_screen"
            ]["references"],
            "per_kind_screen": reference_review["exact_source_screen"][
                "per_kind"
            ],
            "context_screen": {
                "status": "value_free_context_screen_reconciled",
                "workflow_run_id": CONTEXT_SCREEN_RUN_ID,
                "workflow_commit": CONTEXT_SCREEN_WORKFLOW_COMMIT,
                "receipt_sha256": CONTEXT_SCREEN_SHA256,
                "receipt_file_sha256": context_screen_file_sha,
                "source_receipt_sha256": CONTEXT_SCREEN_SOURCE_RECEIPT_SHA256,
                "source_revision": context_report["revision"],
                "source_member_sha256": context_qualification["member_sha256"],
                "source_native_digest": native["candidate_output"][
                    "native_core_sha256"
                ],
                "schema_version": context_payload["schema_version"],
                "strata_count": context_payload["strata_count"],
                "examples_emitted": context_sample["examples_emitted"],
                "examples_omitted": context_payload["examples_omitted"],
                "sample_summary": context_sample,
                "external_targets_fetched": context_payload[
                    "external_targets_fetched"
                ],
                "uri_resolution_performed": context_payload[
                    "uri_resolution_performed"
                ],
                "uri_resolution_screen_performed": context_payload[
                    "uri_resolution_screen_performed"
                ],
                "unique_exact_literal_no_xml_base_candidates": (
                    context_payload[
                        "unique_exact_literal_no_xml_base_candidates"
                    ]
                ),
                "source_values_emitted": context_payload[
                    "literal_values_emitted"
                ],
                "semantic_relationships_qualified": False,
                "calibration_note": (
                    "The 46 deterministic value-free cases remain unreviewed; "
                    "the sample is not probability-based and cannot estimate "
                    "semantic match precision. Matcher behavior remains "
                    "unqualified."
                ),
            },
            "denominator_note": (
                "The schema-role field-state count and source reference-screen "
                "candidate count are separate measures."
            ),
            "semantic_relationships_qualified": False,
            "promotion_rule": reference_review["calibration"]["promotion_rule"],
        },
        "non_claims": {
            "cross_era_or_jurisdiction_pooling": False,
            "current_listing_status": False,
            "patient_rates": "unavailable: no patient-level numerator/denominator evidence in this source",
            "payable_benefit_or_patient_cost": False,
            "clinical_eligibility": False,
            "semantic_relationships": False,
            "new_sources": 0,
            "new_admissions": 0,
            "consumer_canaries": 0,
            "publications": 0,
        },
        "candidate_output": native["candidate_output"],
        "supersedes_report": {
            "path": SUPERSEDED_REPORT,
            "sha256": superseded_report_sha,
        },
    }
