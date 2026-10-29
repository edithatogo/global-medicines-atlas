"""Export all source URLs or acquire an explicitly selected local-only batch."""

from __future__ import annotations

import argparse
import csv
import io
import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import Field

from global_medicines_atlas.acquisition import AcquisitionPolicy, acquire_source
from global_medicines_atlas.models import FrozenModel
from global_medicines_atlas.receipts import EvidenceClass, FailureReceipt
from global_medicines_atlas.reuse_gate import (
    ReuseDisposition,
    ReuseGateDecision,
    require_reuse_decision,
)
from global_medicines_atlas.source_catalog import (
    AccessMode,
    AuthenticationMode,
    InterfaceStatus,
    MedicineDataSource,
    load_source_catalog,
)
from global_medicines_atlas.source_landing_factory import (
    LandingDisposition,
    LandingOverrides,
)

ROOT = Path(__file__).resolve().parents[1]


class DownloadSelection(FrozenModel):
    """Exact batch input; references record existing authority, never grant it."""

    source_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    surface: Literal["download", "single_api_response"] = "download"
    expected_url: str = Field(min_length=1)
    retention_authority_reference: str = ""
    reuse_decision: ReuseGateDecision | None = None
    max_bytes: int = Field(default=64 * 1024 * 1024, ge=1, le=256 * 1024 * 1024)


def url_inventory(sources: tuple[MedicineDataSource, ...]) -> str:
    """Project the canonical catalogue to a readable all-URLs file offline."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow((
        "source_id",
        "access_mode",
        "interface_status",
        "authentication",
        "download_url",
        "api_url",
        "landing_page",
        "documentation_url",
        "formats",
        "rights_status",
        "integration_layer",
    ))
    for source in sorted(sources, key=lambda item: item.source_id):
        writer.writerow((
            source.source_id,
            source.access_mode,
            source.interface_status,
            source.authentication,
            source.download_url or "",
            source.api_url or "",
            source.landing_page,
            source.documentation_url,
            "|".join(source.formats),
            source.rights_status,
            source.integration_layer,
        ))
    return output.getvalue()


def selected_source(
    selection: DownloadSelection, sources: tuple[MedicineDataSource, ...]
) -> MedicineDataSource:
    """Validate the exact endpoint and reuse gate before any network access."""

    source = next(s for s in sources if s.source_id == selection.source_id)
    override = next(
        (
            item
            for item in LandingOverrides.load().overrides
            if item.source_id == source.source_id
        ),
        None,
    )
    if override is not None and (
        not override.preserves_source_bytes
        or override.state
        in {
            LandingDisposition.TEMPORARILY_UNAVAILABLE,
            LandingDisposition.SUPERSEDED_BY_REUSE,
        }
    ):
        raise ValueError(f"existing source restriction: {override.reason}")
    if source.authentication is not AuthenticationMode.NONE:
        raise ValueError("credentialed sources require their existing adapter")
    if source.interface_status not in {
        InterfaceStatus.SUPPORTED,
        InterfaceStatus.DOCUMENTED_DOWNLOAD,
    }:
        raise ValueError("interactive, restricted or undocumented interface")
    api = selection.surface == "single_api_response"
    url = source.api_url if api else source.download_url
    if url is None or str(url) != selection.expected_url:
        raise ValueError("expected_url must match the selected catalogue URL")
    if str(url) in {str(source.landing_page), str(source.documentation_url)}:
        raise ValueError("discovery page is not a qualified payload endpoint")
    if not selection.retention_authority_reference.strip():
        raise ValueError(
            "existing exact-source retention authority is required"
        )
    decision = require_reuse_decision(
        selection.reuse_decision, source.source_id
    )
    if decision.disposition is not ReuseDisposition.ACQUIRE_NEW:
        raise ValueError(
            "reuse the existing payload through its recorded route"
        )
    return source.model_copy(
        update={
            "access_mode": AccessMode.API if api else AccessMode.DOWNLOAD,
            "download_url": None if api else source.download_url,
        }
    )


def run_batch(
    selections: tuple[DownloadSelection, ...],
    *,
    sources: tuple[MedicineDataSource, ...],
    output: Path,
    repository_root: Path,
    execute: bool = False,
) -> list[dict[str, str]]:
    """Skip blocked rows, receipt each attempted source, never publish or crawl."""

    ids = [selection.source_id for selection in selections]
    if not ids:
        raise ValueError("batch must select at least one source")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source IDs in batch")
    target = output.resolve()
    if not target.is_relative_to((repository_root / "build").resolve()):
        raise ValueError("batch output must be a fresh directory under build/")
    if execute:
        target.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, str]] = []
    for selection in selections:
        result = {"source_id": selection.source_id, "state": "blocked"}
        try:
            source = selected_source(selection, sources)
        except (ValueError, StopIteration) as error:
            result["reason"] = str(error) or "unknown catalogue source"
        else:
            result["state"] = "ready"
            if execute:
                directory = target / source.source_id
                receipt = acquire_source(
                    source.source_id,
                    directory / "payload.bin",
                    repository_root=repository_root,
                    catalog=(source,),
                    evidence_class=EvidenceClass.LIVE,
                    reuse_decision=selection.reuse_decision,
                    policy=AcquisitionPolicy(max_bytes=selection.max_bytes),
                )
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "receipt.json").write_text(
                    receipt.model_dump_json(indent=2) + "\n", encoding="utf-8"
                )
                (directory / "selection.json").write_text(
                    selection.model_dump_json(indent=2) + "\n", encoding="utf-8"
                )
                result["state"] = (
                    "failed"
                    if isinstance(receipt, FailureReceipt)
                    else "acquired_local"
                )
        results.append(result)
        if execute:
            (target / "results.json").write_text(
                json.dumps(results, indent=2) + "\n", encoding="utf-8"
            )
    return results


def run_archive_all(
    manifest: Path, *, output: Path, execute: bool = False
) -> list[dict[str, str]]:
    """Account for every catalogue source and execute eligible finite batches."""
    config = json.loads(manifest.read_text(encoding="utf-8"))
    sources = load_source_catalog()
    queue = json.loads(
        (
            ROOT / "quality/qualifications/bronze-source-landing-queue.json"
        ).read_text()
    )
    outcomes = {
        row["source_id"]: {
            "source_id": row["source_id"],
            "state": {
                "credentialed_and_excluded": "excluded_auth",
                "rights_blocked": "blocked_rights",
                "temporarily_unavailable": "blocked_endpoint",
                "manual_only_documented_acquisition": "needs_source_recipe",
            }.get(row.get("state"), "needs_source_review"),
            "reason": row["reason"],
            "next_action": row["next_action"],
        }
        for row in queue["items"]
    }
    if set(outcomes) != {source.source_id for source in sources}:
        raise ValueError("archive-all queue does not cover exact catalogue")
    for row in config["reuse"]:
        if row["source_id"] not in outcomes or not row["evidence_reference"]:
            raise ValueError("invalid existing-archive reference")
        outcomes[row["source_id"]] = dict(row, state="reused_verified_archive")
    for row in config.get("blockers", []):
        if row["source_id"] not in outcomes:
            raise ValueError("unknown blocked source")
        outcomes[row["source_id"]] = row
    selected: set[str] = set()
    for batch in config["batches"]:
        selections = tuple(
            DownloadSelection.model_validate(row)
            for row in json.loads((ROOT / batch).read_text())
        )
        if selected.intersection(row.source_id for row in selections):
            raise ValueError("source selected in multiple batches")
        selected.update(row.source_id for row in selections)
        selections = tuple(
            row
            for row in selections
            if outcomes[row.source_id]["state"] != "reused_verified_archive"
        )
        if not selections:
            continue
        directory = output / Path(batch).parent.name
        if execute and directory.exists():
            results = resume_batch(selections, directory)
        else:
            results = run_batch(
                selections,
                sources=sources,
                output=directory,
                repository_root=ROOT,
                execute=execute,
            )
        for row in results:
            outcomes[row["source_id"]] = row
    results = [outcomes[key] for key in sorted(outcomes)]
    if execute:
        output.mkdir(parents=True, exist_ok=True)
        (output / "archive-all-results.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )
    return results


def resume_batch(
    selections: tuple[DownloadSelection, ...], directory: Path
) -> list[dict[str, str]]:
    """Reuse exact local successful receipts; never retry failures implicitly."""
    results = json.loads((directory / "results.json").read_text())
    if {row["source_id"] for row in results} != {
        row.source_id for row in selections
    }:
        raise ValueError("existing batch inventory differs")
    for selection in selections:
        saved = directory / selection.source_id
        row = next(
            item for item in results if item["source_id"] == selection.source_id
        )
        if row["state"] != "acquired_local":
            continue
        if json.loads(
            (saved / "selection.json").read_text()
        ) != selection.model_dump(mode="json"):
            raise ValueError("existing batch selection differs")
        receipt = json.loads((saved / "receipt.json").read_text())
        if (
            sha256((saved / "payload.bin").read_bytes()).hexdigest()
            != receipt["payload"]["sha256"]
        ):
            raise ValueError("existing payload digest differs")
    return results


def main(argv: list[str] | None = None) -> int:
    """Default to offline inventory or preview; execution requires a batch file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls-output", type=Path)
    parser.add_argument("--batch", type=Path)
    parser.add_argument("--archive-all", type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build/source-batch"
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.archive_all:
        if args.batch:
            parser.error("choose --archive-all or --batch")
        if not args.output.resolve().is_relative_to((ROOT / "build").resolve()):
            parser.error("archive-all output must be under build/")
        results = run_archive_all(
            args.archive_all, output=args.output, execute=args.execute
        )
        print(json.dumps(results, indent=2))
        return int(
            any(row["state"] in {"failed", "blocked"} for row in results)
        )
    if args.execute and args.batch is None:
        parser.error("--execute requires --batch or --archive-all")
    sources = load_source_catalog()
    if args.urls_output:
        args.urls_output.parent.mkdir(parents=True, exist_ok=True)
        args.urls_output.write_text(url_inventory(sources), encoding="utf-8")
    if args.batch is None:
        if not args.urls_output:
            print(url_inventory(sources), end="")
        return 0
    selections = tuple(
        DownloadSelection.model_validate(row)
        for row in json.loads(args.batch.read_text(encoding="utf-8"))
    )
    results = run_batch(
        selections,
        sources=sources,
        output=args.output,
        repository_root=ROOT,
        execute=args.execute,
    )
    print(json.dumps(results, indent=2))
    return int(any(row["state"] in {"blocked", "failed"} for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
