"""Static hosted-only publication and preservation contracts."""

from pathlib import Path

import yaml


def test_hosted_mbs_workflow_preserves_archive_and_verifies_before_cleanup() -> (
    None
):
    path = Path(".github/workflows/australian-mbs-release.yml")
    text = path.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    job = document["jobs"]["release"]
    assert job["environment"] == "australian-hf-publication"
    assert document["permissions"] == {}
    assert "cron:" in text
    assert "require_mbs_hosted_authority(contract)" in text
    assert "parent_commit=parent_revision" in text
    assert "CommitOperationAdd" in text
    assert "CommitOperationDelete" not in text
    assert "token=False" in text
    assert "snapshot_download" not in text
    assert "if not receipt['data_acquired']" in text
    assert text.index(
        "gh issue comment 340 --body-file build/mbs-hosted-receipt.json"
    ) < text.index("shutil.rmtree(target)")
    assert "huggingface-hub==1.14.0" in text
    assert "--python 3.14.6" in text
