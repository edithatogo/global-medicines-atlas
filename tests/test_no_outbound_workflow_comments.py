"""Standing outbound prohibition applies to every workflow command."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
OUTBOUND = re.compile(
    r"\bgh\s+(?:issue|pr)\s+comment\b|issues\.createComment|chat\.postMessage|sendMail",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_has_no_outbound_comment_command_or_issue_write(path):
    document = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    for job in document.get("jobs", {}).values():
        permissions = job.get("permissions", {})
        assert permissions.get("issues") != "write"
        for step in job.get("steps", []):
            assert OUTBOUND.search(step.get("run", "")) is None
