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
    EXPECTED_RESTRICTION_DATE_FIELDS,
    qualify_pbs_domain_fields,
    qualify_pbs_domain_fields_v4,
    qualify_pbs_domain_fields_v5,
)
from global_medicines_atlas.pbs_observed_domain import load_observed_profile
from global_medicines_atlas.pbs_reference_case_adjudication import (
    ADJUDICATION_PATH,
    validate_reference_case_adjudication,
)

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
DOMAIN = "quality/qualifications/pbs-domain-field-semantics-20261025-v3.json"
DOMAIN_V4 = "quality/qualifications/pbs-domain-field-semantics-20261025-v4.json"
DOMAIN_V4_FILE_SHA256 = (
    "1336cd51392a08c29928cb66ae7f80a65589ceaa17b2c0c70f33c0d9a72c40c8"
)
DOMAIN_V4_REPORT_SHA256 = (
    "f2813888a484c0b36f4dbfbf967a418f07215f15c5379883789ecb8407fc18db"
)
REFERENCE_CASE_FILE_SHA256 = (
    "d0701afb167b20f3a67b89b9773e2db4d6ec41f8b9247eddff5a3a9c317e680f"
)
REFERENCE_CASE_REPORT_SHA256 = (
    "e61cf3c3b5744b23d5b68282414750d9322b2ae53fa18298eac60e5eb5384260"
)
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
    "pbs-native-silver-field-reconciliation-20261025-r12.json"
)
SUPERSEDED_REPORT_SHA256 = (
    "942db270550595c24486db48c5095bad92308dc7f7ac0a6afce3d4306232ada1"
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
    "ea11c97eff13051152fde6bf6c3be1788102e75b89662a38c9eb76712f21401a"
)
SOURCE_FIELDS = 18_208_758
SOURCE_PATHS = 5_163
ITEM_DATE_FIELDS = 2_798
PATH_INVENTORY = (
    "quality/qualifications/pbs-schema-paths-20261022-39667604237.json"
)
CURRENT_RECONCILIATION = "quality/qualifications/pbs-native-silver-field-reconciliation-20261025-r13.json"
DOMAIN_V5 = "quality/qualifications/pbs-domain-field-semantics-20261025-v5.json"
DOMAIN_V5_FILE_SHA256 = (
    "85dd2cd1e69971f0dd2093696798e87d1995ee86acaba2b55ee0a2c0fe905bac"
)
DOMAIN_V5_REPORT_SHA256 = (
    "3c06a7a09fced148dfaa672f759886c48875ecf25e561359161964962a40cc94"
)
CURRENT_RECONCILIATION_V5 = "quality/qualifications/pbs-native-silver-field-reconciliation-20261025-r14.json"
URI_SCREEN_V3 = (
    "quality/qualifications/"
    "pbs-native-reference-uri-screen-20261025-40120162365.json"
)
URI_SCREEN_V3_FILE_SHA256 = (
    "4a296004773c57d7c0a6d73aacc6fd67b052fc3e1900a96badb0948193a7b411"
)
URI_SCREEN_V3_REPORT_SHA256 = (
    "475655fd08abf4681908452ec9e76c6654904d697d10d702c6283c2490afde59"
)
URI_STRUCTURAL_REVIEW_V1 = (
    "quality/qualifications/"
    "pbs-native-uri-structural-review-20261025-40120162365.json"
)
URI_STRUCTURAL_REVIEW_V1_FILE_SHA256 = (
    "8e7c61609c84d19e2eaf9f127cff5943319760e2b98481b508b3e2f3bc74dd35"
)
URI_STRUCTURAL_REVIEW_V1_REPORT_SHA256 = (
    "b5834d4e86879c93818bfc49939423e5fbee103a7f40b5114f1f836cafc3b684"
)
CURRENT_RECONCILIATION_V6 = "quality/qualifications/pbs-native-silver-field-reconciliation-20261025-r15.json"
CURRENT_RECONCILIATION_V7 = "quality/qualifications/pbs-native-silver-field-reconciliation-20261028-r16.json"
CURRENT_RECONCILIATION_V8 = "quality/qualifications/pbs-native-silver-field-reconciliation-20261028-r17.json"
CURRENT_RECONCILIATION_V9 = "quality/qualifications/pbs-native-silver-field-reconciliation-20261028-r18.json"
PATH_INVENTORY_SHA256 = (
    "6da85f3e3526a52dca7b0f41206b5ec1afde854f89d858ae659867827219408b"
)
XLINK_FIELD_COUNT = 992_456
RDF_RESOURCE_FIELD_COUNT = 1_167_610
RDF_RESOURCE_PATH_COUNT = 370
AMT_REFERENCE_RESOURCE_FIELD_COUNT = 8_328
RDF_ABOUT_FIELD_COUNT = 10_368
RDF_ABOUT_PATH_COUNT = 34
XLINK_PATH_COUNT = 186
REFERENCE_REVIEW_CASE_COUNT = 46


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
RDF_ABOUT_QNAME = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
RDF_DOCUMENT_QNAME = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF"


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
    domain_v4_path = root / DOMAIN_V4
    package_sha = _file_sha256(package_path)
    date_profile_sha = _file_sha256(date_profile_path)
    date_occurrence_crosswalk_sha = _file_sha256(date_occurrence_crosswalk_path)
    screen_sha = _file_sha256(screen_path)
    reference_screen_sha = _file_sha256(reference_screen_path)
    context_screen_file_sha = _file_sha256(context_screen_path)
    field_state_sha = _file_sha256(field_state_path)
    reference_review_sha = _file_sha256(reference_review_path)
    reference_packet_sha = _file_sha256(reference_packet_path)
    domain_v4_sha = _file_sha256(domain_v4_path)
    superseded_report_sha = _file_sha256(root / SUPERSEDED_REPORT)
    digest_pairs = (
        (package_sha, PACKAGE_SHA256),
        (screen_sha, SCREEN_SHA256),
        (reference_screen_sha, REFERENCE_SCREEN_SHA256),
        (field_state_sha, FIELD_STATE_SHA256),
        (reference_review_sha, REFERENCE_REVIEW_SHA256),
        (reference_packet_sha, REFERENCE_PACKET_SHA256),
        (domain_v4_sha, DOMAIN_V4_FILE_SHA256),
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

    domain_v4_envelope = json.loads(domain_v4_path.read_bytes())
    domain_v4_report = domain_v4_envelope["report"]
    domain_v4_canonical = json.dumps(
        domain_v4_report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    domain_v4_digest_valid = (
        hashlib.sha256(domain_v4_canonical).hexdigest()
        == domain_v4_envelope["report_sha256"]
        == DOMAIN_V4_REPORT_SHA256
    )
    domain_v4_source_valid = (
        domain_v4_report["source"]["native_fields"] == SOURCE_FIELDS
        and domain_v4_report["source"]["member_sha256"]
        == domain_report["source"]["member_sha256"]
    )
    domain_v4_scope_valid = (
        domain_v4_report["scope"]["complete_domain_semantics_qualified"]
        is False
        and domain_v4_report["scope"]["source_values_emitted"] is False
    )
    if not (
        domain_v4_digest_valid
        and domain_v4_source_valid
        and domain_v4_scope_valid
    ):
        raise ValueError("PBS bounded domain-field v4 evidence differs")

    reference_case_path = root / ADJUDICATION_PATH
    reference_case_sha = _file_sha256(reference_case_path)
    if reference_case_sha != REFERENCE_CASE_FILE_SHA256:
        raise ValueError("PBS reference case receipt bytes differ")
    reference_case_report = validate_reference_case_adjudication(root)
    reference_case_envelope = json.loads(reference_case_path.read_bytes())
    if (
        reference_case_envelope["report_sha256"] != REFERENCE_CASE_REPORT_SHA256
        or reference_case_envelope["report"] != reference_case_report
        or reference_case_report["review_scope"]
        != {
            "case_count": 46,
            "structural_pointer_roles_supported": 46,
            "no_target_hard_negatives": 11,
            "semantic_relationships_qualified": False,
            "edges_emitted": False,
            "precision_claimed": False,
            "recall_claimed": False,
            "corpus_generalizable_match_quality_claimed": False,
            "admission_or_clinical_meaning_claimed": False,
            "meaning": "structural roles and exact member-scoped resolution only; no semantic relationship adjudication",
        }
    ):
        raise ValueError("PBS reference case review boundary differs")

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
    if qualify_pbs_domain_fields_v4(root) != domain_v4_report:
        raise ValueError("PBS bounded domain-field v4 evidence differs")

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
        "schema_version": 2,
        "profile_id": "pbs-v3-2026-04-01-field-state-v4",
        "status": "complete_field_partition_with_bounded_domain_semantics_and_unresolved_values",
        "domain_semantics_qualified": False,
        "bounded_domain_semantics_qualified": True,
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
            "domain_semantics_report_path": DOMAIN,
            "domain_semantics_v4_file_sha256": domain_v4_sha,
            "domain_semantics_v4_report_sha256": domain_v4_envelope[
                "report_sha256"
            ],
            "reference_case_receipt_file_sha256": reference_case_sha,
            "reference_case_receipt_report_sha256": reference_case_envelope[
                "report_sha256"
            ],
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
        "bounded_domain_semantics": {
            "path": DOMAIN_V4,
            "file_sha256": domain_v4_sha,
            "report_sha256": domain_v4_envelope["report_sha256"],
            "profile_id": domain_v4_report["profile_id"],
            "status": domain_v4_report["status"],
            "schema_version_evidence": domain_v4_report[
                "schema_version_evidence"
            ],
            "source_member_sha256": domain_v4_report["source"]["member_sha256"],
            "qualified_domains": {
                name: {
                    key: meaning.get(key)
                    for key in (
                        "status",
                        "meaning",
                        "field_count",
                        "entity_count",
                        "limits",
                    )
                    if key in meaning
                }
                for name, meaning in domain_v4_report["domains"].items()
            },
            "source_schema_field_meanings": domain_v4_report[
                "source_schema_field_meanings"
            ],
            "complete_domain_semantics_qualified": False,
            "counts_are_additive_to_field_partition": False,
            "field_state_partition": {
                "interpreted": interpreted,
                "native_unresolved": unresolved,
                "unavailable": unavailable,
                "source_fields": SOURCE_FIELDS,
                "newly_interpreted_native_value_fields": 0,
                "state_counts_changed": False,
                "all_native_values_remain_unresolved": True,
            },
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
            "structural_case_review": {
                "path": ADJUDICATION_PATH,
                "file_sha256": reference_case_sha,
                "report_sha256": reference_case_envelope["report_sha256"],
                "cases": reference_case_report["review_scope"]["case_count"],
                "structural_pointer_roles_supported": reference_case_report[
                    "review_scope"
                ]["structural_pointer_roles_supported"],
                "no_target_hard_negatives": reference_case_report[
                    "review_scope"
                ]["no_target_hard_negatives"],
                "semantic_relationships_qualified": False,
                "edges_emitted": False,
                "precision_claimed": False,
                "recall_claimed": False,
                "source_values_emitted": False,
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
                    "The 46 deterministic value-free cases have structural "
                    "pointer roles reviewed; semantic relationships remain "
                    "unreviewed. The sample is not probability-based and "
                    "cannot estimate semantic match precision. Matcher "
                    "behavior remains unqualified."
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


def reconcile_pbs_field_states_v5(root: Path) -> dict[str, Any]:
    """Add the bounded PBS direct-date grammar receipt without changing counts."""
    report = reconcile_pbs_field_states(root)
    path = root / DOMAIN_V5
    file_sha = _file_sha256(path)
    if file_sha != DOMAIN_V5_FILE_SHA256:
        raise ValueError("PBS domain-field v5 receipt bytes differ")
    envelope = json.loads(path.read_bytes())
    domain = envelope["report"]
    canonical = json.dumps(
        domain,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if (
        hashlib.sha256(canonical).hexdigest() != envelope["report_sha256"]
        or envelope["report_sha256"] != DOMAIN_V5_REPORT_SHA256
        or qualify_pbs_domain_fields_v5(root) != domain
        or domain["source"]["member_sha256"]
        != report["source"]["member_sha256"]
    ):
        raise ValueError(
            "PBS domain-field v5 report differs from source evidence"
        )
    date_grammar = domain["source_schema_field_meanings"][
        "restriction_effective_date_text"
    ]
    if (
        date_grammar["field_count"] != EXPECTED_RESTRICTION_DATE_FIELDS
        or date_grammar["archive_schema_patch_bound"] is not False
        or domain["scope"]["source_values_emitted"] is not False
    ):
        raise ValueError("PBS date grammar scope differs")
    report["profile_id"] = "pbs-v3-2026-04-01-field-state-v5"
    report["source"]["domain_semantics_v5_file_sha256"] = file_sha
    report["source"]["domain_semantics_v5_report_sha256"] = envelope[
        "report_sha256"
    ]
    report["bounded_domain_semantics_v5"] = {
        "path": DOMAIN_V5,
        "file_sha256": file_sha,
        "report_sha256": envelope["report_sha256"],
        "profile_id": domain["profile_id"],
        "qualified_lexical_grammar": {
            "source_schema_field": "restriction_effective_date_text",
            "field_count": date_grammar["field_count"],
            "grammar": date_grammar["lexical_grammar"],
            "archive_schema_version": date_grammar[
                "archive_declared_schema_version"
            ],
            "documentation_release": date_grammar[
                "grammar_documentation_release"
            ],
            "schema_patch_bound": date_grammar["archive_schema_patch_bound"],
            "native_values_validated": False,
        },
        "field_state_partition": {
            "interpreted": report["field_state_coverage"]["interpreted"],
            "native_unresolved": report["field_state_coverage"][
                "native_unresolved"
            ],
            "unavailable": report["field_state_coverage"]["unavailable"],
            "source_fields": report["field_state_coverage"]["source_fields"],
            "state_counts_changed": False,
            "newly_interpreted_native_value_fields": 0,
        },
        "complete_domain_semantics_qualified": False,
    }
    return report


def reconcile_pbs_field_states_v6(root: Path) -> dict[str, Any]:
    """Qualify exact same-member XLink targets in the field-state partition."""
    report = reconcile_pbs_field_states_v5(root)
    uri_path = root / URI_SCREEN_V3
    structural_path = root / URI_STRUCTURAL_REVIEW_V1
    uri_file_sha = _file_sha256(uri_path)
    structural_file_sha = _file_sha256(structural_path)
    if (
        uri_file_sha != URI_SCREEN_V3_FILE_SHA256
        or structural_file_sha != URI_STRUCTURAL_REVIEW_V1_FILE_SHA256
    ):
        raise ValueError("PBS XLink resolution evidence bytes differ")
    uri_envelope = json.loads(uri_path.read_bytes())
    uri = uri_envelope["report"]
    structural_envelope = json.loads(structural_path.read_bytes())
    structural = structural_envelope["report"]
    uri_binding_checks = (
        uri_envelope["report_sha256"] == URI_SCREEN_V3_REPORT_SHA256,
        uri["operation"] == "pbs-native-uri-screen",
        uri["member_sha256"] == report["source"]["member_sha256"],
        uri["qualification"]["uri_resolution_performed"] is True,
        uri["qualification"]["uri_values_emitted"] is False,
        uri["qualification"]["external_targets_fetched"] == 0,
        uri["qualification"]["reference_counts_by_qname"].get("xlink:href")
        == XLINK_FIELD_COUNT,
        uri["qualification"]["outcome_counts_by_qname"].get("xlink:href")
        == {"same_member_unique_id": XLINK_FIELD_COUNT},
    )
    structural_binding_checks = (
        structural_envelope["report_sha256"]
        == URI_STRUCTURAL_REVIEW_V1_REPORT_SHA256,
        structural["outcome_counts"]
        == {
            "same_member_unique_id": 17,
            "absolute_uri_unique_candidate": 18,
            "no_member_definition_negative_controls": 11,
        },
        structural["case_count"] == REFERENCE_REVIEW_CASE_COUNT,
        all(
            case["candidate_edge_emitted"] is not False
            for case in structural["cases"]
        )
        is False,
    )
    if not all(uri_binding_checks) or not all(structural_binding_checks):
        raise ValueError("PBS XLink resolution or calibration evidence differs")

    xlink_rows = [
        row
        for row in report["path_reconciliation"]
        if "{http:~1~1www.w3.org~11999~1xlink}href" in row["schema_path"]
    ]
    if (
        len(xlink_rows) != XLINK_PATH_COUNT
        or sum(row["field_count"] for row in xlink_rows) != XLINK_FIELD_COUNT
        or any(
            row["semantic_state"] != "native_unresolved" for row in xlink_rows
        )
    ):
        raise ValueError("PBS XLink path denominator or baseline differs")
    for row in xlink_rows:
        row["semantic_state"] = "interpreted"
        row["semantic_interpretation"] = {
            "domain": "source_local_xlink_link_target",
            "meaning": (
                "XLink href locator to a unique xml:id target in the exact "
                "pinned PBS member"
            ),
            "rule": "exact fragment URI resolution with one same-member XML ID target",
            "state": "interpreted",
            "target_count": row["field_count"],
            "source_values_emitted": False,
            "limits": [
                "qualifies only the generic XLink link target, not the PBS domain predicate or clinical meaning",
                "no edge payload was emitted by the aggregate URI screen",
                "applies only to the exact April 2026 PBS v3 member digest",
            ],
        }

    count = XLINK_FIELD_COUNT
    coverage = report["field_state_coverage"]
    coverage["interpreted"] += count
    coverage["native_unresolved"] -= count
    coverage["all_native_values_remain_unresolved"] = False
    report["semantic_adjudication"]["interpreted_fields"] += count
    report["semantic_adjudication"]["native_unresolved_fields"] -= count
    report["semantic_adjudication"]["interpretations"][
        "source_local_xlink_link_target"
    ] = count
    report["source"]["xlink_uri_screen_file_sha256"] = uri_file_sha
    report["source"]["xlink_uri_screen_report_sha256"] = uri_envelope[
        "report_sha256"
    ]
    report["source"]["xlink_structural_review_file_sha256"] = (
        structural_file_sha
    )
    report["source"]["xlink_structural_review_report_sha256"] = (
        structural_envelope["report_sha256"]
    )
    report["profile_id"] = "pbs-v3-2026-04-01-field-state-v6"
    report["status"] = (
        "complete_field_partition_with_bounded_domain_and_xlink_link_semantics"
    )
    report["source_local_xlink_link_semantics"] = {
        "status": "qualified_exact_same_member_unique_targets",
        "uri_screen_path": URI_SCREEN_V3,
        "uri_screen_file_sha256": uri_file_sha,
        "uri_screen_report_sha256": uri_envelope["report_sha256"],
        "xlink_href_fields": count,
        "same_member_unique_xml_id_targets": count,
        "other_xlink_outcomes": 0,
        "review_cases": 46,
        "reviewed_same_member_positive_examples": 17,
        "negative_control_cases": 11,
        "other_rdf_local_candidate_cases": 18,
        "probability_sample": False,
        "semantic_precision_or_recall_estimated": False,
        "generic_link_target_meaning_qualified": True,
        "pbs_predicate_or_clinical_meaning_qualified": False,
        "edge_payload_emitted": False,
        "source_values_emitted": False,
        "meaning_basis": [
            "https://www.w3.org/TR/xlink11/",
            URI_STRUCTURAL_REVIEW_V1,
        ],
        "field_state_partition_after_promotion": {
            "interpreted": coverage["interpreted"],
            "native_unresolved": coverage["native_unresolved"],
            "unavailable": coverage["unavailable"],
            "source_fields": coverage["source_fields"],
        },
        "limits": [
            "the 46 deterministic review cases do not estimate corpus-wide semantic precision or recall",
            "RDF resource references remain outside this qualification",
            "link target identity does not establish a PBS-specific predicate, medicine equivalence, eligibility, or clinical meaning",
        ],
    }
    return report


def reconcile_pbs_field_states_v7(root: Path) -> dict[str, Any]:
    """Qualify the generic RDF/XML rdf:resource field role, without links."""
    report = reconcile_pbs_field_states_v6(root)
    uri_path = root / URI_SCREEN_V3
    uri_file_sha = _file_sha256(uri_path)
    if uri_file_sha != URI_SCREEN_V3_FILE_SHA256:
        raise ValueError("PBS RDF resource screen evidence bytes differ")
    uri_envelope = json.loads(uri_path.read_bytes())
    uri = uri_envelope["report"]
    qualification = uri["qualification"]
    rdf_outcomes = qualification["outcome_counts_by_qname"].get(
        "rdf:resource", {}
    )
    rdf_screen_checks = (
        uri_envelope["report_sha256"] == URI_SCREEN_V3_REPORT_SHA256,
        uri["operation"] == "pbs-native-uri-screen",
        uri["member_sha256"] == report["source"]["member_sha256"],
        qualification["reference_counts_by_qname"].get("rdf:resource")
        == RDF_RESOURCE_FIELD_COUNT,
        rdf_outcomes
        == {
            "absolute_uri_no_member_definition": 73_577,
            "absolute_uri_unique_candidate": 1_094_033,
        },
        sum(rdf_outcomes.values()) == RDF_RESOURCE_FIELD_COUNT,
        qualification["uri_values_emitted"] is False,
        qualification["external_targets_fetched"] == 0,
        qualification["semantic_relationships_qualified"] is False,
        qualification["precision_claimed"] is False,
    )
    if not all(rdf_screen_checks):
        raise ValueError("PBS RDF resource screen qualification differs")

    rdf_rows = [
        row
        for row in report["path_reconciliation"]
        if "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
        in row["schema_path"]
    ]
    if (
        len(rdf_rows) != RDF_RESOURCE_PATH_COUNT
        or sum(row["field_count"] for row in rdf_rows)
        != RDF_RESOURCE_FIELD_COUNT
        or sum(
            row["field_count"]
            for row in rdf_rows
            if row["semantic_interpretation"]["domain"]
            == "amt_literal_reference_resource"
        )
        != AMT_REFERENCE_RESOURCE_FIELD_COUNT
        or sum(
            row["field_count"]
            for row in rdf_rows
            if row["semantic_interpretation"]["domain"]
            == "amt_literal_reference_resource"
            and row["semantic_state"] == "interpreted"
        )
        != AMT_REFERENCE_RESOURCE_FIELD_COUNT
        or any(
            row["semantic_state"] != "native_unresolved"
            for row in rdf_rows
            if row["semantic_interpretation"]["domain"]
            != "amt_literal_reference_resource"
        )
    ):
        raise ValueError(
            "PBS RDF resource path denominator or baseline differs"
        )

    generic_count = 0
    for row in rdf_rows:
        if row["semantic_interpretation"]["domain"] == (
            "amt_literal_reference_resource"
        ):
            continue
        row["semantic_state"] = "interpreted"
        row["semantic_interpretation"] = {
            "state": "interpreted",
            "domain": "rdf_resource_reference_literal",
            "meaning": (
                "RDF/XML rdf:resource attribute used to identify an IRI "
                "object node; target validity and identity are unresolved"
            ),
            "rule": (
                "exact RDF namespace resource attribute QName and W3C RDF "
                "1.1 XML Syntax Recommendation"
            ),
            "evidence": "https://www.w3.org/TR/rdf-syntax-grammar/",
            "source_values_read": False,
            "source_values_emitted": False,
            "target_identity_resolved": False,
            "pbs_predicate_meaning_qualified": False,
            "semantic_relationship_qualified": False,
            "edge_payload_emitted": False,
            "limits": [
                "the syntax role does not validate an individual URI value or resolve its target",
                "the PBS predicate QName and any domain or clinical meaning remain unresolved",
                "URI-screen candidate and no-definition outcomes remain diagnostics only",
            ],
        }
        generic_count += row["field_count"]

    if generic_count != (
        RDF_RESOURCE_FIELD_COUNT - AMT_REFERENCE_RESOURCE_FIELD_COUNT
    ):
        raise ValueError("PBS generic RDF resource promotion count differs")
    coverage = report["field_state_coverage"]
    coverage["interpreted"] += generic_count
    coverage["native_unresolved"] -= generic_count
    coverage["all_native_values_remain_unresolved"] = False
    adjudication = report["semantic_adjudication"]
    adjudication["interpreted_fields"] += generic_count
    adjudication["native_unresolved_fields"] -= generic_count
    adjudication["interpretations"]["rdf_resource_reference_literal"] = (
        generic_count
    )
    adjudication["explicit_non_claims"].extend([
        "rdf:resource fields are interpreted only as the RDF/XML object-node IRI reference syntax role",
        "RDF resource URI-screen candidates are not resolved targets or qualified semantic relationships",
    ])
    report["source"]["rdf_resource_uri_screen_file_sha256"] = uri_file_sha
    report["source"]["rdf_resource_uri_screen_report_sha256"] = uri_envelope[
        "report_sha256"
    ]
    report["profile_id"] = "pbs-v3-2026-04-01-field-state-v7"
    report["status"] = (
        "complete_field_partition_with_bounded_rdf_resource_syntax_role"
    )
    report["source_local_rdf_resource_semantics"] = {
        "status": "generic_rdf_xml_object_node_reference_role_qualified",
        "rdf_resource_fields": RDF_RESOURCE_FIELD_COUNT,
        "newly_interpreted_generic_resource_references": generic_count,
        "preexisting_amt_reference_resource_fields": (
            AMT_REFERENCE_RESOURCE_FIELD_COUNT
        ),
        "uri_screen_outcomes": rdf_outcomes,
        "uri_screen_path": URI_SCREEN_V3,
        "uri_screen_file_sha256": uri_file_sha,
        "uri_screen_report_sha256": uri_envelope["report_sha256"],
        "meaning_basis": "https://www.w3.org/TR/rdf-syntax-grammar/",
        "target_identity_resolution_qualified": False,
        "semantic_relationships_qualified": False,
        "pbs_predicate_or_clinical_meaning_qualified": False,
        "edge_payload_emitted": False,
        "source_values_read": False,
        "source_values_emitted": False,
        "precision_or_recall_estimated": False,
        "field_state_partition_after_promotion": {
            "interpreted": coverage["interpreted"],
            "native_unresolved": coverage["native_unresolved"],
            "unavailable": coverage["unavailable"],
            "source_fields": coverage["source_fields"],
        },
        "limits": [
            "the generic RDF/XML syntax role is not a PBS domain relationship",
            "URI-screen matches and misses remain lexical diagnostics",
            "source values, resolved target identities, and graph edges remain unqualified",
        ],
    }
    return report


def reconcile_pbs_field_states_v8(root: Path) -> dict[str, Any]:
    """Qualify RDF/XML rdf:about as a subject-IRI field role only."""
    report = reconcile_pbs_field_states_v7(root)
    uri_path = root / URI_SCREEN_V3
    uri_file_sha = _file_sha256(uri_path)
    if uri_file_sha != URI_SCREEN_V3_FILE_SHA256:
        raise ValueError("PBS RDF about evidence bytes differ")
    uri_envelope = json.loads(uri_path.read_bytes())
    uri = uri_envelope["report"]
    qualification = uri["qualification"]
    definition_count = qualification["definition_counts_by_qname"].get(
        "rdf:about"
    )
    rdf_about_screen_checks = (
        uri_envelope["report_sha256"] == URI_SCREEN_V3_REPORT_SHA256,
        uri["operation"] == "pbs-native-uri-screen",
        uri["member_sha256"] == report["source"]["member_sha256"],
        definition_count == RDF_ABOUT_FIELD_COUNT,
        qualification["uri_values_emitted"] is False,
        qualification["literal_values_emitted"] is False,
        qualification["external_targets_fetched"] == 0,
        qualification["semantic_relationships_qualified"] is False,
        qualification["precision_claimed"] is False,
    )
    if not all(rdf_about_screen_checks):
        raise ValueError("PBS RDF about screen qualification differs")

    about_rows = [
        row
        for row in report["path_reconciliation"]
        if RDF_ABOUT_QNAME.replace("/", "~1") in row["schema_path"]
    ]
    structurally_scoped = all(
        _path_qnames(row["schema_path"])[0:2]
        == (PBS_QNAME + "root", RDF_DOCUMENT_QNAME)
        and _path_qnames(row["schema_path"])[-2:]
        == ("attributes", RDF_ABOUT_QNAME)
        for row in about_rows
    )
    if (
        len(about_rows) != RDF_ABOUT_PATH_COUNT
        or sum(row["field_count"] for row in about_rows)
        != RDF_ABOUT_FIELD_COUNT
        or not structurally_scoped
        or any(
            row["semantic_state"] != "native_unresolved" for row in about_rows
        )
    ):
        raise ValueError("PBS RDF about path denominator or baseline differs")

    for row in about_rows:
        row["semantic_state"] = "interpreted"
        row["semantic_interpretation"] = {
            "state": "interpreted",
            "domain": "rdf_about_subject_iri_reference",
            "meaning": (
                "RDF/XML rdf:about attribute that identifies the subject node "
                "with an IRI reference; base-URI resolution is not evaluated"
            ),
            "rule": (
                "exact rdf:RDF node-element ancestry and rdf:about attribute "
                "QName under W3C RDF 1.1 XML Syntax"
            ),
            "evidence": (
                "https://www.w3.org/TR/2014/REC-rdf-syntax-grammar-20140225/"
            ),
            "source_values_read": False,
            "source_values_emitted": False,
            "subject_iri_resolution_qualified": False,
            "semantic_relationship_qualified": False,
            "edge_payload_emitted": False,
            "limits": [
                "the syntax role does not validate or resolve an individual rdf:about value",
                "predicate, domain, and clinical meanings remain unresolved",
                "no relationships or graph edges are emitted",
            ],
        }

    coverage = report["field_state_coverage"]
    coverage["interpreted"] += RDF_ABOUT_FIELD_COUNT
    coverage["native_unresolved"] -= RDF_ABOUT_FIELD_COUNT
    adjudication = report["semantic_adjudication"]
    adjudication["interpreted_fields"] += RDF_ABOUT_FIELD_COUNT
    adjudication["native_unresolved_fields"] -= RDF_ABOUT_FIELD_COUNT
    adjudication["interpretations"]["rdf_about_subject_iri_reference"] = (
        RDF_ABOUT_FIELD_COUNT
    )
    adjudication["explicit_non_claims"].extend([
        "rdf:about fields identify only the RDF/XML subject-node IRI-reference syntax role",
        "rdf:about values are not resolved, and do not qualify predicates, domain relations, or graph edges",
    ])
    report["source"]["rdf_about_uri_screen_file_sha256"] = uri_file_sha
    report["source"]["rdf_about_uri_screen_report_sha256"] = uri_envelope[
        "report_sha256"
    ]
    report["profile_id"] = "pbs-v3-2026-04-01-field-state-v8"
    report["status"] = (
        "complete_field_partition_with_bounded_rdf_subject_iri_role"
    )
    report["source_local_rdf_about_semantics"] = {
        "status": "rdf_xml_subject_iri_reference_role_qualified",
        "rdf_about_fields": RDF_ABOUT_FIELD_COUNT,
        "newly_interpreted_subject_iri_references": RDF_ABOUT_FIELD_COUNT,
        "rdf_about_schema_paths": RDF_ABOUT_PATH_COUNT,
        "definition_count_in_uri_screen": definition_count,
        "uri_screen_path": URI_SCREEN_V3,
        "uri_screen_file_sha256": uri_file_sha,
        "uri_screen_report_sha256": uri_envelope["report_sha256"],
        "meaning_basis": (
            "https://www.w3.org/TR/2014/REC-rdf-syntax-grammar-20140225/"
        ),
        "subject_iri_resolution_qualified": False,
        "semantic_relationships_qualified": False,
        "pbs_predicate_or_clinical_meaning_qualified": False,
        "edge_payload_emitted": False,
        "source_values_read": False,
        "source_values_emitted": False,
        "field_state_partition_after_promotion": {
            "interpreted": coverage["interpreted"],
            "native_unresolved": coverage["native_unresolved"],
            "unavailable": coverage["unavailable"],
            "source_fields": coverage["source_fields"],
        },
        "limits": [
            "the qualified role is only the RDF/XML subject-node IRI reference syntax",
            "the exact field count is not a count of resolved or distinct subject IRIs",
            "predicate meaning, domain links, and semantic graph relationships remain unqualified",
        ],
    }
    return report


def reconcile_pbs_field_states_v9(root: Path) -> dict[str, Any]:
    """Bind the v8 field-role report to the exact source-path inventory."""
    inventory_path = root / PATH_INVENTORY
    inventory_sha256 = _file_sha256(inventory_path)
    if inventory_sha256 != PATH_INVENTORY_SHA256:
        raise ValueError("PBS schema-path inventory bytes differ")
    report = reconcile_pbs_field_states_v8(root)
    report["profile_id"] = "pbs-v3-2026-04-01-field-state-v9"
    report["status"] = (
        "complete_field_partition_with_digest_bound_rdf_subject_iri_role"
    )
    report["source"]["schema_path_inventory_path"] = PATH_INVENTORY
    report["source"]["schema_path_inventory_file_sha256"] = inventory_sha256
    report["source_local_rdf_about_semantics"]["schema_path_inventory_path"] = (
        PATH_INVENTORY
    )
    report["source_local_rdf_about_semantics"][
        "schema_path_inventory_file_sha256"
    ] = inventory_sha256
    return report
