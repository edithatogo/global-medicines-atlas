"""Qualify a hosted PBS v3 archive into immutable Bronze products."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

from global_medicines_atlas.adapters.au_pbs import (
    inspect_pbs_v3_tags,
    parse_pbs_v3_archive,
    pbs_v3_source_parquet,
)

AUTHORIZATION_REF = (
    "conductor/decisions/"
    "0009-australian-health-authority-and-public-data-plane.md#rights-and-publication-authority"
)


def qualify(
    archive_path: Path,
    output_dir: Path,
    *,
    source_url: str,
    dataset: str,
) -> dict[str, object]:
    """Admit exact source bytes and write deterministic hosted-stage products."""
    archive = parse_pbs_v3_archive(archive_path.read_bytes())
    if archive.effective_date is None:
        raise ValueError("PBS effective date must be an ISO calendar date")
    try:
        effective_date = date.fromisoformat(archive.effective_date).isoformat()
    except ValueError as error:
        raise ValueError(
            "PBS effective date must be an ISO calendar date"
        ) from error
    parquet = pbs_v3_source_parquet(archive.records)
    output_dir.mkdir(parents=True, exist_ok=False)
    raw_dir = output_dir / "raw" / effective_date
    bronze_dir = output_dir / "bronze" / effective_date
    raw_dir.mkdir(parents=True)
    bronze_dir.mkdir(parents=True)
    raw_path = raw_dir / f"{effective_date}-XML-V3.zip"
    xml_path = bronze_dir / Path(archive.member.path).name
    parquet_path = bronze_dir / "pbs-v3-source.parquet"
    shutil.copyfile(archive_path, raw_path)
    xml_path.write_bytes(archive.xml_payload)
    parquet_path.write_bytes(parquet)
    manifest: dict[str, object] = {
        "schema_id": "global-medicines-atlas.australian-pbs-source-archive",
        "schema_version": 1,
        "source_id": "au-pbs-historical-xml",
        "source_url": source_url,
        "source_effective_date": archive.effective_date,
        "destination_dataset": dataset,
        "authorization_ref": AUTHORIZATION_REF,
        "archive": {
            "path": raw_path.relative_to(output_dir).as_posix(),
            "sha256": archive.archive_sha256,
            "size_bytes": raw_path.stat().st_size,
        },
        "member": {
            "source_path": archive.member.path,
            "path": xml_path.relative_to(output_dir).as_posix(),
            "sha256": archive.member.sha256,
            "size_bytes": archive.member.size_bytes,
        },
        "source_parquet": {
            "path": parquet_path.relative_to(output_dir).as_posix(),
            "sha256": hashlib.sha256(parquet).hexdigest(),
            "size_bytes": len(parquet),
        },
        "namespace_uri": archive.namespace_uri,
        "record_count": len(archive.records),
        "tag_sample": list(inspect_pbs_v3_tags(archive.xml_payload)),
        "raw_bytes_are_source_of_truth": True,
        "parquet_is_rebuildable_projection": True,
        "amt_terminology_bytes_included": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "README.md").write_text(
        "---\npretty_name: Australian PBS source archive\n"
        "license: other\n---\n\n"
        "# Australian PBS source archive\n\n"
        "Exact final public PBS XML v3 schedule archive and receipt-bound "
        "Bronze projections. PBS listing is funding/formulary evidence, not "
        "Australian regulatory approval. The source-native ZIP and XML are "
        "evidentiary truth; Parquet is rebuildable. Redistribution authority "
        f"is recorded in `{AUTHORIZATION_REF}`.\n"
    )
    return manifest


def main() -> int:
    """Run the hosted qualification command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--dataset", required=True)
    arguments = parser.parse_args()
    manifest = qualify(
        arguments.archive,
        arguments.output,
        source_url=arguments.source_url,
        dataset=arguments.dataset,
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
