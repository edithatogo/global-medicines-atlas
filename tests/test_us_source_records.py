"""Source-native Bronze record projections for bounded U.S. payloads."""

from __future__ import annotations

import io
import json
import zipfile

import pyarrow as pa
import pytest

from global_medicines_atlas.archive_safety import ArchiveSafetyError
from global_medicines_atlas.us_source_records import us_source_record_batch


def _zip(members: dict[str, str | bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


@pytest.mark.parametrize(
    ("source_id", "identity"),
    [
        ("us-openfda-drugsfda", "NDA001"),
        ("us-openfda-enforcement", "R-001:E-001"),
        ("us-openfda-faers", "100:2"),
        ("us-openfda-ndc", "0001-0001"),
        ("us-openfda-nsde", "00001000101:0001-0001"),
    ],
)
def test_openfda_records_preserve_native_nested_fields(
    source_id: str,
    identity: str,
) -> None:
    native = {
        "application_number": "NDA001",
        "recall_number": "R-001",
        "event_id": "E-001",
        "safetyreportid": "100",
        "safetyreportversion": "2",
        "product_ndc": "0001-0001",
        "package_ndc": "0001-0001",
        "package_ndc11": "00001000101",
        "patient": {"reaction": [{"reactionmeddrapt": "Headache"}]},
        "openfda": {"brand_name": ["Source native name"]},
    }
    payload = json.dumps({"meta": {}, "results": [native]}).encode()

    batch = us_source_record_batch(source_id, payload, "json")

    assert batch is not None
    assert batch.record_id_column == "source_record_key"
    assert batch.table.num_rows == 1
    assert batch.table.column("source_record_key")[0].as_py() == identity
    assert batch.table.column("patient")[0].as_py() == native["patient"]
    assert batch.table.column("openfda")[0].as_py() == native["openfda"]
    assert pa.types.is_struct(batch.table.schema.field("patient").type)
    assert "gma_acquisition_id" not in batch.table.column_names


def test_openfda_duplicate_native_identity_gets_stable_record_link() -> None:
    record = {"product_ndc": "0001-0001", "brand_name": "Native"}
    payload = json.dumps({"results": [record, record]}).encode()

    batch = us_source_record_batch("us-openfda-ndc", payload, "json")

    assert batch is not None
    assert batch.table.column("source_record_key").to_pylist() == [
        "0001-0001:row:1",
        "0001-0001:row:2",
    ]


def test_openfda_malformed_results_fail_closed() -> None:
    with pytest.raises(TypeError, match="payload must be an object"):
        us_source_record_batch("us-openfda-faers", b"[]", "json")
    with pytest.raises(TypeError, match="results must be a list"):
        us_source_record_batch(
            "us-openfda-faers",
            b'{"results": {"unexpected": true}}',
            "json",
        )

    with pytest.raises(TypeError, match="result 1 must be an object"):
        us_source_record_batch(
            "us-openfda-faers", b'{"results": ["unexpected"]}', "json"
        )


def test_openfda_fallback_identity_and_technical_collision() -> None:
    batch = us_source_record_batch(
        "us-openfda-ndc",
        b'{"results": [{"brand_name": "Native"}]}',
        "json",
    )
    assert batch is not None
    assert (
        batch.table.column("source_record_key")[0].as_py().startswith("row:1:")
    )

    with pytest.raises(ValueError, match="technical record key"):
        us_source_record_batch(
            "us-openfda-ndc",
            b'{"results": [{"product_ndc": "1", "source_record_key": "x"}]}',
            "json",
        )


def test_drugsfda_archive_preserves_all_native_tables() -> None:
    members = {
        "ActionTypes_Lookup.txt": "ActionType\tDescription\nA\tApproval\n",
        "ApplicationDocs.txt": "ApplicationDocsID\tApplication_No\n1\t1\n",
        "Applications.txt": "ApplNo\tSponsorName\n1\tSponsor\n",
        "ApplicationsDocsType_Lookup.txt": "ApplicationDocsTypeID\tDescription\n1\tLabel\n",
        "Join_Submission_ActionTypes_Lookup.txt": "SubmissionID\tActionType\n1\tA\n",
        "MarketingStatus.txt": "ApplNo\tProductNo\n1\t1\n",
        "MarketingStatus_Lookup.txt": "MarketingStatusID\tDescription\n1\tPrescription\n",
        "Products.txt": "ApplNo\tProductNo\tDrugName\n1\t1\tNative\n",
        "SubmissionClass_Lookup.txt": "SubmissionClassCodeID\tDescription\n1\tClass\n",
        "SubmissionPropertyType.txt": "SubmissionPropertyTypeID\tDescription\n1\tType\n",
        "Submissions.txt": "ApplNo\tSubmissionID\n1\t1\n",
        "TE.txt": "ApplNo\tProductNo\tTECode\n1\t1\tAB\n",
    }

    batch = us_source_record_batch("us-drugsfda", _zip(members), "zip")

    assert batch is not None
    assert batch.table.num_rows == 12
    assert set(batch.table.column("source_member").to_pylist()) == set(members)
    assert "DrugName" in batch.table.column_names
    assert batch.table.column("source_record_key")[0].as_py().endswith(":1")


def test_orange_book_and_nsde_archives_preserve_native_columns() -> None:
    orange = us_source_record_batch(
        "us-fda-orange-book",
        _zip({
            "patent.txt": "Appl_No~Patent_No\n1~P1\n",
            "products.txt": "Appl_No~Product_No~Ingredient\n1~1~Native\n",
            "exclusivity.txt": "Appl_No~Exclusivity_Code\n1~NCE\n",
        }),
        "zip",
    )
    nsde = us_source_record_batch(
        "us-fda-nsde",
        _zip({
            "Comprehensive_NDC_SPL_Data_Elements_File.csv": (
                "PRODUCTNDC,NDCPACKAGECODE,PROPRIETARYNAME\n"
                "0001-0001,0001-0001-01,Native\n"
            )
        }),
        "zip",
    )

    assert orange is not None
    assert orange.table.num_rows == 3
    assert "Patent_No" in orange.table.column_names
    assert "Ingredient" in orange.table.column_names
    assert nsde is not None
    assert nsde.table.num_rows == 1
    assert nsde.table.column("NDCPACKAGECODE")[0].as_py() == "0001-0001-01"


def test_archive_schema_and_safety_fail_closed() -> None:
    with pytest.raises(ValueError, match="member set"):
        us_source_record_batch(
            "us-fda-orange-book",
            _zip({"products.txt": "Appl_No~Product_No\n1~1\n"}),
            "zip",
        )

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr("../products.txt", "unsafe")
    with pytest.raises(ArchiveSafetyError, match="unsafe member path"):
        us_source_record_batch("us-fda-orange-book", output.getvalue(), "zip")


def test_archive_preserves_unlabelled_overflow_without_guessing() -> None:
    batch = us_source_record_batch(
        "us-fda-orange-book",
        _zip({
            "patent.txt": (
                "Appl_No~Patent_No\n1~P1~unlabelled\n2~P2~also-unlabelled\n"
            ),
            "products.txt": "Appl_No~Product_No\n1~1\n",
            "exclusivity.txt": "Appl_No~Code\n1~NCE\n",
        }),
        "zip",
    )

    assert batch is not None
    assert batch.table.column("source_field_count").to_pylist() == [
        2,
        3,
        3,
        2,
    ]
    overflow = batch.table.column("source_unlabelled_field_1").to_pylist()
    assert overflow == [None, "unlabelled", "also-unlabelled", None]


@pytest.mark.parametrize(
    ("patent", "message"),
    [
        ("", "no header"),
        ("~Patent_No\n1~P1\n", "empty header"),
        ("Appl_No~Appl_No\n1~P1\n", "duplicate columns"),
        ("source_member~Patent_No\n1~P1\n", "technical columns"),
        (
            "source_unlabelled_field_1~Patent_No\n1~P1\n",
            "technical columns",
        ),
    ],
)
def test_archive_header_contract_fails_closed(
    patent: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        us_source_record_batch(
            "us-fda-orange-book",
            _zip({
                "patent.txt": patent,
                "products.txt": "Appl_No~Product_No\n1~1\n",
                "exclusivity.txt": "Appl_No~Code\n1~NCE\n",
            }),
            "zip",
        )


def test_archive_cp1252_short_row_and_blank_row_are_source_faithful() -> None:
    batch = us_source_record_batch(
        "us-fda-orange-book",
        _zip({
            "patent.txt": "Appl_No~Patent_No~Note\n1~P1\n",
            "products.txt": ("Appl_No~Product_No~Name\n\n1~1~caf\xe9\n").encode(
                "cp1252"
            ),
            "exclusivity.txt": "Appl_No~Code\n1~NCE\n",
        }),
        "zip",
    )

    assert batch is not None
    assert batch.table.num_rows == 3
    assert "caf\xe9" in batch.table.column("Name").to_pylist()
    assert batch.table.column("Note").to_pylist() == [None, None, None]


def test_non_record_and_media_mismatch_sources_do_not_project() -> None:
    assert us_source_record_batch("us-fda-rems", b"<html/>", "html") is None
    with pytest.raises(ValueError, match="requires json"):
        us_source_record_batch("us-openfda-faers", b"{}", "zip")
    with pytest.raises(ValueError, match="requires zip"):
        us_source_record_batch("us-fda-orange-book", b"{}", "json")
