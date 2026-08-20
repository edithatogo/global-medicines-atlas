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
from pathlib import Path
from typing import Any, Literal

from .source_catalog import AccessMode, AuthenticationMode

SCHEMA_ID = "global-medicines-atlas.bronze-maturity-qualification"
HORIZON = "bronze-current-public-scope"
CATALOG_RELATIVE = (
    "src/global_medicines_atlas/data/medicine_source_catalog.json"
)
REPORT_RELATIVE = "quality/qualifications/bronze-maturity.json"
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


def evaluate_completeness(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Measure bronze completeness without treating exclusion as failure."""

    catalog = json.loads(_read(root, CATALOG_RELATIVE))
    sources = catalog["sources"]
    classes: dict[str, ScopeClass] = {}
    for source in sources:
        classes[str(source["source_id"])] = classify_catalog_source(source)
    in_scope = {
        source_id
        for source_id, scope in classes.items()
        if scope == "bronze_in_scope"
    }
    ingested = {
        str(source["source_id"])
        for source in sources
        if source.get("implemented_ingestion") is True
        and str(source["source_id"]) in in_scope
    }
    landed = landing_source_ids(root, in_scope) | ingested
    missing = sorted(in_scope - landed)
    inventory = {
        "catalog_source_count": len(sources),
        "bronze_in_scope_count": len(in_scope),
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
        "src/global_medicines_atlas/adapters/fixture_contracts.py",
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
                "observable adapter, fixture, or implemented_ingestion "
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


def evaluate_properties(root: Path) -> list[dict[str, Any]]:
    """Evaluate every bronze maturity property against repository files."""

    completeness, _inventory = evaluate_completeness(root)
    return [
        completeness,
        _evaluate_file_property(
            root,
            property_id="immutability",
            mandatory=True,
            requirement_ids=("M-092", "M-094"),
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
            },
            passing_notes=(
                "Payload bytes and content-addressed receipts are "
                "evidentiary truth; Parquet is analytical only."
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
            requirement_ids=("M-040", "M-095"),
            checks={
                "src/global_medicines_atlas/receipts.py": ("RightsState",),
                "docs/data-sources/SOURCE_RIGHTS.md": ("rights",),
                "DATA_LICENSE.md": ("CC-BY-4.0",),
            },
            passing_notes=(
                "Rights states are explicit. Licensing conclusions remain "
                "a human gate and are not inferred as approved by this "
                "qualification."
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
        _property(
            "disaster_recovery",
            mandatory=True,
            state="blocked",
            requirement_ids=("M-082",),
            evidence=(
                (
                    "quality/qualifications/"
                    "stable-v1-production-dr-authority-blocker.json"
                ),
                "docs/operations/governed-recovery-runbook.md",
            ),
            blocker_ids=("bronze-production-dr",),
            notes=(
                "Local recovery rehearsals exist for other layers. "
                "Production disaster recovery for bronze payloads remains "
                "authority-gated and is not claimed."
            ),
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
                    "Iceberg metadata is rebuildable",
                ),
                "tests/test_iceberg_ready.py": (
                    "test_core_dependencies_do_not_require_iceberg_or_marquez",
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
) -> dict[str, Any]:
    """Return a fail-closed bronze maturity report for ``root``."""

    properties = evaluate_properties(root)
    _, inventory = evaluate_completeness(root)
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
        "horizon": HORIZON,
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
