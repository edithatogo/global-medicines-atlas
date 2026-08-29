"""Inspect a locally prepared PBS v3 archive without network acquisition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.adapters.au_pbs import (
    inspect_pbs_v3_tags,
    parse_pbs_v3_archive,
)


def main() -> int:
    """Print bounded, source-native tag and receipt information as JSON."""
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--max-tags", type=int, default=128)
    arguments = parser.parse_args()
    result = parse_pbs_v3_archive(arguments.archive.read_bytes())
    print(
        json.dumps(
            {
                "archive_sha256": result.archive_sha256,
                "member": {
                    "path": result.member.path,
                    "sha256": result.member.sha256,
                    "size_bytes": result.member.size_bytes,
                },
                "namespace_uri": result.namespace_uri,
                "effective_date": result.effective_date,
                "record_count": len(result.records),
                "tags": inspect_pbs_v3_tags(
                    result.xml_payload, max_tags=arguments.max_tags
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
