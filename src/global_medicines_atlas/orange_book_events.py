"""Source-native product approval dates; never continuing approval intervals."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date as calendar_date
from typing import Any

DATASET = "edithatogo/global-medicines-atlas-fda-open-20260821"
REVISION = "ab3a79a63b5df9f1dca3eb4122d39179c4247417"
SHA256 = "caaa826d4ba72f1abb156c8a38063929d3930d3700e091130474a876513a4da3"
URI = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/data/us-fda-orange-book.zip"
RIGHTS = (
    "quality/qualifications/source-rights-review-ledger.json#us-fda-orange-book"
)


def product_events(payload: bytes, concepts: set[str]) -> list[dict[str, Any]]:
    """Join exact FDA application type/number/product keys, preserving gaps."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [
            x
            for x in archive.infolist()
            if x.filename.lower() == "products.txt"
        ]
        if len(members) != 1 or members[0].file_size > 20 * 1024 * 1024:
            raise ValueError(
                "ambiguous or oversized Orange Book products member"
            )
        text = archive.read(members[0]).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="~")
    required = {"Appl_Type", "Appl_No", "Product_No", "Approval_Date"}
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)) or not required <= set(headers):
        raise ValueError("Orange Book product/date schema differs")
    matches: dict[str, set[str]] = {}
    for row in reader:
        if None in row or any(row.get(key) is None for key in required):
            raise ValueError("malformed Orange Book product row")
        app = row["Appl_No"].strip()
        product = row["Product_No"].strip()
        kind = {"N": "NDA", "A": "ANDA"}.get(row["Appl_Type"].strip())
        if (
            kind is None
            or not re.fullmatch(r"\d{1,6}", app)
            or not re.fullmatch(r"\d{1,3}", product)
        ):
            continue
        identity = f"us-drugsfda:{kind}{app.zfill(6)}:{product.zfill(3)}"
        if identity in concepts:
            matches.setdefault(identity, set()).add(
                row["Approval_Date"].strip()
            )
    output: list[dict[str, Any]] = []
    for identity in sorted(concepts):
        dates = matches.get(identity, set())
        native = next(iter(dates)) if len(dates) == 1 else None
        date = None
        state = "unmatched" if not dates else "conflicting_dates"
        if native is not None:
            state = "non_exact_native_date"
            try:
                # FDA defines this field as a date, not a timezone or interval.
                date = calendar_date.strptime(native, "%b %d, %Y").isoformat()
                state = "exact_product_approval_date"
            except ValueError:
                pass
        output.append({
            "concept_id": identity,
            "qualification": state,
            "approval_date": date,
            "native_approval_dates": sorted(dates),
            "source_id": "us-fda-orange-book",
            "source_uri": URI,
            "source_revision": REVISION,
            "source_sha256": SHA256,
            "source_member": "products.txt",
            "rights_review": RIGHTS,
            "continuing_approval_established": False,
            "validity_interval": None,
        })
    return output
