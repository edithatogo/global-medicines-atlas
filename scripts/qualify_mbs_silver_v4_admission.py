"""Admit and anonymously read the exact existing six-table MBS Silver cohort.

This hosted qualification creates candidate product configurations only. It
retains aggregate identity/read receipts; it never emits source values, changes
the public dataset, or claims complete M-112 federation acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import httpx
from jsonschema import Draft202012Validator, FormatChecker

from global_medicines_atlas.australian_source_contracts import (
    mbs_field_contracts,
)
from global_medicines_atlas.federation_admission import TrustedAdmissionProfile
from global_medicines_atlas.federation_receipt_closure import (
    ReceiptPayload,
    contract_receipt_roles,
)
from global_medicines_atlas.mbs_silver_delivery_qualification import (
    validate_role_semantics,
)
from global_medicines_atlas.platinum_admission import (
    ProductAdmissionProfile,
    admit_product_configuration,
)
from global_medicines_atlas.platinum_configuration import DeploymentTrust
from global_medicines_atlas.platinum_delivery_qualification import (
    DeliveryRequest,
    run_product_delivery_qualification,
)
from global_medicines_atlas.platinum_resolver import (
    ProductResource,
    StorageNeutralResolver,
)
from global_medicines_atlas.platinum_types import (
    EntityGranularity,
    PlatinumSemanticDimension,
)

REPOSITORY = "edithatogo/global-medicines-atlas"
DATASET = "edithatogo/australian-mbs-source-archive"
REVISION = "3d2d528439bddf6f42e8e700c88917f0960a9f38"
ROLE_DIR = "quality/qualifications/australian-mbs-silver-delivery-role-qualification-20261025-40176576600"
RIGHTS_PATH = "quality/qualifications/australian-mbs-v4-public-release-rights-attestation-20261019.json"
USE_PATH = "quality/qualifications/australian-mbs-v4-candidate-use-authorization-20261017.json"
TREE_PATH = "quality/qualifications/australian-mbs-v4-current-public-tree-readback-20261020.json"
PUBLICATION_COMMENT = "https://api.github.com/repos/edithatogo/global-medicines-atlas/issues/comments/5859624790"
SOURCE_RECEIPT_PATH = f"{ROLE_DIR}/source-receipt.json"
OBJECTS = {
    "services": (
        "services.parquet",
        "46e7e652d6561ee82758b540eaf3584649d3e7e57fb3a341968678d0c2a48535",
        100062,
    ),
    "hierarchy": (
        "hierarchy.parquet",
        "05387bab5cc578e9923bfaf8a518fde7a49b4b2cde3c4ac61276a6defb3d3756",
        51851,
    ),
    "descriptions": (
        "descriptions.parquet",
        "2822ed642938c8f6b7274a3ecee3c96effc73a6eeedff87b11ed04e12b1a2733",
        620348,
    ),
    "fees": (
        "fees.parquet",
        "d4b88d6b63fcdd768a2546046f0fd9f6428017e83a5a0b3ce56d3bbbffb1a420",
        93072,
    ),
    "benefits": (
        "benefits.parquet",
        "51b9775dc995d9e5d92a9d90a14493ac885475eef0fb648822b9b139006d5f5f",
        114493,
    ),
    "caps": (
        "caps.parquet",
        "767677eb483f2401bd5b8a9b9f3e255fff1aee769d0c9d1d4f7b98463e1c6cbb",
        60259,
    ),
}
MAX_RECEIPT_BYTES = 1024 * 1024
REVISION_LENGTH = 40
PUBLICATION_COMMENT_ID = 5859624790
ROLE_RUN_ID = 40176576600
CANARY_FIELDS = {
    "services": "ItemNum",
    "hierarchy": "Group",
    "descriptions": "Description",
    "fees": "ScheduleFee",
    "benefits": "Benefit100",
    "caps": "EMSNDescription",
}


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch_receipt(
    url: str,
    limit: int = MAX_RECEIPT_BYTES,
) -> bytes:
    allowed = url.startswith((
        "https://raw.githubusercontent.com/edithatogo/global-medicines-atlas/",
        "https://api.github.com/repos/edithatogo/global-medicines-atlas/issues/comments/",
    ))
    if not allowed:
        raise ValueError("receipt host or path is outside the fixed allowlist")
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.get(
            url, headers={"User-Agent": "gma-v4-qualification"}
        )
        if response.status_code != HTTPStatus.OK:
            raise ValueError("receipt request did not return HTTP 200")
        payload = response.content
    if len(payload) > limit:
        raise ValueError("receipt exceeds the bounded read size")
    return payload


def raw_receipt_url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def normalize_receipt_time(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return (
        parsed
        .astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def qualify(root: Path, output_dir: Path, commit: str) -> dict[str, Any]:  # ruff: ignore[too-many-branches, too-many-statements, too-many-locals] -- one bounded six-object hosted qualification keeps receipts and payloads scoped to the run.
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_SHA") != commit
    ):
        raise ValueError(
            "live admission requires the exact default-branch Actions commit"
        )
    if not commit or len(commit) != REVISION_LENGTH:
        raise ValueError("commit must be a full immutable revision")

    schema = (
        root / "contracts/medallion/v4.1/federation.schema.json"
    ).read_bytes()
    schema_sha = _digest(schema)
    role_dir = root / ROLE_DIR
    role_manifest = json.loads(
        (role_dir / "receipt-manifest.json").read_bytes()
    )
    if (
        role_manifest.get("status") != "passed"
        or role_manifest["workflow_run"].get("id") != ROLE_RUN_ID
        or role_manifest.get("dataset") != DATASET
        or role_manifest.get("revision") != REVISION
        or role_manifest.get("producer_commit")
        != "8558ba0ee07c459f41030ee254d068e0b77b062b"
    ):
        raise ValueError("hosted role receipt bundle identity differs")
    role_documents = {
        name: (role_dir / f"{name}.json").read_bytes()
        for name in (
            "qualification",
            "primary-restore",
            "cache-cleanup",
            "v1-conformance",
            "v2-field-lineage",
            "v3-backfill-replay",
            "silver-promotion",
        )
    }
    for name, raw in role_documents.items():
        if role_manifest["files"][f"{name}.json"] != _digest(raw):
            raise ValueError("retained role report digest differs")
    source_receipt = (role_dir / "source-receipt.json").read_bytes()
    if (
        role_manifest["files"]["source-receipt.json"] != _digest(source_receipt)
        or _digest(source_receipt)
        != "cbb89dde7e24e790440b7aa3ec70ff8a580801d49b5f0b8839290f63bd64819c"
    ):
        raise ValueError("exact retained B1 source receipt digest differs")
    source_doc = json.loads(source_receipt)
    qualification = json.loads(role_documents["qualification"])
    for rel_path, expected_sha in qualification["input_documents"].items():
        if _digest((root / rel_path).read_bytes()) != expected_sha:
            raise ValueError("hosted role input document digest differs")
    role_schemas = {
        "v1-conformance": "contracts/medallion/v1/medallion-conformance.schema.json",
        "v2-field-lineage": "contracts/medallion/v2/field-lineage.schema.json",
        "v3-backfill-replay": "contracts/medallion/v3/backfill-replay.schema.json",
    }
    for role_name, schema_path in role_schemas.items():
        validator = Draft202012Validator(
            json.loads((root / schema_path).read_bytes()),
            format_checker=FormatChecker(),
        )
        cast("Any", validator).validate(json.loads(role_documents[role_name]))
    validate_role_semantics(
        *(json.loads(role_documents[name]) for name in role_schemas)
    )
    rights_raw = (root / RIGHTS_PATH).read_bytes()
    use_raw = (root / USE_PATH).read_bytes()
    tree_raw = (root / TREE_PATH).read_bytes()
    manifest_raw = (
        root
        / "quality/qualifications/australian-mbs-v4-candidate-2025-07/manifest.json"
    ).read_bytes()
    qualification_raw = (
        root
        / "quality/qualifications/australian-mbs-v4-candidate-2025-07/qualification.json"
    ).read_bytes()
    semantics_raw = (
        root
        / "quality/qualifications/australian-mbs-silver-semantic-manifest-20261017.json"
    ).read_bytes()
    rights = json.loads(rights_raw)
    use = json.loads(use_raw)
    tree = json.loads(tree_raw)
    candidate_manifest = json.loads(manifest_raw)
    candidate_qualification = json.loads(qualification_raw)
    semantic_manifest = json.loads(semantics_raw)
    if (
        semantic_manifest["domain_contract"]["subject_kind"] != "service"
        or semantic_manifest["domain_contract"]["dimension"]
        != "service_benefit"
        or semantic_manifest["domain_contract"]["mapping_status"]
        != "source_native"
        or semantic_manifest["domain_contract"]["absence_interpretation"]
        != "unknown"
    ):
        raise ValueError("MBS source-native table domain contract differs")
    if (
        candidate_manifest["source"]["source_id"] != "au-mbs"
        or candidate_manifest["source"]["sha256"]
        != source_doc["payload"]["sha256"]
        or candidate_manifest["source"]["source_revision"]
        != "2025-07-version-3"
        or candidate_manifest["qualification_sha256"]
        != candidate_qualification["qualification"]["qualification_sha256"]
        or candidate_qualification["qualification"]["source_era_verification"][
            "effective_at"
        ]
        != "2025-07-01"
    ):
        raise ValueError("candidate manifest source identity differs")
    if (
        use["dataset_identity"]["dataset"] != DATASET
        or use["dataset_identity"]["revision"] != REVISION
        or use["dataset_identity"]["candidate_only"] is not True
        or rights.get("public_release_authorized") is not True
    ):
        raise ValueError("exact candidate-use and release authority differs")
    publication_raw = fetch_receipt(PUBLICATION_COMMENT)
    publication = json.loads(publication_raw)
    publication_body = json.loads(publication["body"])
    if (
        publication["id"] != PUBLICATION_COMMENT_ID
        or publication_body.get("candidate_only") is not True
    ):
        raise ValueError("historical publication receipt identity differs")
    if (
        publication_body.get("dataset") != DATASET
        or publication_body.get("manifest_sha256")
        != "bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59"
        or publication_body.get("revision")
        != "ba82cd1d0f9b0f28514df431b8da3a6c207d76fa"
    ):
        raise ValueError("historical publication revision differs")

    auth_objects = {item["name"]: item for item in use["authorized_objects"]}
    release_objects = {
        item["path"]: item for item in rights["authorized_objects"]
    }
    qual_objects = {item["table"]: item for item in qualification["tables"]}
    publication_objects = {
        item["path"]: item for item in publication_body["verified_objects"]
    }
    tree_objects = {item["path"]: item for item in tree["objects"]}
    expected_names = set(OBJECTS)
    if (
        set(auth_objects) != expected_names
        or set(qual_objects) != expected_names
    ):
        raise ValueError(
            "authorized or role-qualified table denominator differs"
        )
    if (
        tree["access"].get("private") is not False
        or tree["access"].get("gated") is not False
    ):
        raise ValueError("current public-tree access state is not public")

    source_receipt_url = raw_receipt_url(commit, SOURCE_RECEIPT_PATH)
    receipt_docs: dict[str, bytes] = {
        PUBLICATION_COMMENT: publication_raw,
        source_receipt_url: source_receipt,
    }
    fixed_paths = {
        "rights": RIGHTS_PATH,
        "discovery": TREE_PATH,
        "verification": f"{ROLE_DIR}/qualification.json",
        "v1": f"{ROLE_DIR}/v1-conformance.json",
        "v2": f"{ROLE_DIR}/v2-field-lineage.json",
        "v3": f"{ROLE_DIR}/v3-backfill-replay.json",
        "promotion": f"{ROLE_DIR}/silver-promotion.json",
        "restore": f"{ROLE_DIR}/primary-restore.json",
        "cache": f"{ROLE_DIR}/cache-cleanup.json",
    }
    for path in fixed_paths.values():
        receipt_docs[raw_receipt_url(commit, path)] = (root / path).read_bytes()

    profiles: list[ProductAdmissionProfile] = []
    contracts: list[bytes] = []
    semantics: list[bytes] = []
    admitted: list[Any] = []
    configurations: list[Any] = []
    object_urls = {
        url: ReceiptPayload(url=url, payload=raw)
        for url, raw in receipt_docs.items()
    }
    table_configs: list[dict[str, Any]] = []
    for name, (filename, digest, byte_count) in OBJECTS.items():
        path = f"silver/mbs/v4/2025-07-v3/{filename}"
        auth = auth_objects[name]
        if (auth["path"], auth["sha256"], auth["byte_count"]) != (
            path,
            digest,
            byte_count,
        ):
            raise ValueError("candidate authorization identity differs")
        if (path, digest, byte_count) != (
            auth["path"],
            auth["sha256"],
            auth["byte_count"],
        ):
            raise ValueError("fixed object identity differs")
        if path not in release_objects or (
            release_objects[path]["sha256"],
            release_objects[path]["byte_count"],
        ) != (digest, byte_count):
            raise ValueError("rights attestation does not bind exact object")
        if path not in publication_objects or (
            publication_objects[path]["sha256"],
            publication_objects[path]["byte_count"],
        ) != (digest, byte_count):
            raise ValueError("publication receipt does not bind exact object")
        if path not in tree_objects or (
            tree_objects[path]["sha256"],
            tree_objects[path]["byte_count"],
        ) != (digest, byte_count):
            raise ValueError("public tree readback does not bind exact object")
        qobj = qual_objects[name]
        if not qobj["passed"] or (
            qobj["path"],
            qobj["sha256"],
            qobj["byte_count"],
            qobj["row_count"],
        ) != (path, digest, byte_count, 5989):
            raise ValueError(
                "hosted role qualification does not bind exact object"
            )

        urls = {
            key: raw_receipt_url(commit, path_)
            for key, path_ in fixed_paths.items()
        }

        def ref(url: str) -> dict[str, str]:
            return {"url": url, "sha256": _digest(receipt_docs[url])}

        retrieved_at = source_doc["retrieval"]["retrieved_at"]
        report_completed_at = json.loads(role_documents["primary-restore"])[
            "completed_at"
        ]
        cache = json.loads(role_documents["cache-cleanup"])
        contract_doc: dict[str, Any] = {
            "version": "4.1.0",
            "evidence_kind": "live",
            "authority": {
                "producer_repository": REPOSITORY,
                "contract_repository": REPOSITORY,
                "contract_commit": commit,
                "schema_sha256": schema_sha,
            },
            "source": {
                "source_id": "au-mbs",
                "acquisition_id": source_doc["temporal"]["acquisition_id"],
                "layer": "silver",
                "bronze_stratum": None,
                "representation": "projection",
                "schema_era": "2025-07-version-3",
                "comparison_cohort": "legacy",
                "effective_date": "2025-07-01",
                "retrieved_at": normalize_receipt_time(retrieved_at),
            },
            "location": {
                "dataset": DATASET,
                "revision": REVISION,
                "path": path,
                "bytes": byte_count,
                "sha256": digest,
                "private": False,
                "gated": False,
                "xet_hash": None,
                "lfs_oid": None,
            },
            "publication": {
                "origin": "github_actions",
                "workflow": ".github/workflows/australian-mbs-silver-publication.yml",
                "run": "https://github.com/edithatogo/global-medicines-atlas/actions/runs/36348699885",
                "commit": "decdeca1f3724405b0e085eb77d8ff11b6944ef9",
                "receipt": ref(PUBLICATION_COMMENT),
            },
            "verification": {
                "dataset": DATASET,
                "revision": REVISION,
                "path": path,
                "sha256": digest,
                "bytes": byte_count,
                "anonymous": True,
                "clean_room": True,
                "status": "passed",
                "verified_at": normalize_receipt_time(report_completed_at),
                "receipt": ref(urls["verification"]),
            },
            "rights": {
                "authorization": ref(urls["rights"]),
                "subject_sha256": digest,
                "dataset": DATASET,
                "path": path,
                "basis": "maintainer_attested_exact_six_public_release_rights_20261019_instrument_not_independently_reviewed",
                "sensitivity": "non_sensitive",
                "publication": "approved_exact_scope",
            },
            "discovery": {
                "collections": [],
                "estate_entry": ref(urls["discovery"]),
            },
            "lineage": {
                "inputs": [ref(source_receipt_url)],
                "v1_conformance": ref(urls["v1"]),
                "v2_field_lineage": ref(urls["v2"]),
                "v2_field_lineage_applicability": "provided",
                "v3_replay": ref(urls["v3"]),
                "promotion_receipt": ref(urls["promotion"]),
            },
            "recovery": {
                "role": "primary",
                "independent": False,
                "administrative_domain": "huggingface.co primary dataset account",
                "primary_administrative_domain": "huggingface.co primary dataset account",
                "region": "unverified",
                "primary_region": "unverified",
                "rpo_seconds": None,
                "rto_seconds": None,
                "checksum_inventory": ref(urls["restore"]),
                "restore_receipt": ref(urls["restore"]),
                "authorization_receipt": None,
            },
            "cache": {
                "origin": "github_actions",
                "state": "removed",
                "max_bytes": 67108864,
                "created_at": normalize_receipt_time(cache["created_at"]),
                "expires_at": normalize_receipt_time(cache["expires_at"]),
                "cleanup_receipt": ref(urls["cache"]),
                "offline_behavior": "fail_closed",
            },
            "consumers": [],
        }
        contract = json.dumps(
            contract_doc, sort_keys=True, separators=(",", ":")
        ).encode()
        expected_role_payloads = {
            "/publication/receipt": PUBLICATION_COMMENT,
            "/verification/receipt": urls["verification"],
            "/rights/authorization": urls["rights"],
            "/discovery/estate_entry": urls["discovery"],
            "/lineage/inputs/0": source_receipt_url,
            "/lineage/v1_conformance": urls["v1"],
            "/lineage/v2_field_lineage": urls["v2"],
            "/lineage/v3_replay": urls["v3"],
            "/lineage/promotion_receipt": urls["promotion"],
            "/recovery/checksum_inventory": urls["restore"],
            "/recovery/restore_receipt": urls["restore"],
            "/cache/cleanup_receipt": urls["cache"],
        }
        roles = contract_receipt_roles(contract, schema=schema)
        if {role.role: role.url for role in roles} != expected_role_payloads:
            raise ValueError(
                "contract receipt roles differ from independently configured allowlist"
            )
        payloads = tuple(
            object_urls[url] for url in sorted({role.url for role in roles})
        )
        resource_id = f"au.mbs.2025-07-v3.{name}"
        dimension: PlatinumSemanticDimension = "service_benefit"
        granularity: EntityGranularity = "service_item"
        semantic = json.dumps(
            {
                "version": "1.0",
                "resource_id": resource_id,
                "semantic_dimension": dimension,
                "entity_granularity": granularity,
                "contract_sha256": _digest(contract),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        trusted = TrustedAdmissionProfile(
            producer_repository=REPOSITORY,
            contract_repository=REPOSITORY,
            contract_commit=commit,
            schema_sha256=schema_sha,
            dataset=DATASET,
            revision=REVISION,
            path=path,
            byte_count=byte_count,
            sha256=digest,
            source_id="au-mbs",
            acquisition_id=source_doc["temporal"]["acquisition_id"],
            layer="silver",
            bronze_stratum=None,
            representation="projection",
            schema_era="2025-07-version-3",
            comparison_cohort="legacy",
            effective_date="2025-07-01",
            retrieved_at=normalize_receipt_time(retrieved_at),
            evidence_kind="live",
            authorization=next(
                role for role in roles if role.role == "/rights/authorization"
            ),
            lineage=tuple(
                role for role in roles if role.role.startswith("/lineage/")
            ),
        )
        profile = ProductAdmissionProfile(
            resource_id=resource_id,
            semantic_dimension=dimension,
            entity_granularity=granularity,
            semantic_sha256=_digest(semantic),
            subject=trusted,
            receipt_roles=roles,
        )
        config = admit_product_configuration(
            contract,
            payloads,
            semantic,
            schema=schema,
            profile=profile,
            contract_path=f"contracts/{name}.json",
            semantic_path=f"semantics/{name}.json",
        )
        profiles.append(profile)
        contracts.append(contract)
        semantics.append(semantic)
        admitted.append(config.admission)
        configurations.append(config)
        table_configs.append({
            "table": name,
            "path": path,
            "sha256": digest,
            "byte_count": byte_count,
            "row_count": qobj["row_count"],
            "resource_id": resource_id,
            "contract_sha256": _digest(contract),
            "receipt_roles": [role.model_dump(mode="json") for role in roles],
            "semantic_sha256": _digest(semantic),
            "semantic_dimension": dimension,
            "entity_granularity": granularity,
            "admission_record": config.admission.model_dump(mode="json"),
        })

    resources = tuple(
        ProductResource(
            resource_id=profile.resource_id,
            semantic_dimension=profile.semantic_dimension,
            entity_granularity=profile.entity_granularity,
            binding=configuration.binding,
            contract=contract,
            semantic_manifest=semantic,
        )
        for profile, configuration, contract, semantic in zip(
            profiles, configurations, contracts, semantics, strict=True
        )
    )
    read_receipts: list[dict[str, Any]] = []
    with StorageNeutralResolver(
        schema=schema,
        resources=resources,
        admission_records=admitted,
        admitted_semantic_manifests=frozenset(
            _digest(item) for item in semantics
        ),
        max_read_bytes=1024 * 1024,
        cache_bytes=8 * 1024 * 1024,
        max_open_reads=2,
        timeout_seconds=60,
    ) as resolver:
        for profile in profiles:
            with resolver.open(profile.resource_id) as result:
                content_hash = result.verified.sha256
                if (
                    content_hash != result.metadata.sha256
                    or result.verified.byte_count != result.metadata.byte_count
                ):
                    raise ValueError(
                        "remote reader returned a different object identity"
                    )
                read_receipts.append({
                    "resource_id": profile.resource_id,
                    "contract_sha256": result.verified.contract_sha256,
                    "object_sha256": content_hash,
                    "byte_count": result.verified.byte_count,
                    "origin": result.verified.origin,
                    "status": "passed",
                })
        resolver.evict()
        if resolver.cached_bytes != 0:
            raise ValueError("verified remote read cache did not evict")

    metadata_root = output_dir / "metadata"
    for name, contract, semantic in zip(
        OBJECTS, contracts, semantics, strict=True
    ):
        (metadata_root / "contracts").mkdir(parents=True, exist_ok=True)
        (metadata_root / "semantics").mkdir(parents=True, exist_ok=True)
        (metadata_root / "contracts" / f"{name}.json").write_bytes(contract)
        (metadata_root / "semantics" / f"{name}.json").write_bytes(semantic)
    trust = DeploymentTrust(version="1.1", resources=tuple(configurations))
    trust_file = output_dir / "deployment-trust.json"
    trust_file.write_text(
        trust.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    native_fields = {
        field.native_name: field.target_table for field in mbs_field_contracts()
    }
    if any(native_fields.get(CANARY_FIELDS[name]) != name for name in OBJECTS):
        raise ValueError("consumer canary field differs from its native table")
    requests = tuple(
        DeliveryRequest(
            resource_id=profile.resource_id,
            columns=(CANARY_FIELDS[name],),
            limit=2,
        )
        for (name, _object), profile in zip(
            OBJECTS.items(),
            profiles,
            strict=True,
        )
    )
    consumer_canary = run_product_delivery_qualification(
        trust_file,
        metadata_root,
        root / "contracts/medallion/v4.1/federation.schema.json",
        requests,
    )
    if consumer_canary["status"] != "passed":
        raise ValueError("API, CLI, Atlas, or export consumer canary failed")

    result = {
        "schema_id": "global-medicines-atlas.australian-mbs-silver-v4-remote-admission-qualification",
        "schema_version": 1,
        "status": "passed",
        "dataset": DATASET,
        "revision": REVISION,
        "contract_commit": commit,
        "role_receipt_bundle": ROLE_DIR,
        "objects": table_configs,
        "remote_reads": read_receipts,
        "consumer_canary": consumer_canary,
        "verified_object_count": len(read_receipts),
        "boundaries": {
            "candidate_product_profiles_admitted": True,
            "m112_federation_acceptance": False,
            "production_promotion": False,
            "consumer_canaries": True,
            "external_publication_performed": False,
            "source_values_included": False,
            "new_sources_added": False,
            "inventory_changed": False,
            "independent_recovery_qualified": False,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "admission-remote-read.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    result = qualify(args.repository_root, args.output_dir, args.exact_commit)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
