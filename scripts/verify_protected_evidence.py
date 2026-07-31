"""Verify an offline protected-evidence snapshot and emit a receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.protected_evidence import (
    EvidenceVerification,
    HostedEvidenceSnapshot,
    ProtectedEvidencePolicy,
    inspect_local_truth,
    verify_protected_evidence,
    write_protected_evidence_receipt,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    policy = ProtectedEvidencePolicy.model_validate_json(
        arguments.policy.read_bytes()
    )
    hosted = HostedEvidenceSnapshot.model_validate_json(
        arguments.snapshot.read_bytes()
    )
    receipt = verify_protected_evidence(
        policy=policy,
        local=inspect_local_truth(arguments.repository),
        hosted=hosted,
    )
    digest_path = write_protected_evidence_receipt(arguments.output, receipt)
    print(
        json.dumps(
            {
                "digest": digest_path.as_posix(),
                "receipt": arguments.output.as_posix(),
                "verification": receipt.evidence_verification.value,
            },
            sort_keys=True,
        )
    )
    return (
        0
        if receipt.evidence_verification is EvidenceVerification.VERIFIED
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
