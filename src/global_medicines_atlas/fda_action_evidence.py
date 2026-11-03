"""Manually reviewed FDA letter evidence for bounded product action events.

The referenced FDA letters are identified by exact downloaded byte digests.
These are historical actions, not assertions of continuing product status.
"""

from __future__ import annotations

import json
from typing import Any

REVIEWS: tuple[dict[str, Any], ...] = (
    {
        "application_number": "ANDA207984",
        "submission_status": "TA",
        "submission_status_date": "20201218",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2020/207984Orig1s000TAltr.pdf",
        "letter_sha256": "11c8e4b8fd578dccec7efa2d5427654701d490c2af31d89c505c6eb0c6ee5eb8",
        "letter_bytes": 309133,
        "letter_pages": [1, 5],
        "product_strengths": {
            "001": "EQ 75MG BASE",
            "002": "EQ 110MG BASE",
            "003": "EQ 150MG BASE",
        },
        "brand_name": "DABIGATRAN ETEXILATE MESYLATE",
        "dosage_form": "CAPSULE",
        "route": "ORAL",
        "ingredient": "DABIGATRAN ETEXILATE MESYLATE",
    },
    {
        "application_number": "BLA761385",
        "submission_status": "AP",
        "submission_status_date": "20260327",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/761385Orig1s000ltr.pdf",
        "letter_sha256": "289fdf6e569aa410598f7f24d6007586baa2e64916cd07260b2efaf1cf8a3629",
        "letter_bytes": 1008225,
        "letter_pages": [1, 12],
        "product_strengths": {"001": "60MG/ML"},
        "brand_name": "PONLIMSI",
        "dosage_form": "INJECTABLE",
        "route": "SUBCUTANEOUS",
        "ingredient": "DENOSUMAB-ADET",
    },
    {
        "application_number": "NDA050744",
        "submission_status": "AP",
        "submission_status_date": "19980930",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/1998/50744ltr.pdf",
        "letter_sha256": "b37388f078d8ac94727bddc793b9b52436897ae63c061e0d5ba82d723197af48",
        "letter_bytes": 36152,
        "letter_pages": [1, 2],
        "product_strengths": {
            "001": "EQ 20MG BASE **Federal Register determination that product was not discontinued or withdrawn for safety or effectiveness reasons**"
        },
        "brand_name": "PERIOSTAT",
        "dosage_form": "CAPSULE",
        "route": "ORAL",
        "ingredient": "DOXYCYCLINE HYCLATE",
        "withdrawal": {
            "qualification": "conflicting_dates",
            "effective_date": None,
            "continuity_between_actions_verified": False,
            "candidates": [
                {
                    "effective_date": "2004-06-04",
                    "source_uri": "https://www.govinfo.gov/content/pkg/FR-2004-05-05/pdf/04-10194.pdf",
                    "source_sha256": "cc60ce8b168eac3c2e1cfaf03f395a5e33dd3a258e346095f8d2040d9a05687f",
                    "source_bytes": 128246,
                    "document_number": "04-10194",
                    "correction": {
                        "document_number": "04-17110",
                        "source_uri": "https://www.govinfo.gov/content/pkg/FR-2004-07-28/pdf/04-17110.pdf",
                        "source_sha256": "15a893ca578852d3eb62a0c07dddaf41bc605d2486a0dbe8a89dce4943eccea5",
                        "source_bytes": 142559,
                        "corrected_application": "ANDA088584",
                    },
                },
                {
                    "effective_date": "2005-06-15",
                    "source_uri": "https://www.govinfo.gov/content/pkg/FR-2005-05-16/pdf/05-9624.pdf",
                    "source_sha256": "427592fd2c5c65bf69a28cb55af43451aa40117ae43a791630b0a590b86aa568",
                    "source_bytes": 147989,
                    "document_number": "05-9624",
                },
            ],
        },
    },
    {
        "application_number": "NDA206843",
        "submission_status": "AP",
        "submission_status_date": "20150724",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2015/206843Orig1s000ltr.pdf",
        "letter_sha256": "5b373565d7c84d6f1ae75004963b4b497b5e142237f5032a1473725d939e6601",
        "letter_bytes": 137385,
        "letter_pages": [1, 8],
        "product_strengths": {"001": "EQ 30MG BASE", "002": "EQ 60MG BASE"},
        "brand_name": "DAKLINZA",
        "dosage_form": "TABLET",
        "route": "ORAL",
        "ingredient": "DACLATASVIR DIHYDROCHLORIDE",
        "withdrawal": {
            "effective_date": "2021-12-01",
            "source_uri": "https://www.govinfo.gov/content/pkg/FR-2021-11-01/pdf/2021-23729.pdf",
            "source_sha256": "ee008a1db9c79d6866e42a55434c5b0f9cc2b355d2b56c1d2995c2cc5f27f9b0",
            "source_bytes": 210140,
            "document_number": "2021-23729",
            "continuity_between_actions_verified": False,
        },
    },
    {
        "application_number": "ANDA075037",
        "submission_status": "AP",
        "submission_status_date": "19981030",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/1998/75037ltr.pdf",
        "letter_sha256": "e49ff5624f200bcb47c88828ead787aff2f82d3a481eb50651fda37d8ac28e83",
        "letter_bytes": 4119,
        "letter_pages": [1, 2],
        "product_strengths": {"001": "20MG", "002": "10MG"},
        "brand_name": "ISOSORBIDE MONONITRATE",
        "dosage_form": "TABLET",
        "route": "ORAL",
        "ingredient": "ISOSORBIDE MONONITRATE",
    },
    {
        "application_number": "ANDA074723",
        "submission_status": "AP",
        "submission_status_date": "19990330",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/1999/74723ltr.pdf",
        "letter_sha256": "11db4b4d59b957d7c456bb58b855104a16c2e8582c349e9ad41059741b296c4e",
        "letter_bytes": 4341,
        "letter_pages": [1, 2],
        "product_strengths": {"001": "50MG"},
        "brand_name": "DICLOFENAC SODIUM",
        "dosage_form": "TABLET, DELAYED RELEASE",
        "route": "ORAL",
        "ingredient": "DICLOFENAC SODIUM",
        "withdrawal": {
            "effective_date": "2021-07-26",
            "source_uri": "https://www.govinfo.gov/content/pkg/FR-2021-06-25/pdf/2021-13593.pdf",
            "source_sha256": "49c1165d9fabfa22d0983aa7bfc6f80a02d23b409c94ad4a2e9de9e77bab52a6",
            "source_bytes": 203751,
            "document_number": "2021-13593",
            "continuity_between_actions_verified": False,
            "correction": {
                "document_number": "2021-21371",
                "source_uri": "https://www.govinfo.gov/content/pkg/FR-2021-10-01/pdf/2021-21371.pdf",
                "source_sha256": "c1873e56ca3289f4371e3a7ac74fec839d34a7f05afeedadacca95044b9d80ff",
                "source_bytes": 173522,
                "corrected_application": "ANDA065152",
            },
        },
    },
    {
        "application_number": "NDA021938",
        "submission_status": "AP",
        "submission_status_date": "20060126",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2006/021938s000ltr.pdf",
        "letter_sha256": "8fa4aede6ae571f1cc635560d31d7fa9b8c8d1c01dff0443b0c0c58e397606ed",
        "letter_bytes": 833942,
        "letter_pages": [1, 6],
        "product_strengths": {
            "001": "EQ 12.5MG BASE",
            "002": "EQ 25MG BASE",
            "003": "EQ 50MG BASE",
        },
        "brand_name": "SUTENT",
        "dosage_form": "CAPSULE",
        "route": "ORAL",
        "ingredient": "SUNITINIB MALATE",
    },
    {
        "application_number": "ANDA202956",
        "submission_status": "AP",
        "submission_status_date": "20150917",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2015/202956Orig1s000ltr.pdf",
        "letter_sha256": "12643d18ee8ae8f930a4c36b0970741231e8b00cb5d5497a399c416f3ccb3ee5",
        "letter_bytes": 60759,
        "letter_pages": [1, 3],
        "product_strengths": {"001": "2.5MG", "002": "5MG"},
        "brand_name": "ZOLMITRIPTAN",
        "dosage_form": "TABLET, ORALLY DISINTEGRATING",
        "route": "ORAL",
        "ingredient": "ZOLMITRIPTAN",
    },
    {
        "application_number": "ANDA216947",
        "submission_status": "AP",
        "submission_status_date": "20230713",
        "letter_url": "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2023/216947Orig1s000ltr.pdf",
        "letter_sha256": "fda78a7b7bd7ea37cd64be0a8c09da69cd3ee23d1ce672e6f2baee76178489ae",
        "letter_bytes": 616816,
        "letter_pages": [1, 3],
        "product_strengths": {"001": "5MG", "002": "15MG"},
        "brand_name": "ERTUGLIFLOZIN",
        "dosage_form": "TABLET",
        "route": "ORAL",
        "ingredient": "ERTUGLIFLOZIN",
    },
)


def reviewed_action_mappings(
    payload: bytes, reviews: tuple[dict[str, Any], ...] = REVIEWS
) -> list[dict[str, Any]]:
    """Bind reviewed letter claims to exactly matching pinned source records."""
    apps = json.loads(payload)["results"]
    result: list[dict[str, Any]] = []
    for review in reviews:
        matched_apps = [
            a
            for a in apps
            if a.get("application_number") == review["application_number"]
        ]
        if len(matched_apps) != 1:
            raise ValueError("reviewed application identity differs")
        app = matched_apps[0]
        submissions = [
            s
            for s in app.get("submissions", [])
            if s.get("submission_type") == "ORIG"
            and s.get("submission_number") == "1"
            and s.get("submission_status") == review["submission_status"]
            and s.get("submission_status_date")
            == review["submission_status_date"]
            and any(
                d.get("url", "").replace("http://", "https://", 1)
                == review["letter_url"]
                and d.get("type") == "Letter"
                for d in s.get("application_docs", [])
            )
        ]
        if len(submissions) != 1:
            raise ValueError("reviewed submission identity differs")
        for number, strength in review["product_strengths"].items():
            products = [
                p
                for p in app.get("products", [])
                if p.get("product_number") == number
            ]
            if len(products) != 1:
                raise ValueError("reviewed product identity differs")
            product = products[0]
            if (
                product.get("brand_name") != review["brand_name"]
                or product.get("dosage_form") != review["dosage_form"]
                or product.get("route") != review["route"]
                or product.get("active_ingredients")
                != [{"name": review["ingredient"], "strength": strength}]
            ):
                raise ValueError("reviewed product characteristics differ")
            result.append({
                "concept_id": f"us-drugsfda:{review['application_number']}:{number}",
                "application_number": review["application_number"],
                "submission_type": "ORIG",
                "submission_number": "1",
                "action_status": review["submission_status"],
                "action_date": review["submission_status_date"],
                "product_strength_native": strength,
                "letter_url": review["letter_url"],
                "letter_sha256": review["letter_sha256"],
                "letter_bytes": review["letter_bytes"],
                "letter_pages": review["letter_pages"],
                "withdrawal": review.get("withdrawal"),
                "continuing_status_established": False,
                "validity_interval": None,
            })
    return result
