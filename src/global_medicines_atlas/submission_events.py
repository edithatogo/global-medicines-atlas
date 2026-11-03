"""Preserve source-native FDA application-submission observations as events.

An application submission is not an individual product approval or a current
regulatory-status interval. Missing or malformed dates remain explicit.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, cast


def project_submission_events(
    payload: bytes, *, source_uri: str, source_revision: str, source_sha256: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Account for all application and submission rows in the pinned payload."""
    document_raw = json.loads(payload)
    if not isinstance(document_raw, dict):
        raise TypeError("application source must be an object")
    document = cast("dict[str, Any]", document_raw)
    applications = document.get("results")
    if not isinstance(applications, list) or not applications:
        raise ValueError(
            "application source must contain a nonempty results list"
        )
    applications = cast("list[Any]", applications)
    events: list[dict[str, Any]] = []
    applications_with_submissions = 0
    seen_applications: set[str] = set()
    for app_index, application in enumerate(applications):
        if not isinstance(application, dict):
            raise TypeError("application record must be an object")
        application = cast("dict[str, Any]", application)
        number = application.get("application_number")
        if not isinstance(number, str) or not number.strip():
            raise ValueError("application identity is missing")
        if number in seen_applications:
            raise ValueError("duplicate application identity")
        seen_applications.add(number)
        submissions = application.get("submissions", [])
        if not isinstance(submissions, list):
            raise TypeError("application submissions must be a list")
        submissions = cast("list[Any]", submissions)
        applications_with_submissions += bool(submissions)
        for submission_index, submission in enumerate(submissions):
            if not isinstance(submission, dict):
                raise TypeError("submission must be an object")
            submission = cast("dict[str, Any]", submission)
            native_date = submission.get("submission_status_date")
            if native_date is not None and not isinstance(native_date, str):
                raise TypeError("submission date must be source-native text")
            parsed_date = None
            date_state = "missing" if not native_date else "invalid"
            if native_date and re.fullmatch(r"\d{8}", native_date):
                try:
                    parsed_date = date.strptime(
                        native_date, "%Y%m%d"
                    ).isoformat()
                    date_state = "exact_date"
                except ValueError:
                    pass
            events.append({
                "source_path": f"/results/{app_index}/submissions/{submission_index}",
                "application_number": number,
                "application_ordinal": app_index,
                "submission_ordinal": submission_index,
                "submission_type": submission.get("submission_type"),
                "submission_number": submission.get("submission_number"),
                "submission_status": submission.get("submission_status"),
                "submission_status_date_native": native_date,
                "submission_status_date": parsed_date,
                "date_qualification": date_state,
                "source_id": "us-openfda-drugsfda",
                "source_uri": source_uri,
                "source_revision": source_revision,
                "source_sha256": source_sha256,
                "native_submission": submission,
                "product_status_inferred": False,
                "continuing_status_established": False,
            })
    return events, {
        "application_denominator": len(applications),
        "applications_with_submissions": applications_with_submissions,
        "applications_without_submissions": len(applications)
        - applications_with_submissions,
        "submission_count": len(events),
        "exact_date_count": sum(
            e["date_qualification"] == "exact_date" for e in events
        ),
        "missing_date_count": sum(
            e["date_qualification"] == "missing" for e in events
        ),
        "invalid_date_count": sum(
            e["date_qualification"] == "invalid" for e in events
        ),
    }
