"""Standing outbound prohibition applies to every workflow command."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
PYTHON_SOURCES = sorted((ROOT / "scripts").rglob("*.py")) + sorted(
    (ROOT / "src").rglob("*.py")
)
OUTBOUND = re.compile(
    r"\bgh\s+(?:issue|pr)\s+comment\b|issues\.createComment|chat\.postMessage|sendMail",
    re.IGNORECASE,
)
ISSUE_COMMENT_POST = re.compile(
    r"issues/[0-9]+/comments[\s\S]{0,200}?(?:--method[\s\S]{0,40}?POST|['\"]POST['\"])",
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
    assert ISSUE_COMMENT_POST.search(path.read_text()) is None


@pytest.mark.parametrize("path", PYTHON_SOURCES, ids=lambda path: path.name)
def test_python_source_has_no_outbound_issue_comment_post(path):
    source = path.read_text(encoding="utf-8")
    assert ISSUE_COMMENT_POST.search(source) is None
    assert OUTBOUND.search(source) is None
