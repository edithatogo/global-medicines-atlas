"""Calendar-only P7 date diagnostics preserve ambiguous and native states."""

import json
from hashlib import sha256

from test_mbs_workbook_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic receipt
)
from test_mbs_workbook_values import payload_with

from global_medicines_atlas.mbs_p7_calendar_profile import (
    profile_p7_calendar_dates,
)


def test_profile_counts_unique_ambiguous_invalid_and_serial_dates() -> None:
    payload = payload_with(
        '<c r="C2" t="inlineStr"><is><t>15.07.2024</t></is></c>'
        '<c r="C3" t="inlineStr"><is><t>05.06.2024</t></is></c>'
        '<c r="C4" t="inlineStr"><is><t>06.06.2024</t></is></c>'
        '<c r="C5" t="inlineStr"><is><t>31.02.2024</t></is></c>'
        '<c r="C6"><v>45000</v></c>'
    )
    profile = profile_p7_calendar_dates(payload, _receipt(payload))

    assert profile["source_sha256"] == sha256(payload).hexdigest()
    assert profile["date_order_selected"] is False
    assert profile["source_values_emitted"] is False
    assert profile["by_field"]["ItemStartDate"] == {
        "ambiguous_calendar_order": 1,
        "invalid": 1,
        "unique_calendar_date": 2,
        "unsupported_serial_date": 1,
    }
    assert "15.07.2024" not in json.dumps(profile)
