"""Bounded PBS v3 field meanings supported by one exact source structure.

This profile qualifies native XML structure labels only. It never promotes
native values to funding, payment, currency, clinical, or current-status facts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

INVENTORY = "quality/qualifications/pbs-schema-paths-20261022-39667604237.json"
OBSERVED = (
    "quality/qualifications/"
    "pbs-observed-domain-values-qualification-20261022-39672588063.json"
)
DATE_PROFILE = (
    "quality/qualifications/"
    "pbs-v3-2026-04-01-date-profile-qualification-20260929.json"
)
INVENTORY_SHA256 = (
    "6da85f3e3526a52dca7b0f41206b5ec1afde854f89d858ae659867827219408b"
)
MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
NATIVE_DIGEST = (
    "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25"
)
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
EXPECTED_NATIVE_FIELDS = 18_208_758
EXPECTED_RESTRICTION_DATE_FIELDS = 3_028
SOURCE_LABEL_SIGNATURES = {
    "brand_name_text": ("brand-name", "text"),
    "ex_manufacturer_amount_text": (
        "ex-manufacturer",
        "amount",
        "text",
    ),
    "copayment_amount_text": ("copayment", "amount", "text"),
    "threshold_amount_text": ("threshold", "amount", "text"),
    "fee_definition_amount_text": (
        "fee-definition",
        "amount",
        "text",
    ),
}
RESTRICTION_EFFECTIVE_DATE_TEXT_PATH = (
    "/{http:~1~1schema.pbs.gov.au~1}root/"
    "{http:~1~1schema.pbs.gov.au~1}prescribing-texts-list/"
    "{http:~1~1schema.pbs.gov.au~1}restriction/"
    "{http:~1~1schema.pbs.gov.au~1}effective/"
    "{http:~1~1schema.pbs.gov.au~1}date/text"
)


def _canonical_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_bytes())


def _source_label_observations(
    inventory: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Summarize exact-source path labels without interpreting their values."""
    observations: dict[str, dict[str, Any]] = {
        label: {
            "interpretation_state": "native_unresolved",
            "null_fields": 0,
            "schema_path_count": 0,
            "status": "source_path_label_only",
            "value_fields": 0,
            "native_fields": 0,
        }
        for label in SOURCE_LABEL_SIGNATURES
    }
    for row in inventory["paths"]:
        names = [
            segment.split("}")[-1] for segment in row["schema_path"].split("/")
        ]
        for label, signature in SOURCE_LABEL_SIGNATURES.items():
            width = len(signature)
            if any(
                tuple(names[index : index + width]) == signature
                for index in range(len(names) - width + 1)
            ):
                target = observations[label]
                target["schema_path_count"] += 1
                for count in ("native_fields", "value_fields", "null_fields"):
                    target[count] += row[count]
    return observations


def _pbs_amount_role_counts(
    inventory: dict[str, Any],
) -> dict[str, int]:
    """Count exact PBS amount text slots and documented nested roles."""
    counts = {
        "pbs_amount_fields": 0,
        "product_price_fields": 0,
        "patient_contribution_fields": 0,
    }
    for row in inventory["paths"]:
        parts = [
            segment.replace("~1", "/").replace("~0", "~")
            for segment in row["schema_path"].split("/")[1:]
        ]
        if parts[-2:] != ["{http://schema.pbs.gov.au/}amount", "text"]:
            continue
        count = row["native_fields"]
        counts["pbs_amount_fields"] += count
        ancestry = parts[:-2]
        if "{http://schema.pbs.gov.au/}contribution" in ancestry:
            counts["patient_contribution_fields"] += count
        elif "{http://schema.pbs.gov.au/}price" in ancestry:
            counts["product_price_fields"] += count
    return counts


def qualify_pbs_domain_fields(root: Path) -> dict[str, Any]:
    """Bind conservative field-meaning decisions to the exact retained inputs."""
    inventory_bytes = (root / INVENTORY).read_bytes()
    inventory_sha256 = hashlib.sha256(inventory_bytes).hexdigest()
    if inventory_sha256 != INVENTORY_SHA256:
        raise ValueError("PBS domain-field inventory digest differs")
    inventory = json.loads(inventory_bytes)
    if (
        inventory["member_sha256"] != MEMBER_SHA256
        or inventory["native_fields"] != EXPECTED_NATIVE_FIELDS
        or inventory["domain_semantics_qualified"] is not False
    ):
        raise ValueError("PBS domain-field source denominator differs")
    if any(
        segment.split("}")[-1].lower() == "status"
        for row in inventory["paths"]
        for segment in row["schema_path"].replace("~1", "/").split("/")
    ):
        raise ValueError(
            "PBS source inventory contains an unreviewed status path"
        )

    observed_envelope = _read_json(root, OBSERVED)
    observed = observed_envelope["report"]
    if (
        _canonical_digest(observed) != observed_envelope["report_sha256"]
        or observed["qualification"]["member_binding_sha256"]
        != "5bc111736f76cee651a73be99b37f5921b2924e53428b0c0f8ae45964943c4f2"
        or observed["qualification"]["native_digest"] != NATIVE_DIGEST
        or observed["qualification"]["domain_semantics_qualified"] is not False
    ):
        raise ValueError("PBS observed structural receipt differs")

    date_profile = _read_json(root, DATE_PROFILE)
    if (
        date_profile["source"]["member_sha256"] != MEMBER_SHA256
        or date_profile["source"]["native_digest"] != NATIVE_DIGEST
        or date_profile["source"]["revision"] != REVISION
        or date_profile["scope"]["domain_semantics_qualified"] is not False
    ):
        raise ValueError("PBS exact-source date receipt differs")

    fields = observed["qualification"]["role_field_counts"]
    entities = observed["qualification"]["role_entity_counts"]
    dates = date_profile["date_profile"]["role_counts"]
    restriction_date_rows = [
        row
        for row in inventory["paths"]
        if row["schema_path"] == RESTRICTION_EFFECTIVE_DATE_TEXT_PATH
    ]
    if (
        len(restriction_date_rows) != 1
        or restriction_date_rows[0]["native_fields"]
        != EXPECTED_RESTRICTION_DATE_FIELDS
    ):
        raise ValueError("PBS restriction effective-date path count differs")
    restriction_date_fields = restriction_date_rows[0]["native_fields"]
    domains = {
        "item": {
            "status": "qualified_bounded_source_structure",
            "meaning": "PBS pharmaceutical-item record occurrence",
            "field_count": fields["items"],
            "entity_count": entities["items"],
            "limits": [
                "occurrence identity is source/member/path-bound, not a global item key",
                "native code or identifier values are not interpreted or normalized",
            ],
        },
        "product": {
            "status": "qualified_bounded_source_structure",
            "meaning": "PBS drug/product and nested mp structures",
            "field_count": fields["products"],
            "entity_count": entities["products"],
            "limits": [
                "source structure does not establish ingredient equivalence or a unique marketed product",
                "mp/product code references remain literal and unresolved",
            ],
        },
        "restriction": {
            "status": "qualified_bounded_source_structure",
            "meaning": "PBS prescribing restriction and prescribing-rule source material",
            "field_count": fields["restrictions"] + fields["prescribing_rules"],
            "entity_count": entities["restrictions"]
            + entities["prescribing_rules"],
            "limits": [
                "text and rule structure are preserved; no patient eligibility or clinical conclusion is inferred",
                "linked criteria and administrative advice remain source references unless separately resolved",
            ],
        },
        "price": {
            "status": "qualified_bounded_source_structure",
            "meaning": "source-labelled product price and amount structure",
            "field_count": fields["prices"] + fields["pricing_components"],
            "entity_count": entities["prices"] + entities["pricing_components"],
            "limits": [
                "an amount under a PBS price path is not by itself a payable benefit or patient cost",
                "price basis, currency, contribution, and benefit semantics remain unresolved",
                "numeric candidate conversion remains lossless-only and native values remain native_unresolved",
            ],
        },
        "status": {
            "status": "unresolved_no_explicit_status_field_qualified",
            "meaning": None,
            "field_count": 0,
            "entity_count": 0,
            "limits": [
                "the exact path inventory contains no PBS element or attribute named status",
                "effective, supply-only, and non-effective dates do not establish a current listing state",
            ],
        },
        "effective_date": {
            "status": "qualified_bounded_source_structure_and_date_grammar",
            "meaning": "source schedule and item-effectivity date roles",
            "field_count": dates["pbs_effective_date"]
            + dates["schedule_effective_date"],
            "entity_count": dates["pbs_effective_date"]
            + dates["schedule_effective_date"],
            "limits": [
                "profile applies only to the exact pinned 2026-04-01 PBS v3 member",
                "date roles remain separate; no validity interval, commencement precedence, or current status is inferred",
                "other date-shaped values and other PBS eras remain unresolved",
            ],
        },
        "restriction_effective_date": {
            "status": "qualified_exact_source_path_role_date_grammar_unqualified",
            "meaning": "source date literal attached beneath a restriction's effective element",
            "field_count": restriction_date_fields,
            "limits": [
                "count covers only the exact direct PBS restriction/effective/date/text QName path in the pinned member",
                "the XSD date grammar is not qualified by the separate date-profile receipt for this path",
                "does not establish a validity interval, precedence, current status, or clinical eligibility",
                "reference-nested effective dates remain native_unresolved",
            ],
        },
        "document_valid_date": {
            "status": "qualified_separate_source_date_role",
            "meaning": "document-level dcterms:valid date, kept distinct from schedule effective date",
            "field_count": dates["schedule_dct_valid"],
            "entity_count": dates["schedule_dct_valid"],
            "limits": [
                "does not establish a medicine listing interval or current status",
                "applies only to the exact pinned 2026-04-01 PBS v3 member",
            ],
        },
    }
    return {
        "schema_id": "global-medicines-atlas.pbs-domain-field-semantics",
        "schema_version": 1,
        "profile_id": "pbs-v3-pinned-2026-04-01-domain-fields-v3",
        "status": "bounded_semantics_qualified_with_explicit_unresolved_fields",
        "source": {
            "dataset": "edithatogo/australian-pbs-source-archive",
            "revision": REVISION,
            "archive_sha256": inventory["archive_sha256"],
            "member_path": inventory["member_path"],
            "member_sha256": MEMBER_SHA256,
            "native_digest": NATIVE_DIGEST,
            "native_fields": inventory["native_fields"],
            "schema_path_inventory_sha256": inventory_sha256,
            "observed_domain_receipt_sha256": observed_envelope[
                "report_sha256"
            ],
            "date_profile_receipt_sha256": date_profile["digest"]["value"],
        },
        "meaning_basis": [
            "docs/qualification/australian-source-contracts.md#pbs-structural-destination-candidates",
            "docs/qualification/australian-source-contracts.md#pbs-opt-in-date-candidates",
            "docs/qualification/pbs-public-qualification.md#pinned-v3-date-profile-receipt-2026-09-28",
            date_profile["date_profile"]["developers_guide"],
            date_profile["date_profile"]["mapping_specification"],
            "https://info.data.pbs.gov.au/xml-schema/doc/html/elements/pbs_amount.html",
            "https://info.data.pbs.gov.au/xml-schema/doc/html/elements/pbs_pbs.price.content.html",
            "https://info.data.pbs.gov.au/xml-schema/doc/html/elements/pbs_contribution.html",
            "https://info.data.pbs.gov.au/xml-schema/doc/html/elements/pbs_pbs.restriction.html",
        ],
        "domains": domains,
        "source_schema_field_meanings": {
            "pbs_amount_text": {
                **_pbs_amount_role_counts(inventory),
                "status": "qualified_exact_pinned_v3_schema_role",
                "meaning": "PBS amount content is defined by the source schema as a dollar value; nested price and patient-contribution contexts retain their distinct source roles",
                "limits": [
                    "the schema does not supply an explicit currency code for these fields",
                    "the exact schema minor release used for the archive is not separately bound by the value-free path inventory",
                    "native lexemes, precision classification, amount category references, and monetary values remain unresolved",
                    "a source price amount is not thereby a payable benefit or patient cost",
                    "patient-contribution role does not establish the amount actually paid by a patient",
                    "applies only to exact PBS namespace amount/text paths in the pinned v3 member",
                ],
            },
            "restriction": {
                "status": "qualified_exact_pinned_v3_schema_label",
                "meaning": "the source restriction element represents the reason for subsidisation, including indications and criteria",
                "limits": [
                    "restriction text does not establish patient-specific eligibility or a clinical conclusion",
                    "reference descendants remain source-local references and are not resolved here",
                    "applies only to the exact pinned v3 restriction structure",
                ],
            },
        },
        "scope": {
            "source_values_emitted": False,
            "new_sources": 0,
            "new_admissions": 0,
            "consumer_canaries": 0,
            "publications": 0,
            "complete_domain_semantics_qualified": False,
            "rights_conclusion_changed": False,
            "cross_era_equivalence": False,
        },
    }


def qualify_pbs_source_label_observations(root: Path) -> dict[str, Any]:
    """Summarize pinned PBS path labels without altering domain meanings."""
    domain_profile = qualify_pbs_domain_fields(root)
    inventory = _read_json(root, INVENTORY)
    return {
        "schema_id": "global-medicines-atlas.pbs-source-label-observations",
        "schema_version": 1,
        "profile_id": "pbs-v3-pinned-2026-04-01-source-labels-v1",
        "status": "source_path_labels_observed_values_unresolved",
        "source": {
            "dataset": domain_profile["source"]["dataset"],
            "revision": REVISION,
            "member_sha256": MEMBER_SHA256,
            "native_digest": NATIVE_DIGEST,
            "native_fields": EXPECTED_NATIVE_FIELDS,
            "schema_path_inventory_sha256": domain_profile["source"][
                "schema_path_inventory_sha256"
            ],
        },
        "observations": _source_label_observations(inventory),
        "scope": {
            "source_values_emitted": False,
            "new_sources": 0,
            "new_admissions": 0,
            "consumer_canaries": 0,
            "publications": 0,
            "rights_conclusion_changed": False,
            "domain_value_semantics_qualified": False,
        },
    }
