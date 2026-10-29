"""Bind the maintainer attestation to the independently reproduced output."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTESTATION = ROOT / (
    "quality/qualifications/"
    "australian-pbs-reproduced-silver-output-rights-attestation-20261029.json"
)


def test_attestation_binds_exact_reproduced_output() -> None:
    attestation = json.loads(ATTESTATION.read_text())
    source = attestation["source_report"]
    source_bytes = (ROOT / source["path"]).read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == source["sha256"]
    reconciliation = json.loads(source_bytes)
    output = attestation["authorized_output"]
    package = reconciliation["package"]
    assert reconciliation["independent_execution"] is True
    assert reconciliation["prior_exact_candidate_reproduced"] is False
    binding = package["member_binding"]
    assert output["archive_sha256"] == binding["archive_payload"]["sha256"]
    assert output["member_sha256"] == binding["member_payload"]["sha256"]
    assert output["output_id"] == package["output_id"]
    assert output["parquet_sha256"] == package["parquet"]["sha256"]
    assert output["parquet_bytes"] == package["parquet"]["bytes"]
    assert (
        output["native_core_sha256"]
        == package["coverage"]["native_core_sha256"]
    )
    assert attestation["public_release_rights_attested"] is True
    assert (
        attestation["boundaries"]["instrument_independently_reviewed"] is False
    )
    assert attestation["boundaries"]["v4_admission_performed"] is False
    assert attestation["boundaries"]["public_release_performed"] is False
