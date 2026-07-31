"""Executable contributor, operator, source, and incident documentation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

DOCUMENT_SECTIONS = {
    "CONTRIBUTING.md": (
        "## Development",
        "## Medicine source and adapter changes",
        "## Pull-request evidence",
    ),
    "docs/operations/README.md": ("## Procedures", "## Action boundaries"),
    "docs/data-sources/source-onboarding.md": (
        "## Intake",
        "## Qualification lifecycle",
        "## Acceptance and deferral",
    ),
    "docs/operations/data-incident-response.md": (
        "## Scope and reporting boundary",
        "## Severity",
        "## Response procedure",
        "## Recovery and closure evidence",
    ),
    "docs/operations/governed-recovery-runbook.md": (
        "## Rehearse",
        "## Operator checks",
        "## Limitations and authority gates",
    ),
}


def test_operational_documents_have_required_sections_and_local_links() -> None:
    for relative, sections in DOCUMENT_SECTIONS.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        for section in sections:
            assert section in text, f"{relative}: {section}"
        for target in LINK.findall(text):
            if "://" in target or target.startswith("#"):
                continue
            local_target = target.split("#", 1)[0]
            assert (path.parent / local_target).resolve().is_file(), (
                f"{relative}: broken link {target}"
            )


@pytest.mark.parametrize(
    ("form", "required_ids"),
    [
        (
            "source-onboarding.yml",
            {
                "jurisdiction",
                "authority",
                "dimension",
                "url",
                "access",
                "authentication",
                "rights",
                "time",
                "limitations",
                "boundary",
            },
        ),
        (
            "data-incident.yml",
            {
                "severity",
                "affected",
                "jurisdiction",
                "source",
                "observed",
                "clocks",
                "expected",
                "containment",
                "safety",
            },
        ),
    ],
)
def test_issue_forms_match_documented_operational_contracts(
    form: str,
    required_ids: set[str],
) -> None:
    yaml = pytest.importorskip("yaml")
    document = yaml.safe_load(
        (ROOT / ".github/ISSUE_TEMPLATE" / form).read_text(encoding="utf-8")
    )
    fields = {item["id"]: item for item in document["body"]}
    assert required_ids <= fields.keys()
    for field_id in required_ids:
        field = fields[field_id]
        field_required = field.get("validations", {}).get("required") is True
        option_required = False
        if not field_required:
            options = field.get("attributes", {}).get("options", ())
            option_required = bool(options) and all(
                isinstance(option, dict) and option.get("required") is True
                for option in options
            )
        assert field_required or option_required, field_id
