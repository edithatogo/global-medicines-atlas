"""Reconcile each pinned PBS native field to one bounded meaning state."""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_domain_field_semantics import (
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
    "pbs-native-reference-screen-20261024-40076190245.json"
)
CONTEXT_SCREEN = (
    "quality/qualifications/"
    "pbs-native-reference-screen-20261024-40091358786.json"
)
DOMAIN = "quality/qualifications/pbs-domain-field-semantics-20261023.json"
FIELD_STATE = (
    "quality/qualifications/pbs-native-silver-field-state-20261023.json"
)
REFERENCE_REVIEW = (
    "quality/qualifications/"
    "pbs-native-reference-meaning-review-20261024-40076190245.json"
)
PACKAGE_SHA256 = (
    "769a1d88ab52d6ed9ab08d07ce7d7b433dd7f9034e6b501ad30198a9b6e59202"
)
SCREEN_SHA256 = (
    "a1adda4e946365b98bf3febc03b9ae51acdae6db1569c7fc6606f8892c7ae48e"
)
REFERENCE_SCREEN_SHA256 = (
    "570cc803a6657e421dc614855fe75013440f716dd3ff1d0096232c08ae363711"
)
CONTEXT_SCREEN_SHA256 = (
    "5bcc25fef1ad5a1a68a05fdc943f5b96e89848b56d5b6c506e9cba49d3b9db37"
)
CONTEXT_SCREEN_FILE_SHA256 = (
    "1bed1a970d599e2bf8cc422352bced094c9568afd4776930b9df2a01d0273313"
)
FIELD_STATE_SHA256 = (
    "2f35eebe45c0326dc80e76c461b0a8af23585923479cec8b74dcb9de5019120d"
)
REFERENCE_REVIEW_SHA256 = (
    "9c15cbfd8fb12b7078caf3c61411eb77df24a139b4cc27851c1abad2ca458084"
)
SUPERSEDED_REPORT = (
    "quality/qualifications/"
    "pbs-native-silver-field-reconciliation-20261024-r5.json"
)
SUPERSEDED_REPORT_SHA256 = (
    "d897b164aaf3f5524ed5cdddaac36a33c88bd0153f94464c65a78408c0dd94ca"
)
SCREEN_RUN_ID = "40076190245"
SCREEN_WORKFLOW_COMMIT = "b3139f9c655f48ccbb7a1714712219ac2281d838"
CONTEXT_SCREEN_RUN_ID = "40091358786"
CONTEXT_SCREEN_WORKFLOW_COMMIT = "a198ffff88531f06a34e4f237af6d55dfc74260a"
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
REFERENCE_CONTEXT_EXAMPLE_POLICY = (
    "up_to_five_value_free_examples_per_structural_stratum"
)
DOMAIN_REPORT_SHA256 = (
    "6999155565770f6112385705ba22b6b819db51508d352b3d16330ec8077c8a72"
)
SOURCE_FIELDS = 18_208_758
SOURCE_PATHS = 5_163
PATH_INVENTORY = (
    "quality/qualifications/pbs-schema-paths-20261022-39667604237.json"
)
SEMANTIC_ADJUDICATION = (
    "quality/qualifications/pbs-domain-semantic-adjudication-20261024.json"
)


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


def _semantic_adjudication(schema_path: str) -> dict[str, str | None]:  # ruff: ignore[too-many-return-statements] -- ordered path/QName allowlist keeps each adjudication independently auditable
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
    restriction_index = next(
        (
            i
            for i, name in enumerate(entity)
            if name == PBS_QNAME + "restriction"
        ),
        None,
    )
    if (
        restriction_index is not None
        and PBS_QNAME + "previous-list" not in entity
    ):
        restriction_suffix = entity[restriction_index + 1 :]
        reference_or_code = any(
            name.endswith(("-reference", "}code", "}assessment"))
            or name
            in {
                PBS_QNAME + "criteria",
                PBS_QNAME + "effective",
                PBS_QNAME + "non-effective",
            }
            or name == PBS_QNAME + "all"
            for name in restriction_suffix
        )
        if (
            slot in {"text", "tail"}
            and not reference_or_code
            and all(
                name.startswith((PBS_QNAME, "{http://docbook.org/ns/docbook#}"))
                for name in restriction_suffix
            )
        ):
            return {
                "state": "interpreted",
                "domain": "restriction_text",
                "meaning": "source restriction narrative text occurrence",
                "rule": "exact non-historical PBS restriction QName ancestry; references and date subtrees excluded",
            }
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
        == REFERENCE_CONTEXT_EXAMPLE_POLICY
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
    screen_path = root / SCREEN
    reference_screen_path = root / REFERENCE_SCREEN
    context_screen_path = root / CONTEXT_SCREEN
    field_state_path = root / FIELD_STATE
    reference_review_path = root / REFERENCE_REVIEW
    domain_path = root / DOMAIN
    package_sha = _file_sha256(package_path)
    screen_sha = _file_sha256(screen_path)
    reference_screen_sha = _file_sha256(reference_screen_path)
    context_screen_file_sha = _file_sha256(context_screen_path)
    field_state_sha = _file_sha256(field_state_path)
    reference_review_sha = _file_sha256(reference_review_path)
    superseded_report_sha = _file_sha256(root / SUPERSEDED_REPORT)
    digest_pairs = (
        (package_sha, PACKAGE_SHA256),
        (screen_sha, SCREEN_SHA256),
        (reference_screen_sha, REFERENCE_SCREEN_SHA256),
        (field_state_sha, FIELD_STATE_SHA256),
        (reference_review_sha, REFERENCE_REVIEW_SHA256),
        (superseded_report_sha, SUPERSEDED_REPORT_SHA256),
    )
    if any(actual != expected for actual, expected in digest_pairs):
        raise ValueError("PBS field evidence receipt digest differs")
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
        == "85b46210cc982c21f317cb6e5b1e64306ed166add87083c1d8f19d177521f5a2"
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
        "examples_emitted": 61,
        "no_exact_literal": 52,
        "unique_exact_literal": 9,
        "sampled_reference_kind_counts": {"rdf_resource": 61},
        "distinct_predicate_qname_count": 2,
        "nearest_subject_elements": 0,
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
            cast("dict[str, Any]", review_context_screen), schema_version=2
        ),
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
    ):
        raise ValueError("PBS schema-path field-state partition does not close")
    return {
        "schema_id": "global-medicines-atlas.pbs-field-state-reconciliation",
        "schema_version": 1,
        "profile_id": "pbs-v3-2026-04-01-field-state-v1",
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
            "profile_id": "pbs-v3-pinned-2026-04-01-path-qname-adjudication-v1",
            "inventory_sha256": "6da85f3e3526a52dca7b0f41206b5ec1afde854f89d858ae659867827219408b",
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
                "price, currency, unit, status/currentness, and cross-era date effects remain unresolved",
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
                    "The bounded sample is value-free diagnostic context; "
                    "it has no reviewed semantic labels or negative controls "
                    "and does not qualify matcher behavior."
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
