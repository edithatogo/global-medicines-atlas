"""Bronze maturity qualification against repository evidence.

The immutable source payload and its content-addressed receipt are
evidentiary truth; source-faithful Parquet is the portable analytical
representation; table/catalogue layers are rebuildable metadata over those
artefacts. Later-layer, dashboard, and Hugging Face publication success
are never bronze maturity evidence.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from .bronze_admission import BronzeAdmissionRecord
from .bronze_raw_evidence import RawEvidenceManifest
from .cms_partd_qualification import (
    RAW_RELATIVE as CMS_RAW_RELATIVE,
)
from .cms_partd_qualification import (
    RECORDS_RELATIVE as CMS_RECORDS_RELATIVE,
)
from .cms_partd_qualification import (
    RIGHTS_RELATIVE as CMS_RIGHTS_RELATIVE,
)
from .cms_partd_qualification import (
    SOURCE_IDS as CMS_SOURCE_IDS,
)
from .cms_partd_qualification import (
    qualified_cms_sources,
)
from .receipts import AcquisitionEvent, SourceReceipt
from .source_catalog import AccessMode, AuthenticationMode

SCHEMA_ID = "global-medicines-atlas.bronze-maturity-qualification"
HORIZON = "bronze-bounded-public-scope-v1"
FULL_SCOPE_HORIZON = "bronze-current-public-scope"
SCOPE_DECISION_RELATIVE = (
    "quality/qualifications/bronze-bounded-scope-decision-v1.json"
)
BOUNDED_SCOPE_FULL_SOURCE_COUNT = 157
BOUNDED_SCOPE_ACTIVE_SOURCE_COUNT = 42
BOUNDED_SCOPE_DEFERRED_SOURCE_COUNT = 115
CATALOG_RELATIVE = (
    "src/global_medicines_atlas/data/medicine_source_catalog.json"
)
REPORT_RELATIVE = "quality/qualifications/bronze-maturity.json"
LANDING_OVERRIDES_RELATIVE = (
    "src/global_medicines_atlas/data/source_landing_overrides.json"
)
SCHEMA_RELATIVE = "schemas/bronze-maturity-qualification-v1.json"
PROPERTY_IDS: tuple[str, ...] = (
    "completeness",
    "immutability",
    "temporal_identity",
    "provenance",
    "rights",
    "reuse_discovery",
    "lineage",
    "quarantine",
    "reproducibility",
    "disaster_recovery",
    "security",
    "performance",
    "interoperability",
    "documentation",
)
FDA_SHORTAGES_HISTORICAL_SNAPSHOT_COUNT = 129
SHA256_HEX_LENGTH = 64
GIT_SHA_HEX_LENGTH = 40
NICE_UTILISATION_EXPECTED_PAYLOAD_COUNT = 15
NICE_UTILISATION_EXPECTED_RELEASE_COUNT = 4
SWEDEN_SOURCE_ID = "se-socialstyrelsen-utilisation"
SWEDEN_QUALIFICATION_RELATIVE = "quality/qualifications/sweden-socialstyrelsen-live-private-bronze-20260929.json"
SWEDEN_WORKFLOW_COMMIT = "09d3c8370b04c4b92439b2587e683e92276f3d6b"
SWEDEN_PAYLOAD_SHA256 = (
    "2776225df2bae38451747a89dfc211a6f09edc43e1c3584d2855b574f6c061ed",
    "19ef7f11d3d9cd42307ad54a0c1bb7098b333877cf1e66666d37e7349b4267ef",
    "dd1887387561be7c1a111ec4ab11ef895b21cd2e0c2a29c40bd50fa9578b0414",
    "c91a65306745bc80bcac5e599fcd5a540c027a49d9f6bf8c309628e3c747a8fb",
    "de2f425c74a39f14b59fb0d1da13ae0466f29ad9dc38f9f8048321dda77a8883",
)
SWEDEN_PAYLOAD_COUNT = 5
SWEDEN_CELL_COUNT_UPPER_BOUND = 90
SWEDEN_MAXIMUM_CELLS = 70000
SWEDEN_MAXIMUM_ATC_CODES = 100
SWEDEN_ARCHIVE_BYTE_COUNT = 921600
AU_MBS_PAYLOAD_SHA256 = (
    "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
)
AU_MBS_PAYLOAD_BYTE_COUNT = 8293331
AU_MBS_ACQUISITION_ID = (
    "fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd"
)
AU_MBS_RECEIPT_ID = "mbs-release:dab6a3a2793596b485fb6b1825837a13ade8bce04a897b65002c7794a6832cfb"
AU_MBS_ARCHIVE_REVISION = "abdf414cdea0127d3edda6f8af402d1a01139623"
AU_MBS_VERIFIED_LIFECYCLE_OBJECT_COUNT = 5
AU_MBS_QUALIFICATION_SCHEMA_VERSION = 2
AU_MBS_RAW_REFERENCE = (
    "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/resolve/"
    f"{AU_MBS_ARCHIVE_REVISION}/raw/mbs/releases/2026-08-01/{AU_MBS_PAYLOAD_SHA256}.xml"
)
NORPD_SOURCE_ID = "no-norpd-utilisation"
NORPD_QUALIFICATION_RELATIVE = (
    "quality/qualifications/norpd-live-private-bronze-20261001.json"
)
NORPD_AUTHORIZATION_RELATIVE = (
    "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)
NORPD_WORKFLOW_RUN = "https://github.com/edithatogo/global-medicines-atlas/actions/runs/36870401810"
NORDIC_AUTHORIZED_SOURCE_COUNT = 3
OPEN_MEDIC_SOURCE_ID = "fr-open-medic"
OPEN_MEDIC_QUALIFICATION_RELATIVE = (
    "quality/qualifications/open-medic-all-release-bronze-20260827.json"
)
OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE = (
    "quality/qualifications/open-medic-bronze-release-manifest-v1.json"
)
OPEN_MEDIC_RELEASE_MANIFEST_SHA256 = (
    "238896393567936cae98b2014b85b1597d5b8cfd52b8562e1cf20e5564ff0df6"
)
OPEN_MEDIC_ACQUISITION_AUTHORIZATION_RELATIVE = "quality/qualifications/additional-utilisation-acquisition-authorization.json"
OPEN_MEDIC_RIGHTS_DISPOSITION_RELATIVE = (
    "quality/qualifications/source-rights-disposition.json"
)
OPEN_MEDIC_RIGHTS_LEDGER_RELATIVE = (
    "quality/qualifications/source-rights-review-ledger.json"
)
OPEN_MEDIC_DATASET = "edithatogo/global-medicines-atlas-open-medic-20260821"
OPEN_MEDIC_REVISION = "d19f7a66e35c58c557615bffa456856b485b7edc"
OPEN_MEDIC_RELEASE_YEARS = tuple(range(2014, 2026))
OPEN_MEDIC_PROMPT_ID = 34
OPEN_MEDIC_PUBLIC_MANIFEST_FILE_COUNT = 24
OPEN_MEDIC_PUBLIC_MANIFEST_SHA256 = (
    "5a08e2eb4e99ec0e95f596a384df22007ca67b9df311a7af9b285f55eada0578"
)
AU_MBS_QUALIFICATION_RELATIVE = (
    "quality/qualifications/australian-mbs-bronze-source-receipt-20261004.json"
)
AUTHORITIES = {
    "requirements": "conductor/requirements.md",
    "maturity_model": "conductor/maturity-model.json",
    "source_catalog": CATALOG_RELATIVE,
    "bronze_completion_spec": (
        "conductor/tracks/bronze_medallion_completion_20260819/spec.md"
    ),
    "reuse_policy": "docs/ECOSYSTEM_REUSE.md",
}
FORBIDDEN_EVIDENCE = frozenset({
    "quality/qualifications/stable-v1-contract.json",
    "quality/qualifications/data-layer-archive-receipt.json",
    "quality/qualifications/stable-v1-consumer-compatibility.json",
    "docs/publication/data-layer-archive-receipt.md",
    "docs/publication/external-publication-receipt.md",
})
FORBIDDEN_EVIDENCE_PREFIXES = (
    "docs/publication/",
    "quality/qualifications/stable-v1-",
)
FORBIDDEN_NEEDLES = (
    "silver implementation complete",
    "gold implementation complete",
    "dashboard bronze mature",
)
FIXTURE_ONLY_SOURCE_IDS = frozenset({
    "global-rxnorm",
    "us-rxnorm-api",
})
ScopeClass = Literal["bronze_in_scope", "fixture_only", "excluded"]
PropertyState = Literal["evidenced", "blocked"]


def classify_catalog_source(source: Mapping[str, Any]) -> ScopeClass:
    """Classify one catalog row for the current bronze horizon.

    Missing coverage is not negative evidence. Credentialed and licensed
    feeds are excluded from this horizon, not scored as incomplete bronze.
    """

    source_id = str(source["source_id"])
    if source_id in FIXTURE_ONLY_SOURCE_IDS:
        return "fixture_only"
    authentication = str(source.get("authentication", ""))
    access_mode = str(source.get("access_mode", ""))
    if (
        authentication != AuthenticationMode.NONE.value
        or access_mode == AccessMode.LICENSED_FEED.value
    ):
        return "excluded"
    return "bronze_in_scope"


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def _contains(root: Path, relative: str, needles: Sequence[str]) -> bool:
    if not _exists(root, relative):
        return False
    text = _read(root, relative)
    return all(needle in text for needle in needles)


def _evidence_is_forbidden(path: str) -> bool:
    if path in FORBIDDEN_EVIDENCE:
        return True
    return any(
        path.startswith(prefix) for prefix in FORBIDDEN_EVIDENCE_PREFIXES
    )


def reject_forbidden_evidence(evidence: Sequence[str]) -> tuple[str, ...]:
    """Return forbidden later-layer or publication paths used as evidence."""

    return tuple(path for path in evidence if _evidence_is_forbidden(path))


def _quoted_source_ids(text: str, source_ids: set[str]) -> set[str]:
    found: set[str] = set()
    for source_id in source_ids:
        if f'"{source_id}"' in text or f"'{source_id}'" in text:
            found.add(source_id)
    return found


def landing_source_ids(root: Path, source_ids: set[str]) -> set[str]:
    """Return catalog IDs with adapter, fixture, or ingest evidence."""

    found: set[str] = set()
    adapter_dir = root / "src/global_medicines_atlas/adapters"
    fixture_dir = root / "tests/fixtures"
    for path in (*adapter_dir.glob("*.py"), *fixture_dir.rglob("*")):
        if not path.is_file() or path.suffix == ".pyc":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found.update(_quoted_source_ids(text, source_ids))
    return found


def _contains_exact_value(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, Mapping):
        return any(
            _contains_exact_value(item, expected)
            for item in cast("Mapping[str, Any]", value).values()
        )
    if isinstance(value, list):
        return any(
            _contains_exact_value(item, expected)
            for item in cast("list[Any]", value)
        )
    return False


def _is_receipt_reference(relative: str) -> bool:
    """Reject publication paths before opening a claimed Bronze receipt."""

    normalized = relative.replace("\\", "/")
    name = Path(normalized).name.casefold()
    return (
        normalized.endswith(".json")
        and not _evidence_is_forbidden(normalized)
        and "publication" not in name
        and "huggingface" not in name
    )


def _is_successful_bronze_receipt(
    root: Path, receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Require a typed qualification receipt and a positive success outcome."""

    schema_id = receipt.get("schema_id")
    if not isinstance(schema_id, str) or not schema_id.startswith(
        "global-medicines-atlas."
    ):
        return False
    specialized: dict[str, Callable[[], bool]] = {
        "global-medicines-atlas.us-live-bronze-records-qualification": lambda: (
            _is_successful_us_live_records_receipt(receipt, source_id)
        ),
        "global-medicines-atlas.fda-shortages-live-qualification": lambda: (
            _is_successful_fda_shortages_receipt(receipt, source_id)
        ),
        "global-medicines-atlas.nice-utilisation-acquisition-success": lambda: (
            _is_successful_nice_utilisation_receipt(root, receipt, source_id)
        ),
        "global-medicines-atlas.sweden-socialstyrelsen-live-private-bronze-qualification": lambda: (
            _is_successful_sweden_receipt(receipt, source_id)
        ),
        "global-medicines-atlas.norpd-live-private-bronze-qualification": lambda: (
            _is_successful_norpd_receipt(root, receipt, source_id)
        ),
        "global-medicines-atlas.open-medic-all-release-bronze-qualification": lambda: (
            _is_successful_open_medic_receipt(root, receipt, source_id)
        ),
        "global-medicines-atlas.australian-mbs-bronze-source-receipt": lambda: (
            _is_successful_australian_mbs_receipt(root, receipt, source_id)
        ),
    }
    if schema_id in specialized:
        return specialized[schema_id]()
    if not (
        schema_id.endswith(("-live-qualification", "-acquisition-success"))
        or schema_id
        == "global-medicines-atlas.international-public-bronze-qualification"
    ):
        return False
    admitted = receipt.get("accepted_admission_count")
    releases = receipt.get("accepted_release_count")
    failed_releases = receipt.get("release_failed_count")
    successful_admission = isinstance(admitted, int) and admitted > 0
    successful_release = (
        isinstance(releases, int) and releases > 0 and failed_releases == 0
    )
    return (
        successful_admission or successful_release
    ) and _contains_exact_value(receipt, source_id)


def _is_successful_australian_mbs_receipt(  # ruff: ignore[too-many-return-statements, too-many-branches, too-many-locals, too-many-statements]
    root: Path, receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Validate a raw B1/B2 MBS receipt without qualifying projections."""

    if source_id != "au-mbs" or receipt.get("source_id") != source_id:
        return False
    boundaries = receipt.get("boundaries")
    if not isinstance(boundaries, Mapping):
        return False
    boundaries = cast("Mapping[str, Any]", boundaries)
    claims = (
        receipt.get("schema_version") == AU_MBS_QUALIFICATION_SCHEMA_VERSION,
        receipt.get("qualification_scope") == "raw_b1_b2_only",
        receipt.get("evidence_class") == "live",
        receipt.get("source_version") == "2026-08-01",
        receipt.get("acquisition_id") == AU_MBS_ACQUISITION_ID,
        receipt.get("receipt_id") == AU_MBS_RECEIPT_ID,
        receipt.get("content_id") == AU_MBS_PAYLOAD_SHA256,
        receipt.get("qualification_state") == "accepted",
        boundaries.get("source_record_projection_qualified") is False,
        boundaries.get("m112_federation_accepted") is False,
        boundaries.get("published_at_observed") is False,
        boundaries.get("source_effective_at_in_b1_receipt") is False,
    )
    if not all(claims):
        return False
    b2 = receipt.get("b2")
    if not isinstance(b2, Mapping):
        return False
    b2 = cast("Mapping[str, Any]", b2)
    b2_claims = (
        receipt.get("rights_state") == "permitted",
        receipt.get("reuse_disposition") == "extend",
        receipt.get("admission_state") == "accepted",
        receipt.get("effective_date") == "2026-08-01",
        b2.get("state") == "external_reference_only",
        b2.get("payload_sha256") == AU_MBS_PAYLOAD_SHA256,
        b2.get("byte_count") == AU_MBS_PAYLOAD_BYTE_COUNT,
        b2.get("payload_bytes_retained_locally") is False,
        receipt.get("authority")
        == {
            "current_release_contract": "quality/qualifications/mbs-current-release-contract.json",
            "publication_authorization": "quality/qualifications/australian-mbs-harvest-publication-authorization.json",
            "rights_issue": "https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5467052330",
        },
    )
    if not all(b2_claims):
        return False
    contract_path = "quality/qualifications/mbs-current-release-contract.json"
    authorization_path = "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
    try:
        current_contract = json.loads(
            (root / contract_path).read_text(encoding="utf-8")
        )
        publication_authorization = json.loads(
            (root / authorization_path).read_text(encoding="utf-8")
        )
    except OSError, ValueError, TypeError:
        return False
    if not isinstance(current_contract, Mapping) or not isinstance(
        publication_authorization, Mapping
    ):
        return False
    current_contract = cast("Mapping[str, Any]", current_contract)
    publication_authorization = cast(
        "Mapping[str, Any]", publication_authorization
    )
    hosted = receipt.get("hosted_publication")
    lifecycle = receipt.get("admission_lifecycle")
    if not isinstance(hosted, Mapping) or not isinstance(lifecycle, Mapping):
        return False
    hosted = cast("Mapping[str, Any]", hosted)
    lifecycle = cast("Mapping[str, Any]", lifecycle)
    authorization_claims = (
        current_contract.get("source_id") == source_id,
        current_contract.get("effective_date") == "2026-08-01",
        current_contract.get("publication_authorized") is True,
        publication_authorization.get("external_publication_authorized")
        is True,
        publication_authorization.get(
            "maintainer_asserted_redistribution_permission"
        )
        is True,
        publication_authorization.get("allowed_sources") == [source_id],
        hosted.get("workflow_run")
        == "https://github.com/edithatogo/global-medicines-atlas/actions/runs/37163925043",
        hosted.get("workflow_commit")
        == "644f3f6cfd2b76b0866d5ecb90dde397d67a51eb",
        hosted.get("source_archive_revision") == AU_MBS_ARCHIVE_REVISION,
        hosted.get("lifecycle_metadata_revision")
        == "1e4971c35c0ef45026168a8e2498d1bd57a3c324",
        hosted.get("anonymous_digest_verification") == "passed",
        hosted.get("temporary_source_bytes_removed") is True,
        hosted.get("verified_lifecycle_objects")
        == AU_MBS_VERIFIED_LIFECYCLE_OBJECT_COUNT,
        lifecycle.get("required_order") == ["landed", "accepted"],
        lifecycle.get("landed_predecessor_present") is True,
        lifecycle.get("qualification_blocked") is False,
        receipt.get("boundaries", {}).get("source_record_projection_qualified")
        is False,
        receipt.get("boundaries", {}).get("m112_federation_accepted") is False,
    )
    if not all(authorization_claims):
        return False

    files = receipt.get("files")
    archive = receipt.get("archive")
    if not isinstance(files, Mapping) or not isinstance(archive, Mapping):
        return False
    files = cast("Mapping[str, Any]", files)
    archive = cast("Mapping[str, Any]", archive)
    expected_files = {
        "source_receipt": (
            f"quality/bronze/receipts/au-mbs/{AU_MBS_ACQUISITION_ID}.json",
            "14fb98f49eb4e92dc467c0781a1cbd8a3409994b28059922783558235e97b21a",
        ),
        "acquisition_event": (
            f"quality/bronze/acquisitions/au-mbs/{AU_MBS_ACQUISITION_ID}.json",
            "0473edd93fe9c2781701116febbd68a0c68262b74be5b4de52409d5c52570d30",
        ),
        "landed_admission": (
            f"quality/bronze/admissions/au-mbs/{AU_MBS_ACQUISITION_ID}/56434cc0e027f2d8b082060feee63c490959b63a26a6aff91c01f84614432a12.json",
            "a2e4cb971425c78b9d39cdceb46420bc4beb5b0006636d94911a2013e0b414b6",
        ),
        "accepted_admission": (
            f"quality/bronze/admissions/au-mbs/{AU_MBS_ACQUISITION_ID}/39df4d1a14f1b90d1be41ae9e1fab7b99c9c75385f735b00831c8c199a1350f0.json",
            "25dcc63b950ee330b28cfdd66747e4708891701703f8a91bda3c3b569d5fee7a",
        ),
        "b2_manifest": (
            f"quality/bronze/raw-evidence/au-mbs/{AU_MBS_ACQUISITION_ID}/manifest.json",
            "4104bc85b891dd489e94378c40129870ef98f087c0e28862feb759a3723501fb",
        ),
    }
    for key, (relative, digest) in expected_files.items():
        claimed = files.get(key)
        if not isinstance(claimed, Mapping):
            return False
        try:
            actual_digest = sha256((root / relative).read_bytes()).hexdigest()
        except OSError:
            return False
        claimed_file = cast("Mapping[str, Any]", claimed)
        if (
            claimed_file != {"path": relative, "sha256": digest}
            or actual_digest != digest
        ):
            return False
    try:
        source = SourceReceipt.model_validate_json(
            (root / expected_files["source_receipt"][0]).read_bytes()
        )
        event = AcquisitionEvent.model_validate_json(
            (root / expected_files["acquisition_event"][0]).read_bytes()
        )
        landed = BronzeAdmissionRecord.model_validate_json(
            (root / expected_files["landed_admission"][0]).read_bytes()
        )
        admission = BronzeAdmissionRecord.model_validate_json(
            (root / expected_files["accepted_admission"][0]).read_bytes()
        )
        b2_manifest = RawEvidenceManifest.model_validate_json(
            (root / expected_files["b2_manifest"][0]).read_bytes()
        )
    except OSError, ValueError, TypeError, KeyError, json.JSONDecodeError:
        return False
    if not _australian_mbs_admission_has_landed_predecessor(root, admission):
        return False
    if source.temporal is None or not b2_manifest.rows:
        return False
    b2_row = b2_manifest.rows[0]
    source_claims = (
        source.source.source_id == source_id,
        source.receipt_id == AU_MBS_RECEIPT_ID,
        source.payload.sha256 == AU_MBS_PAYLOAD_SHA256,
        source.payload.byte_count == AU_MBS_PAYLOAD_BYTE_COUNT,
        source.rights_state.value == "permitted",
        source.retrieval.status.value == "succeeded",
        source.reuse is not None,
        event.source_id == source_id,
        event.acquisition_id == source.temporal.acquisition_id,
        event.payload_sha256 == source.payload.sha256,
        event.rights_state is not None,
        admission.state.value == "accepted",
        admission.acquisition_id == event.acquisition_id,
        admission.content_id == source.payload.sha256,
        landed.state.value == "landed",
        landed.acquisition_id == event.acquisition_id,
        landed.content_id == source.payload.sha256,
        admission.supersedes_decision_id == landed.decision_id,
        b2_row.state.value == "external_reference_only",
        b2_row.source_id == source_id,
        b2_row.acquisition_id == event.acquisition_id,
        b2_row.content_id == source.payload.sha256,
        b2_row.external_reference == AU_MBS_RAW_REFERENCE,
    )
    if not all(source_claims) or event.rights_state is None:
        return False
    if source.reuse is None or source.reuse.disposition.value != "extend":
        return False
    if not {
        "local_clones",
        "github",
        "hugging_face",
        "source_registry",
    }.issubset(set(source.reuse.searched_surfaces)):
        return False
    archive_path = f"quality/bronze/references/au-mbs/{AU_MBS_ACQUISITION_ID}/archive-manifest.json"
    try:
        raw_archive_value = json.loads(
            (root / archive_path).read_text(encoding="utf-8")
        )
    except OSError, ValueError, TypeError, json.JSONDecodeError:
        return False
    if not isinstance(raw_archive_value, Mapping):
        return False
    raw_archive = cast("Mapping[str, Any]", raw_archive_value)
    object_values = raw_archive.get("objects", [])
    contract = raw_archive.get("contract")
    if not isinstance(object_values, list) or not isinstance(contract, Mapping):
        return False
    object_values = cast("list[Any]", object_values)
    raw_objects: list[Mapping[str, Any]] = []
    for item in object_values:
        if isinstance(item, Mapping):
            typed_item = cast("Mapping[str, Any]", item)
            if typed_item.get("role") == "raw":
                raw_objects.append(typed_item)
    if len(raw_objects) != 1:
        return False
    raw_object = raw_objects[0]
    archive_claims = (
        archive.get("path") == archive_path,
        archive.get("revision") == AU_MBS_ARCHIVE_REVISION,
        archive.get("root_manifest_path_present") is False,
        raw_archive.get("source_id") == source_id,
        raw_archive.get("profile_state") == "accepted",
        raw_archive.get("data_acquired") is False,
        raw_object.get("sha256") == source.payload.sha256,
        raw_object.get("bytes") == source.payload.byte_count,
        raw_object.get("path")
        == f"raw/mbs/releases/2026-08-01/{AU_MBS_PAYLOAD_SHA256}.xml",
        cast("Mapping[str, Any]", contract).get("effective_date")
        == "2026-08-01",
    )
    return all(archive_claims)


def _australian_mbs_admission_has_landed_predecessor(
    root: Path, admission: BronzeAdmissionRecord
) -> bool:
    """Require a durable landed decision superseded by accepted admission."""

    predecessor_id = admission.supersedes_decision_id
    if admission.state.value != "accepted" or predecessor_id is None:
        return False
    landed_path = (
        root
        / "quality/bronze/admissions/au-mbs"
        / AU_MBS_ACQUISITION_ID
        / f"{predecessor_id}.json"
    )
    try:
        landed = BronzeAdmissionRecord.model_validate_json(
            landed_path.read_bytes()
        )
    except OSError, ValueError, TypeError, json.JSONDecodeError:
        return False
    return (
        landed.state.value == "landed"
        and landed.acquisition_id == admission.acquisition_id
        and landed.content_id == admission.content_id
        and landed.decision_id == predecessor_id
    )


def _is_successful_nice_utilisation_receipt(
    root: Path, receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Require approved internal rights and the complete private restore."""
    authorization_path = (
        "quality/qualifications/nice-utilisation-acquisition-authorization.json"
    )
    try:
        raw_authorization = json.loads(_read(root, authorization_path))
    except OSError, json.JSONDecodeError:
        return False
    if not isinstance(raw_authorization, Mapping):
        return False
    authorization = cast("Mapping[str, Any]", raw_authorization)
    payload_count = receipt.get("payload_count")
    admitted_count = receipt.get("accepted_admission_count")
    manifest_count = receipt.get("acquisition_manifest_count")
    release_count = receipt.get("release_count")
    archive = receipt.get("private_archive")
    hashes = receipt.get("payload_sha256")
    if not isinstance(archive, Mapping):
        return False
    archive = cast("Mapping[str, Any]", archive)
    if not isinstance(hashes, list):
        return False
    hashes = cast("list[object]", hashes)
    return (
        source_id == "gb-nice-medicines-utilisation"
        and receipt.get("source_id") == source_id
        and receipt.get("schema_version") == 1
        and receipt.get("evidence_class") == "live_private_acquisition"
        and receipt.get("rights_state") == "restricted"
        and receipt.get("publication_authorized") is False
        and receipt.get("external_publication_authorized") is False
        and isinstance(payload_count, int)
        and not isinstance(payload_count, bool)
        and payload_count == NICE_UTILISATION_EXPECTED_PAYLOAD_COUNT
        and isinstance(admitted_count, int)
        and not isinstance(admitted_count, bool)
        and admitted_count == payload_count
        and isinstance(manifest_count, int)
        and not isinstance(manifest_count, bool)
        and manifest_count == payload_count
        and isinstance(release_count, int)
        and not isinstance(release_count, bool)
        and release_count == NICE_UTILISATION_EXPECTED_RELEASE_COUNT
        and release_count == authorization.get("expected_release_count")
        and len(hashes) == payload_count
        and all(
            isinstance(value, str)
            and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value)
            for value in hashes
        )
        and archive.get("clean_room_restore_verified") is True
        and archive.get("restored_payload_digests_match") is True
        and archive.get("restored_payload_count") == payload_count
        and authorization.get("decision_status") == "approved_internal"
        and authorization.get("acquisition_authorized") is True
        and authorization.get("internal_retention_authorized") is True
        and authorization.get("public_release_authorized") is False
        and authorization.get("external_publication_authorized") is False
    )


def _is_successful_fda_shortages_receipt(
    receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Require the bounded FDA shortages internal Bronze receipt contract."""
    return (
        source_id == "us-fda-drug-shortages"
        and receipt.get("schema_version") == 1
        and not isinstance(receipt.get("schema_version"), bool)
        and receipt.get("evidence_class") == "live_internal_historical"
        and receipt.get("prompt_complete") is True
        and receipt.get("current_bulk_export_complete") is True
        and receipt.get("historical_list_snapshot_inventory_complete") is True
        and receipt.get("historical_list_snapshot_count")
        == FDA_SHORTAGES_HISTORICAL_SNAPSHOT_COUNT
        and receipt.get("qualified_temporal_corpus")
        == "complete_current_export_and_129_monthly_lists"
        and receipt.get("internal_retention_authorized") is True
        and receipt.get("public_release_authorized") is False
        and receipt.get("external_publication_performed") is False
        and receipt.get("current_source_record_rows", 0) > 0
        and not isinstance(receipt.get("current_source_record_rows"), bool)
        and receipt.get("current_source_record_projection_count") == 1
        and receipt.get("current_recovered_source_record_projection_count") == 1
        and receipt.get("current_source_record_parquet_pairs_byte_identical")
        == 1
        and receipt.get("unique_historical_list_snapshots_archived")
        == FDA_SHORTAGES_HISTORICAL_SNAPSHOT_COUNT
        and receipt.get("archive_checksums_verified", 0) > 0
        and not isinstance(receipt.get("archive_checksums_verified"), bool)
        and receipt.get("historical_detail_snapshot_coverage_complete") is False
        and _contains_exact_value(receipt, source_id)
    )


def _is_successful_sweden_receipt(
    receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Require the exact private aggregate receipt, archive and boundaries."""
    query = receipt.get("query")
    retention = receipt.get("retention")
    rights = receipt.get("rights_boundary")
    if not all(
        isinstance(value, Mapping) for value in (query, retention, rights)
    ):
        return False
    query = cast("Mapping[str, Any]", query)
    retention = cast("Mapping[str, Any]", retention)
    rights = cast("Mapping[str, Any]", rights)
    return (
        source_id == SWEDEN_SOURCE_ID
        and receipt.get("schema_version") == 1
        and not isinstance(receipt.get("schema_version"), bool)
        and receipt.get("source_id") == SWEDEN_SOURCE_ID
        and receipt.get("workflow_commit") == SWEDEN_WORKFLOW_COMMIT
        and receipt.get("workflow_conclusion") == "success"
        and receipt.get("evidence_class")
        == "live_private_source_generated_aggregate"
        and receipt.get("payload_count") == SWEDEN_PAYLOAD_COUNT
        and receipt.get("payload_byte_count") == [1771, 1772, 1795, 1791, 1771]
        and receipt.get("payload_sha256") == list(SWEDEN_PAYLOAD_SHA256)
        and query.get("year") == ["2025"]
        and query.get("measure_ids") == [1, 2, 3, 4, 9]
        and query.get("atc_codes") == ["TOTALT"]
        and query.get("regions") == ["0"]
        and query.get("ages") == [str(value) for value in range(1, 19)]
        and query.get("sexes") == ["3"]
        and query.get("cell_count_upper_bound") == SWEDEN_CELL_COUNT_UPPER_BOUND
        and query.get("maximum_cells_per_query") == SWEDEN_MAXIMUM_CELLS
        and query.get("maximum_atc_codes_per_query") == SWEDEN_MAXIMUM_ATC_CODES
        and retention.get("dataset")
        == "edithatogo/global-medicines-atlas-socialstyrelsen-private"
        and retention.get("revision")
        == "f8489957e64b2122d0cc31964addecb5164f65f0"
        and retention.get("archive_byte_count") == SWEDEN_ARCHIVE_BYTE_COUNT
        and retention.get("archive_sha256")
        == "aa9b10dcb0b910d48402ae2f4699cee6730e34e54e9891569790d548ddb6fa48"
        and retention.get("private") is True
        and retention.get("authenticated_pinned_revision_readback_verified")
        is True
        and retention.get("clean_room_recovered_payload_count")
        == SWEDEN_PAYLOAD_COUNT
        and retention.get(
            "temporary_runner_payload_bytes_removed_after_digest_verification"
        )
        is True
        and rights.get("coarse_rights_state") == "unknown"
        and rights.get("internal_retention_authorized") is True
        and rights.get("maintainer_licence_approved") is False
        and rights.get("publication_authorized") is False
        and rights.get("external_publication_authorized") is False
        and rights.get("person_level_data_acquired") is False
        and rights.get("bulk_download_acquired") is False
    )


def _is_successful_norpd_receipt(
    root: Path, receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Require the exact hosted private NorPD report and its decision bounds."""
    try:
        authorization_value = json.loads(
            _read(root, NORPD_AUTHORIZATION_RELATIVE)
        )
    except OSError, json.JSONDecodeError:
        return False
    if not isinstance(authorization_value, Mapping):
        return False
    authorization = cast("Mapping[str, Any]", authorization_value)
    sources = authorization.get("sources")
    if not isinstance(sources, list):
        return False
    source_entries = cast("list[object]", sources)
    if len(source_entries) != NORDIC_AUTHORIZED_SOURCE_COUNT:
        return False
    norway = cast("Mapping[str, Any]", source_entries[1])
    retention = receipt.get("retention")
    rights = receipt.get("rights_boundary")
    if not isinstance(retention, Mapping) or not isinstance(rights, Mapping):
        return False
    retention = cast("Mapping[str, Any]", retention)
    rights = cast("Mapping[str, Any]", rights)
    payload_sha256 = receipt.get("payload_sha256")
    payload_size = receipt.get("payload_byte_count")
    archive_sha256 = retention.get("archive_sha256")
    archive_size = retention.get("archive_byte_count")
    revision = retention.get("revision")
    workflow_commit = receipt.get("workflow_commit")

    def valid_sha256(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value)
        )

    def valid_git_sha(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == GIT_SHA_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value)
        )

    return (
        source_id == NORPD_SOURCE_ID
        and receipt.get("schema_version") == 1
        and not isinstance(receipt.get("schema_version"), bool)
        and receipt.get("source_id") == NORPD_SOURCE_ID
        and receipt.get("workflow_run") == NORPD_WORKFLOW_RUN
        and receipt.get("workflow_conclusion") == "success"
        and valid_git_sha(workflow_commit)
        and receipt.get("evidence_class")
        == "live_private_historical_aggregate_report"
        and receipt.get("report_period") == "2014-2018"
        and receipt.get("report_url")
        == "https://www.fhi.no/contentassets/4df2902e8492453bb22c219bf69d8f71/191303_legemiddelstatistikk2019.pdf"
        and receipt.get("payload_count") == 1
        and isinstance(payload_size, int)
        and not isinstance(payload_size, bool)
        and payload_size > 0
        and valid_sha256(payload_sha256)
        and receipt.get("public_release_authorized") is False
        and receipt.get("external_publication_authorized") is False
        and retention.get("dataset")
        == "edithatogo/global-medicines-atlas-norpd-private"
        and valid_git_sha(revision)
        and retention.get("private") is True
        and retention.get("gated") is False
        and isinstance(archive_size, int)
        and not isinstance(archive_size, bool)
        and archive_size > 0
        and valid_sha256(archive_sha256)
        and retention.get("authenticated_pinned_revision_readback_verified")
        is True
        and retention.get("clean_room_recovered_payload_count") == 1
        and retention.get(
            "temporary_runner_payload_bytes_removed_after_digest_verification"
        )
        is True
        and rights.get("coarse_rights_state") == "unknown"
        and rights.get("internal_retention_authorized") is True
        and rights.get("maintainer_licence_approved") is False
        and rights.get("publication_authorized") is False
        and rights.get("external_publication_authorized") is False
        and rights.get("person_level_data_acquired") is False
        and rights.get("post_2020_coverage_asserted") is False
        and norway.get("source_id") == NORPD_SOURCE_ID
        and norway.get("decision_date") == "2026-10-01"
        and norway.get("decision_status") == "approved_internal"
        and norway.get("acquisition_authorized") is True
        and norway.get("internal_retention_authorized") is True
        and norway.get("public_release_authorized") is False
        and norway.get("external_publication_authorized") is False
    )


def _source_entry(
    root: Path, relative: str, collection: str, source_id: str
) -> Mapping[str, Any] | None:
    """Return one unique source-specific row from a governed JSON ledger."""

    try:
        document = json.loads((root / relative).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    if not isinstance(document, Mapping):
        return None
    typed_document = cast("Mapping[str, Any]", document)
    rows = typed_document.get(collection)
    if not isinstance(rows, list):
        return None
    matches: list[Mapping[str, Any]] = []
    for row in cast("list[object]", rows):
        if isinstance(row, Mapping):
            candidate = cast("Mapping[str, Any]", row)
            if candidate.get("source_id") == source_id:
                matches.append(candidate)
    if len(matches) != 1:
        return None
    return matches[0]


def _valid_open_medic_sha256(value: object) -> bool:
    """Return whether value is a lowercase SHA-256 digest."""

    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


def _valid_open_medic_positive_count(value: object) -> bool:
    """Reject bools as counts while requiring a positive integer."""

    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_open_medic_release_item(item: object) -> bool:
    """Require one accepted release with distinct content identities."""

    if not isinstance(item, Mapping):
        return False
    row = cast("Mapping[str, Any]", item)
    identity_valid = (
        isinstance(row.get("year"), int)
        and not isinstance(row.get("year"), bool)
        and row.get("admission") == "accepted"
    )
    digests_valid = all(
        _valid_open_medic_sha256(row.get(name))
        for name in (
            "acquisition_id",
            "payload_sha256",
            "source_records_sha256",
        )
    )
    counts_valid = all(
        _valid_open_medic_positive_count(row.get(name))
        for name in ("payload_byte_count", "source_record_count")
    )
    return identity_valid and digests_valid and counts_valid


def _open_medic_release_items(
    receipt: Mapping[str, Any],
) -> list[Mapping[str, Any]] | None:
    """Return all valid annual rows in their declared release order."""

    items = receipt.get("items")
    if not isinstance(items, list):
        return None
    raw_items = cast("list[object]", items)
    if any(not _valid_open_medic_release_item(item) for item in raw_items):
        return None
    rows = cast("list[Mapping[str, Any]]", raw_items)
    years = [row["year"] for row in rows]
    acquisition_ids = [row["acquisition_id"] for row in rows]
    payload_digests = [row["payload_sha256"] for row in rows]
    release_count = len(OPEN_MEDIC_RELEASE_YEARS)
    release_set_valid = (
        years == list(OPEN_MEDIC_RELEASE_YEARS)
        and len(set(acquisition_ids)) == release_count
        and len(set(payload_digests)) == release_count
        and len({row["source_records_sha256"] for row in rows}) == release_count
    )
    return rows if release_set_valid else None


def _open_medic_release_manifest_identity_valid(
    manifest: Mapping[str, Any],
) -> bool:
    """Require a release manifest bound to the approved public archive."""

    return all((
        manifest.get("schema_id")
        == "global-medicines-atlas.open-medic-bronze-release-manifest",
        manifest.get("schema_version") == 1,
        manifest.get("source_id") == OPEN_MEDIC_SOURCE_ID,
        manifest.get("public_dataset") == OPEN_MEDIC_DATASET,
        manifest.get("immutable_revision") == OPEN_MEDIC_REVISION,
        manifest.get("public_manifest_sha256")
        == OPEN_MEDIC_PUBLIC_MANIFEST_SHA256,
    ))


def _open_medic_manifest_release_items(
    manifest: Mapping[str, Any],
) -> list[Mapping[str, Any]] | None:
    """Project validated release records from the pinned manifest."""

    releases = manifest.get("releases")
    if not isinstance(releases, list):
        return None
    raw_releases = cast("list[object]", releases)
    if len(raw_releases) != len(OPEN_MEDIC_RELEASE_YEARS):
        return None
    release_items: list[Mapping[str, Any]] = []
    receipt_digests: list[str] = []
    expected_item_keys = (
        "year",
        "payload_sha256",
        "payload_byte_count",
        "acquisition_id",
        "admission",
        "source_record_count",
        "source_records_sha256",
    )
    for raw_release in raw_releases:
        if not isinstance(raw_release, Mapping):
            return None
        release = cast("Mapping[str, Any]", raw_release)
        digests_valid = all(
            _valid_open_medic_sha256(release.get(key))
            for key in (
                "public_archive_receipt_sha256",
                "public_archive_payload_sha256",
            )
        )
        payload_matches = release.get(
            "public_archive_payload_sha256"
        ) == release.get("payload_sha256") and release.get(
            "public_archive_payload_byte_count"
        ) == release.get("payload_byte_count")
        if not digests_valid or not payload_matches:
            return None
        receipt_digests.append(
            cast("str", release["public_archive_receipt_sha256"])
        )
        release_items.append({
            key: release.get(key) for key in expected_item_keys
        })
    release_identity_valid = [
        item.get("year") for item in release_items
    ] == list(OPEN_MEDIC_RELEASE_YEARS) and len(set(receipt_digests)) == len(
        OPEN_MEDIC_RELEASE_YEARS
    )
    return release_items if release_identity_valid else None


def _open_medic_expected_release_items(
    root: Path,
) -> list[Mapping[str, Any]] | None:
    """Load release identities from the content-bound qualification manifest."""

    try:
        raw_manifest = (
            root / OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
        ).read_bytes()
        document = json.loads(raw_manifest)
    except OSError, json.JSONDecodeError:
        return None
    manifest_digest_valid = (
        sha256(raw_manifest).hexdigest() == OPEN_MEDIC_RELEASE_MANIFEST_SHA256
    )
    if not manifest_digest_valid or not isinstance(document, Mapping):
        return None
    manifest = cast("Mapping[str, Any]", document)
    if not _open_medic_release_manifest_identity_valid(manifest):
        return None
    return _open_medic_manifest_release_items(manifest)


def _open_medic_receipt_scope_valid(
    receipt: Mapping[str, Any], items: list[Mapping[str, Any]]
) -> bool:
    """Match the exact linked archive, completeness boundary, and totals."""

    release_count = len(OPEN_MEDIC_RELEASE_YEARS)
    summary_counts_valid = all(
        isinstance(receipt.get(name), int)
        and not isinstance(receipt.get(name), bool)
        and receipt.get(name) == release_count
        for name in (
            "accepted_admission_count",
            "release_count",
            "recovered_acquisition_count",
            "source_record_projection_count",
            "recovered_source_record_projection_count",
            "source_record_parquet_pairs_byte_identical",
        )
    )
    totals_valid = (
        receipt.get("payload_byte_count")
        == sum(row["payload_byte_count"] for row in items)
        and receipt.get("source_record_count")
        == sum(row["source_record_count"] for row in items)
        and _valid_open_medic_positive_count(receipt.get("payload_byte_count"))
        and _valid_open_medic_positive_count(receipt.get("source_record_count"))
    )
    return all((
        receipt.get("schema_version") == 1,
        not isinstance(receipt.get("schema_version"), bool),
        receipt.get("source_id") == OPEN_MEDIC_SOURCE_ID,
        receipt.get("evidence_class") == "live_public_archive_reuse",
        receipt.get("source_live_qualified") is True,
        receipt.get("source_bytes_committed") is False,
        receipt.get("existing_public_archive_verified") is True,
        receipt.get("external_publication_performed") is False,
        receipt.get("prompt_id") == OPEN_MEDIC_PROMPT_ID,
        receipt.get("prompt_complete") is False,
        receipt.get("rights") == "Etalab-2.0",
        receipt.get("public_dataset") == OPEN_MEDIC_DATASET,
        receipt.get("immutable_revision") == OPEN_MEDIC_REVISION,
        receipt.get("reuse_disposition") == "link",
        receipt.get("reuse_revision") == OPEN_MEDIC_REVISION,
        _valid_open_medic_sha256(receipt.get("public_manifest_sha256")),
        receipt.get("public_manifest_sha256")
        == OPEN_MEDIC_PUBLIC_MANIFEST_SHA256,
        receipt.get("public_manifest_files_verified")
        == OPEN_MEDIC_PUBLIC_MANIFEST_FILE_COUNT,
        summary_counts_valid,
        totals_valid,
        receipt.get("canonical_medicine_identity_claimed") is False,
        receipt.get("cross_country_comparability_claimed") is False,
        receipt.get("regulatory_approval_claimed") is False,
    ))


def _open_medic_rights_valid(root: Path) -> bool:
    """Require matching source-specific acquisition and reuse approvals."""

    source_id = OPEN_MEDIC_SOURCE_ID
    authorization = _source_entry(
        root,
        OPEN_MEDIC_ACQUISITION_AUTHORIZATION_RELATIVE,
        "sources",
        source_id,
    )
    disposition = _source_entry(
        root,
        OPEN_MEDIC_RIGHTS_DISPOSITION_RELATIVE,
        "entries",
        source_id,
    )
    rights = _source_entry(
        root,
        OPEN_MEDIC_RIGHTS_LEDGER_RELATIVE,
        "entries",
        source_id,
    )
    try:
        catalog = json.loads(
            (root / CATALOG_RELATIVE).read_text(encoding="utf-8")
        )
    except OSError, json.JSONDecodeError:
        return False
    if not isinstance(catalog, Mapping):
        return False
    typed_catalog = cast("Mapping[str, Any]", catalog)
    sources = typed_catalog.get("sources")
    if not isinstance(sources, list):
        return False
    catalog_matches: list[Mapping[str, Any]] = []
    for row in cast("list[object]", sources):
        if isinstance(row, Mapping):
            candidate = cast("Mapping[str, Any]", row)
            if candidate.get("source_id") == source_id:
                catalog_matches.append(candidate)
    if len(catalog_matches) != 1:
        return False
    source = catalog_matches[0]
    expected_status = (
        f"approved_public_exact_inventory:{OPEN_MEDIC_DATASET}"
        f"@{OPEN_MEDIC_REVISION}"
    )
    if authorization is None or disposition is None or rights is None:
        return False
    return all((
        authorization.get("decision_status") == "approved_public",
        authorization.get("acquisition_authorized") is True,
        authorization.get("internal_retention_authorized") is True,
        authorization.get("public_release_authorized") is True,
        authorization.get("external_publication_authorized") is True,
        disposition.get("catalogue_rights_status") == expected_status,
        disposition.get("recommended_disposition") == "approved_public_source",
        disposition.get("internal_acquisition")
        == "approved_for_exact_reviewed_scope",
        disposition.get("public_derived_release")
        == "approved_for_exact_manifest",
        disposition.get("blocker") is None,
        rights.get("disposition") == "approved_public_source",
        rights.get("redistribute") == "permitted",
        rights.get("transform") == "permitted",
        rights.get("publish_source_bytes") == "permitted",
        rights.get("maintainer_licence_approved") is True,
        rights.get("maintainer_publication_approved") is True,
        rights.get("public_source_eligible") is True,
        rights.get("public_derived_eligible") is True,
        rights.get("sensitivity") == "public",
        source.get("rights_status") == expected_status,
    ))


def _is_successful_open_medic_receipt(
    root: Path, receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Require the exact approved 12-release Open Medic Bronze receipt."""

    if source_id != OPEN_MEDIC_SOURCE_ID:
        return False
    expected_items = _open_medic_expected_release_items(root)
    if expected_items is None or receipt.get("items") != expected_items:
        return False
    items = _open_medic_release_items(receipt)
    if items is None:
        return False
    return _open_medic_receipt_scope_valid(receipt, items) and (
        _open_medic_rights_valid(root)
    )


def _is_successful_us_live_records_receipt(
    receipt: Mapping[str, Any], source_id: str
) -> bool:
    """Match only accepted, projected, recovered products in a bounded U.S. run."""
    if (
        receipt.get("schema_version") != 1
        or receipt.get("evidence_class") != "live_bounded_internal"
        or receipt.get("coverage_complete") is not False
        or receipt.get("external_publication_performed") is not False
        or receipt.get("public_release_authorized") is not False
    ):
        return False
    products = receipt.get("record_products")
    if not isinstance(products, list) or not products:
        return False
    raw_products = cast("list[Any]", products)
    if any(not isinstance(product, Mapping) for product in raw_products):
        return False
    typed_products = cast("list[Mapping[str, Any]]", raw_products)
    product_source_ids = [
        product.get("source_id") for product in typed_products
    ]
    row_counts = [product.get("row_count") for product in typed_products]
    if (
        any(
            not isinstance(product_id, str) or not product_id
            for product_id in product_source_ids
        )
        or any(
            not isinstance(row_count, int)
            or isinstance(row_count, bool)
            or row_count <= 0
            for row_count in row_counts
        )
        or len(set(product_source_ids)) != len(product_source_ids)
    ):
        return False
    product_count = len(product_source_ids)
    count_fields = (
        "source_count",
        "acquisition_succeeded_count",
        "acquisition_failed_count",
        "accepted_admission_count",
        "quarantined_admission_count",
        "recovered_acquisition_count",
        "source_record_projection_count",
        "recovered_source_record_projection_count",
        "source_record_parquet_pairs_byte_identical",
    )
    counts = cast(
        "dict[str, int | None]",
        {name: receipt.get(name) for name in count_fields},
    )
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in counts.values()
    ):
        return False
    valid_counts = cast("dict[str, int]", counts)
    return (
        source_id in product_source_ids
        and valid_counts["source_count"] > 0
        and valid_counts["acquisition_succeeded_count"]
        == valid_counts["source_count"]
        and valid_counts["acquisition_failed_count"] == 0
        and valid_counts["accepted_admission_count"] == product_count
        and valid_counts["recovered_acquisition_count"] == product_count
        and valid_counts["source_record_projection_count"] == product_count
        and valid_counts["recovered_source_record_projection_count"]
        == product_count
        and valid_counts["source_record_parquet_pairs_byte_identical"]
        == product_count
        and valid_counts["accepted_admission_count"]
        + valid_counts["quarantined_admission_count"]
        <= valid_counts["acquisition_succeeded_count"]
    )


def receipt_backed_landing_evidence(  # ruff: ignore[too-many-branches]
    root: Path, source_ids: set[str]
) -> dict[str, str]:
    """Return each source's direct, successful, non-publication receipt."""

    path = root / LANDING_OVERRIDES_RELATIVE
    if not path.is_file():
        return {}
    overrides = json.loads(path.read_text(encoding="utf-8")).get(
        "overrides", []
    )
    evidence: dict[str, str] = {}
    for override in overrides:
        source_id = override.get("source_id")
        if (
            not isinstance(source_id, str)
            or source_id not in source_ids
            or override.get("state") != "landed_and_evidenced"
        ):
            continue
        is_mbs_qualification_reference = False
        for relative in override.get("evidence_references", []):
            if not isinstance(relative, str) or not _is_receipt_reference(
                relative
            ):
                continue
            if relative == CMS_RECORDS_RELATIVE and source_id in CMS_SOURCE_IDS:
                try:
                    qualified = qualified_cms_sources(
                        root / CMS_RIGHTS_RELATIVE,
                        root / CMS_RAW_RELATIVE,
                        root / CMS_RECORDS_RELATIVE,
                    )
                except OSError, ValueError, KeyError, TypeError:
                    continue
                if source_id in qualified:
                    evidence[source_id] = relative
                    break
            receipt_path = root / relative
            if not receipt_path.is_file():
                continue
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(receipt, Mapping) and _is_successful_bronze_receipt(
                root, cast("Mapping[str, Any]", receipt), source_id
            ):
                evidence[source_id] = relative
                if (
                    source_id == "au-mbs"
                    and relative == AU_MBS_QUALIFICATION_RELATIVE
                ):
                    is_mbs_qualification_reference = True
                break
        if source_id == "au-mbs" and not is_mbs_qualification_reference:
            evidence.pop("au-mbs", None)
    return evidence


def receipt_backed_landing_source_ids(
    root: Path, source_ids: set[str]
) -> set[str]:
    """Return source IDs bound by direct, non-publication Bronze receipts.

    Queue labels alone are not evidence. An override can contribute only when
    it names a landed source and an existing JSON receipt contains that exact
    source ID. Publication-only references remain deliberately excluded.
    """
    return set(receipt_backed_landing_evidence(root, source_ids))


def _property(
    property_id: str,
    *,
    mandatory: bool,
    state: PropertyState,
    requirement_ids: Sequence[str],
    evidence: Sequence[str],
    blocker_ids: Sequence[str],
    notes: str,
) -> dict[str, Any]:
    return {
        "property_id": property_id,
        "mandatory": mandatory,
        "state": state,
        "requirement_ids": list(requirement_ids),
        "evidence": list(evidence),
        "blocker_ids": list(blocker_ids),
        "notes": notes,
    }


def _files_pass(root: Path, checks: Mapping[str, Sequence[str]]) -> bool:
    return all(
        _contains(root, relative, needles)
        for relative, needles in checks.items()
    )


def _evaluate_file_property(
    root: Path,
    *,
    property_id: str,
    mandatory: bool,
    requirement_ids: Sequence[str],
    checks: Mapping[str, Sequence[str]],
    passing_notes: str,
    failing_notes: str,
    blocker_id: str,
) -> dict[str, Any]:
    evidence = tuple(checks)
    if _files_pass(root, checks):
        return _property(
            property_id,
            mandatory=mandatory,
            state="evidenced",
            requirement_ids=requirement_ids,
            evidence=evidence,
            blocker_ids=(),
            notes=passing_notes,
        )
    return _property(
        property_id,
        mandatory=mandatory,
        state="blocked",
        requirement_ids=requirement_ids,
        evidence=evidence,
        blocker_ids=(blocker_id,),
        notes=failing_notes,
    )


# ruff: ignore[too-many-locals]
def evaluate_completeness(
    root: Path,
    *,
    use_bounded_scope: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Measure the approved bounded horizon and retain full-universe counts."""

    catalog = json.loads(_read(root, CATALOG_RELATIVE))
    sources = catalog["sources"]
    classes: dict[str, ScopeClass] = {}
    for source in sources:
        classes[str(source["source_id"])] = classify_catalog_source(source)
    full_scope = {
        source_id
        for source_id, scope in classes.items()
        if scope == "bronze_in_scope"
    }
    active_scope = full_scope
    if use_bounded_scope:
        decision_path = root / SCOPE_DECISION_RELATIVE
        if not decision_path.is_file():
            raise ValueError(
                "approved bounded Bronze scope decision is missing"
            )
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        if decision.get("decision_id") != "bronze-bounded-scope-v1":
            raise ValueError("unsupported bounded Bronze scope decision")
        active_values_raw = decision.get("active_source_ids")
        if not isinstance(active_values_raw, list):
            raise ValueError("bounded Bronze active_source_ids must be strings")
        active_values_raw = cast("list[Any]", active_values_raw)
        if not all(isinstance(value, str) for value in active_values_raw):
            raise ValueError("bounded Bronze active_source_ids must be strings")
        active_values: list[str] = [
            cast("str", value) for value in active_values_raw
        ]
        active_scope = set(active_values)
        universe_digest = sha256(
            ("\n".join(sorted(full_scope)) + "\n").encode()
        ).hexdigest()
        active_digest = sha256(
            ("\n".join(sorted(active_scope)) + "\n").encode()
        ).hexdigest()
        scope_checks = (
            len(active_scope) != len(active_values),
            not active_scope,
            not active_scope <= full_scope,
            len(full_scope) != BOUNDED_SCOPE_FULL_SOURCE_COUNT,
            len(active_scope) != BOUNDED_SCOPE_ACTIVE_SOURCE_COUNT,
            len(full_scope - active_scope)
            != BOUNDED_SCOPE_DEFERRED_SOURCE_COUNT,
            decision.get("full_scope_source_count") != len(full_scope),
            decision.get("full_scope_source_ids_sha256") != universe_digest,
            decision.get("active_scope_source_count") != len(active_scope),
            decision.get("active_scope_source_ids_sha256") != active_digest,
            decision.get("deferred_source_count")
            != len(full_scope - active_scope),
        )
        if any(scope_checks):
            raise ValueError(
                "bounded Bronze scope decision does not match catalog"
            )
    in_scope = active_scope
    ingested_full = {
        str(source["source_id"])
        for source in sources
        if source.get("implemented_ingestion") is True
        and str(source["source_id"]) in full_scope
    }
    receipt_evidence_full = receipt_backed_landing_evidence(root, full_scope)
    adapter_landing_full = landing_source_ids(root, full_scope)
    landed_full = (
        adapter_landing_full | set(receipt_evidence_full) | ingested_full
    )
    # The au-mbs receipt upgrades the catalog's legacy parser marker to a
    # source-specific raw B1/B2 landing, without qualifying its projection.
    if "au-mbs" in receipt_evidence_full:
        landed_full.add("au-mbs")
    landed = landed_full & in_scope
    missing = sorted(in_scope - landed)
    missing_full = full_scope - landed_full
    receipt_evidence = {
        source_id: path
        for source_id, path in receipt_evidence_full.items()
        if source_id in in_scope
    }
    deferred_count = len(full_scope - in_scope)
    inventory = {
        "catalog_source_count": len(sources),
        "bronze_in_scope_count": len(in_scope),
        "full_bronze_source_universe_count": len(full_scope),
        "deferred_source_count": deferred_count,
        "full_scope_landing_count": len(landed_full),
        "full_scope_missing_count": len(missing_full),
        "fixture_only_count": sum(
            scope == "fixture_only" for scope in classes.values()
        ),
        "excluded_count": sum(
            scope == "excluded" for scope in classes.values()
        ),
        "in_scope_without_landing_or_blocker": len(missing),
        "missing_coverage_is_not_negative_evidence": True,
    }
    evidence = (
        CATALOG_RELATIVE,
        AUTHORITIES["bronze_completion_spec"],
        *((SCOPE_DECISION_RELATIVE,) if use_bounded_scope else ()),
        "src/global_medicines_atlas/adapters/fixture_contracts.py",
        LANDING_OVERRIDES_RELATIVE,
        *sorted(set(receipt_evidence.values())),
    )
    if missing:
        property_row = _property(
            "completeness",
            mandatory=True,
            state="blocked",
            requirement_ids=("M-095", "S-012"),
            evidence=evidence,
            blocker_ids=("bronze-ingest-incomplete",),
            notes=(
                f"{len(missing)} in-scope public/no-credential sources lack "
                "observable adapter, fixture, implemented_ingestion, or "
                "direct successful receipt-backed "
                "landing evidence. Excluded and fixture-only rows are not "
                "scored as negative evidence."
            ),
        )
    else:
        property_row = _property(
            "completeness",
            mandatory=True,
            state="evidenced",
            requirement_ids=("M-095", "S-012"),
            evidence=evidence,
            blocker_ids=(),
            notes=(
                "Every bronze-in-scope catalog source has landing evidence. "
                "Excluded sources remain catalogued, not incomplete."
            ),
        )
    return property_row, inventory


def evaluate_properties(
    root: Path,
    *,
    use_bounded_scope: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate every bronze maturity property against repository files."""

    completeness, _inventory = evaluate_completeness(
        root,
        use_bounded_scope=use_bounded_scope,
    )
    return [
        completeness,
        _evaluate_file_property(
            root,
            property_id="immutability",
            mandatory=True,
            requirement_ids=("M-092", "M-094", "M-102"),
            checks={
                "src/global_medicines_atlas/bronze_landing.py": (
                    "evidentiary truth",
                    "PAYLOAD_DIR",
                    "Parquet is not raw-as-landed",
                ),
                "tests/test_bronze_landing.py": (
                    "payload_bytes_are_preserved",
                    "parquet_is_not_the_payload",
                ),
                "src/global_medicines_atlas/bronze_storage.py": (
                    "ObjectStoragePayloadStore",
                    "ImmutabilityMode",
                    "PayloadStorageReceipt",
                ),
                "tests/test_bronze_storage.py": (
                    "test_local_store_is_explicitly_development_only_and_immutable",
                    "test_object_store_versions_replicates_inventories_and_restores",
                ),
            },
            passing_notes=(
                "Payload bytes and content-addressed receipts are "
                "evidentiary truth; Parquet is analytical only. Local and "
                "durable object-storage paths share an immutable contract."
            ),
            failing_notes=(
                "Bronze landing tests or payload/receipt split are missing."
            ),
            blocker_id="bronze-immutability-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="temporal_identity",
            mandatory=True,
            requirement_ids=("M-099",),
            checks={
                "src/global_medicines_atlas/receipts.py": (
                    "source_published_at",
                    "retrieved_at",
                    "acquisition_id",
                    "valid_from",
                ),
                "tests/test_temporal_identity.py": (
                    "substituting_retrieved_at_for_published_time_fails",
                    "temporal_fields_are_distinct",
                ),
            },
            passing_notes=(
                "Published, retrieved, validity, and acquisition identity "
                "remain independent fields."
            ),
            failing_notes="Temporal identity contracts are incomplete.",
            blocker_id="bronze-temporal-identity-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="provenance",
            mandatory=True,
            requirement_ids=("M-001", "M-092"),
            checks={
                "src/global_medicines_atlas/receipts.py": (
                    "SourceReceipt",
                    "PayloadEvidence",
                    "sha256",
                ),
                "tests/test_source_receipts.py": ("source_receipt",),
            },
            passing_notes="Content-addressed receipts bind payload identity.",
            failing_notes="Receipt provenance contracts are incomplete.",
            blocker_id="bronze-provenance-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="rights",
            mandatory=True,
            requirement_ids=("M-040", "M-095", "M-102"),
            checks={
                "src/global_medicines_atlas/receipts.py": (
                    "RightsState",
                    "SensitivityClassification",
                    "require_publication_permitted",
                ),
                "tests/test_bronze_storage.py": (
                    "test_rights_and_sensitivity_are_independent_publication_gates",
                ),
                "docs/data-sources/SOURCE_RIGHTS.md": ("rights",),
                "DATA_LICENSE.md": ("CC-BY-4.0",),
            },
            passing_notes=(
                "Rights states are explicit. Licensing conclusions remain "
                "a human gate and are not inferred as approved by this "
                "qualification. Sensitivity and publication disposition are "
                "independent and fail closed."
            ),
            failing_notes="Rights documentation or receipt fields are missing.",
            blocker_id="bronze-rights-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="reuse_discovery",
            mandatory=True,
            requirement_ids=("M-098",),
            checks={
                "src/global_medicines_atlas/reuse_gate.py": (
                    "acquire-new",
                    "SEARCH_SURFACES",
                    "require_reuse_decision",
                ),
                "tests/test_reuse_gate.py": (
                    "acquire_new_is_last_resort",
                    "all_dispositions_are_representable",
                ),
                "docs/ECOSYSTEM_REUSE.md": ("Pre-acquisition reuse gate",),
            },
            passing_notes=(
                "Acquisition without the reuse gate fails. Hugging Face is "
                "a search surface here, not bronze maturity evidence."
            ),
            failing_notes="Reuse gate tests or implementation are missing.",
            blocker_id="bronze-reuse-gate-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="lineage",
            mandatory=True,
            requirement_ids=("M-100",),
            checks={
                "src/global_medicines_atlas/openlineage_projection.py": (
                    "eventType",
                    "schemaURL",
                    "gma.payload",
                    "gma.parquet",
                ),
                "tests/test_openlineage_projection.py": (
                    "openlineage_event_uses_real_field_names",
                ),
            },
            passing_notes=(
                "OpenLineage projection keeps payload and Parquet as "
                "distinct datasets. Native receipts remain authoritative."
            ),
            failing_notes="OpenLineage projection evidence is incomplete.",
            blocker_id="bronze-lineage-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="quarantine",
            mandatory=True,
            requirement_ids=("M-089", "M-097"),
            checks={
                "src/global_medicines_atlas/bronze_admission.py": (
                    "quarantined",
                    "rejected-from-processing",
                ),
                "tests/test_bronze_admission.py": (
                    "quarantined_requires_explicit_authorization",
                ),
            },
            passing_notes=(
                "Bronze admission preserves malformed payloads and fails "
                "closed downstream."
            ),
            failing_notes=(
                "Bronze admission/quarantine lifecycle is not evidenced on "
                "this revision. Canonical data-integrity quarantine is a "
                "later or adjacent layer and is not counted."
            ),
            blocker_id="bronze-quarantine-admission",
        ),
        _evaluate_file_property(
            root,
            property_id="reproducibility",
            mandatory=True,
            requirement_ids=("M-094", "M-097"),
            checks={
                "src/global_medicines_atlas/bronze_landing.py": (
                    "def regenerate_parquet",
                ),
                "tests/test_bronze_landing.py": (
                    "acquisition_id_immutable_across_parquet_regeneration",
                ),
            },
            passing_notes=(
                "Parquet regeneration keeps the acquisition identity immutable."
            ),
            failing_notes="Deterministic Parquet regeneration is unevidenced.",
            blocker_id="bronze-regeneration-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="disaster_recovery",
            mandatory=True,
            requirement_ids=("M-082", "M-097", "M-102"),
            checks={
                "src/global_medicines_atlas/bronze_recovery.py": (
                    "CLEAN_ROOM_REBUILD",
                    "PARTIAL_STORAGE_LOSS",
                    "CODE_ROLLBACK_NEWER_PAYLOADS",
                    "def reconstruct_bronze",
                ),
                "tests/test_bronze_recovery.py": (
                    "test_clean_room_rebuild_from_payloads_and_receipts_only",
                    "test_catalogue_deletion_rebuilds_from_receipts",
                    "test_parquet_deletion_regenerates_without_new_acquisition",
                    "test_interrupted_acquisition_fails_closed_then_resumes",
                    "test_partial_storage_loss_rebuilds_analytical_layers",
                    "test_duplicate_retrieval_keeps_one_payload_two_acquisitions",
                ),
                "src/global_medicines_atlas/bronze_storage.py": (
                    "create_checksum_inventory",
                    "rehearse_restore",
                    "rpo_seconds",
                    "rto_seconds",
                ),
                "tests/test_bronze_storage.py": (
                    "test_checksum_inventory_detects_replica_corruption",
                ),
            },
            passing_notes=(
                "Bronze metadata, Parquet, and catalogue are reconstructed "
                "from immutable payloads and receipts across the required "
                "clean-room and loss scenarios. Production operation remains "
                "a separate deployment and qualification gate."
            ),
            failing_notes=(
                "Bronze clean-room reconstruction and loss-scenario evidence "
                "is incomplete."
            ),
            blocker_id="bronze-disaster-recovery-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="security",
            mandatory=True,
            requirement_ids=("M-089",),
            checks={
                "src/global_medicines_atlas/acquisition.py": (
                    "require_reuse_decision",
                    "reject_private_networks",
                ),
                "conductor/design.md": ("Acquired bytes are untrusted",),
                "src/global_medicines_atlas/snapshots.py": (
                    "credential",
                    "secret",
                ),
                "tests/test_source_acquisition.py": (
                    "test_acquisition_without_reuse_gate_fails",
                ),
            },
            passing_notes=(
                "Public ingest uses untrusted-acquisition controls. "
                "Credentials must not be persisted."
            ),
            failing_notes="Untrusted acquisition security evidence is missing.",
            blocker_id="bronze-security-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="performance",
            mandatory=True,
            requirement_ids=("S-012",),
            checks={
                "tests/test_bronze_scale.py": (
                    "evaluate_bronze_scale_budgets",
                    "test_budget_evaluation_fails_closed_on_slow_pipeline",
                ),
                "quality/bronze-scale-budgets.json": (
                    "pipeline_seconds",
                    "parquet_seconds",
                ),
                "src/global_medicines_atlas/bronze_scale.py": (
                    "published bronze scale performance budgets",
                ),
            },
            passing_notes=(
                "Bronze scale/landing budgets are measured in-repo and are "
                "independent of product or dashboard workloads."
            ),
            failing_notes=(
                "No bronze-specific landing performance budget exists. "
                "Product, Scalene, or stable-v1 performance receipts are "
                "not bronze evidence."
            ),
            blocker_id="bronze-landing-performance-budget",
        ),
        _evaluate_file_property(
            root,
            property_id="interoperability",
            mandatory=True,
            requirement_ids=("M-094", "S-013"),
            checks={
                "src/global_medicines_atlas/iceberg_ready.py": (
                    "Python 3.14 core does not import",
                    "Iceberg REST catalogue",
                ),
                "tests/test_iceberg_ready.py": (
                    "test_iceberg_ready_module_does_not_import_pyiceberg",
                    "test_parquet_remains_valid_without_iceberg",
                ),
                "src/global_medicines_atlas/bronze_landing.py": (
                    "analytical representation",
                    "PAYLOAD_DIR",
                ),
            },
            passing_notes=(
                "Source-faithful Parquet is portable. Iceberg-ready "
                "identities exist without requiring Iceberg in core."
            ),
            failing_notes=(
                "Parquet/Iceberg-ready interoperability is incomplete."
            ),
            blocker_id="bronze-interoperability-unevidenced",
        ),
        _evaluate_file_property(
            root,
            property_id="documentation",
            mandatory=True,
            requirement_ids=("M-092", "M-093", "W-007"),
            checks={
                "conductor/design.md": ("Medallion Datahouse",),
                "conductor/requirements.md": ("M-094", "W-007"),
                AUTHORITIES["bronze_completion_spec"]: (
                    "Silver, gold, and platinum implementation",
                ),
                "docs/ECOSYSTEM_REUSE.md": ("Hugging Face",),
            },
            passing_notes=(
                "Bronze horizon, later-layer boundaries, and reuse policy "
                "are documented. Silver/gold remain out of scope."
            ),
            failing_notes="Bronze documentation authorities are incomplete.",
            blocker_id="bronze-documentation-unevidenced",
        ),
    ]


def _blockers_from_properties(
    properties: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    notes = {row["property_id"]: row["notes"] for row in properties}
    evidence = {row["property_id"]: row["evidence"] for row in properties}
    blockers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in properties:
        for blocker_id in row["blocker_ids"]:
            if blocker_id in seen:
                continue
            seen.add(blocker_id)
            blockers.append({
                "blocker_id": blocker_id,
                "property_id": row["property_id"],
                "description": notes[row["property_id"]],
                "evidence": list(evidence[row["property_id"]]),
            })
    return blockers


def _residual_risks(
    properties: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    index = 1
    for row in properties:
        if row["state"] != "blocked":
            continue
        risks.append({
            "risk_id": f"RISK-{index:03d}",
            "description": row["notes"],
            "disposition": "unresolved",
            "blocking": True,
            "evidence": list(row["evidence"]),
        })
        index += 1
    human_gates = (
        (
            (
                "Production disaster-recovery operation, independent backup "
                "storage, RPO, and RTO remain authority-gated; the in-repo "
                "Bronze reconstruction qualification is synthetic and local."
            ),
            [
                (
                    "quality/qualifications/"
                    "stable-v1-production-dr-authority-blocker.json"
                ),
                "docs/operations/governed-recovery-runbook.md",
            ],
        ),
        (
            "Licensing conclusions remain a maintainer human gate.",
            ["docs/governance/licensing-decision.md", "DATA_LICENSE.md"],
        ),
        (
            "Public software or dataset release remains a human gate.",
            ["conductor/autonomy.md"],
        ),
        (
            (
                "External dataset publication, including Hugging Face "
                "archives, remains a human gate and is not bronze "
                "evidentiary truth."
            ),
            ["docs/ECOSYSTEM_REUSE.md"],
        ),
        (
            "Consequential clinical or policy claims remain a human gate.",
            ["conductor/product.md"],
        ),
    )
    for description, evidence in human_gates:
        risks.append({
            "risk_id": f"RISK-{index:03d}",
            "description": description,
            "disposition": "accepted",
            "blocking": False,
            "evidence": evidence,
        })
        index += 1
    return risks


def run_adversarial_review(
    root: Path,
    properties: Sequence[Mapping[str, Any]],
    *,
    bronze_mature: bool,
) -> dict[str, Any]:
    """Review criteria against code, tests, and docs. Not a second person."""

    findings: list[dict[str, str]] = []
    all_evidence = [
        path
        for row in properties
        if row["state"] == "evidenced"
        for path in row["evidence"]
    ]
    forbidden = reject_forbidden_evidence(all_evidence)
    if forbidden:
        findings.append({
            "finding_id": "ADV-FORBIDDEN-EVIDENCE",
            "severity": "error",
            "detail": (
                "Later-layer or publication artefacts were used as bronze "
                f"evidence: {', '.join(forbidden)}."
            ),
        })
    else:
        findings.append({
            "finding_id": "ADV-FORBIDDEN-EVIDENCE",
            "severity": "info",
            "detail": (
                "No stable-v1, dashboard, Silver/Gold, or Hugging Face "
                "publication artefact was accepted as bronze evidence."
            ),
        })

    for row in properties:
        for path in row["evidence"]:
            if row["state"] == "evidenced" and not _exists(root, path):
                findings.append({
                    "finding_id": f"ADV-MISSING-{row['property_id']}",
                    "severity": "error",
                    "detail": (
                        f"Property {row['property_id']} is evidenced but "
                        f"{path} is absent."
                    ),
                })
            text = ""
            if _exists(root, path):
                text = _read(root, path).lower()
            if any(needle in text for needle in FORBIDDEN_NEEDLES):
                findings.append({
                    "finding_id": f"ADV-NEEDLE-{row['property_id']}",
                    "severity": "error",
                    "detail": (
                        f"{path} contains later-layer success language "
                        "that cannot qualify bronze."
                    ),
                })

    mandatory_blocked = [
        row["property_id"]
        for row in properties
        if row["mandatory"] and row["state"] != "evidenced"
    ]
    if bronze_mature and mandatory_blocked:
        findings.append({
            "finding_id": "ADV-FALSE-MATURITY",
            "severity": "error",
            "detail": (
                "Bronze was declared mature while mandatory properties "
                f"remain blocked: {', '.join(mandatory_blocked)}."
            ),
        })
    elif mandatory_blocked:
        findings.append({
            "finding_id": "ADV-FALSE-MATURITY",
            "severity": "info",
            "detail": (
                "Bronze maturity is not declared. Blocked mandatory "
                f"properties: {', '.join(mandatory_blocked)}."
            ),
        })
    else:
        findings.append({
            "finding_id": "ADV-FALSE-MATURITY",
            "severity": "info",
            "detail": "Every mandatory property is evidenced.",
        })

    observed_ids = [row["property_id"] for row in properties]
    if observed_ids != list(PROPERTY_IDS):
        findings.append({
            "finding_id": "ADV-PROPERTY-SET",
            "severity": "error",
            "detail": "Property set does not match the required criteria.",
        })
    else:
        findings.append({
            "finding_id": "ADV-PROPERTY-SET",
            "severity": "info",
            "detail": "All 14 required bronze properties were evaluated.",
        })

    passed = all(item["severity"] != "error" for item in findings)
    return {
        "kind": "independent-repository-evidence-review",
        "actor": "criteria-versus-code-tests-docs",
        "method": (
            "Each mandatory property was checked against repository files "
            "and tests. Hugging Face publication, stable-v1 qualification "
            "success, dashboards, and Silver/Gold behaviour were rejected "
            "as bronze evidence. Missing excluded-source coverage is not "
            "treated as negative evidence. The actor is not a person."
        ),
        "passed": passed,
        "findings": findings,
    }


def evaluate_repository(
    root: Path,
    *,
    clock: Callable[[], datetime] | None = None,
    git_commit: str | None = None,
    use_bounded_scope: bool = True,
) -> dict[str, Any]:
    """Return a fail-closed bronze maturity report for ``root``."""

    properties = evaluate_properties(root, use_bounded_scope=use_bounded_scope)
    _, inventory = evaluate_completeness(
        root,
        use_bounded_scope=use_bounded_scope,
    )
    mandatory_ok = all(
        row["state"] == "evidenced" for row in properties if row["mandatory"]
    )
    bronze_mature = mandatory_ok
    blockers = _blockers_from_properties(properties)
    if bronze_mature and blockers:
        bronze_mature = False
    review = run_adversarial_review(
        root,
        properties,
        bronze_mature=bronze_mature,
    )
    if not review["passed"]:
        bronze_mature = False
    stamp = (clock or (lambda: datetime.now(UTC)))()
    report = {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "horizon": HORIZON if use_bounded_scope else FULL_SCOPE_HORIZON,
        "evaluated_at": stamp.isoformat(),
        "git_commit": git_commit or "unspecified",
        "authorities": AUTHORITIES,
        "properties": properties,
        "residual_risks": _residual_risks(properties),
        "blockers": blockers,
        "adversarial_review": review,
        "bronze_mature": bronze_mature,
        "qualification_state": "qualified" if bronze_mature else "blocked",
        "report_complete": all(
            row["state"] in {"evidenced", "blocked"} for row in properties
        ),
        "completeness_inventory": inventory,
    }
    if bronze_mature:
        report["blockers"] = []
    return report


def dump_report(report: Mapping[str, Any]) -> str:
    """Serialize a report with a trailing newline."""

    return json.dumps(report, indent=2, ensure_ascii=True) + "\n"
