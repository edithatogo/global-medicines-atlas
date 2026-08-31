"""Synthetic full-scan MBS cohort integration; no actual source acquisition."""

from hashlib import sha256

import pytest
from pydantic import ValidationError
from test_mbs_silver import (
    TABLES,
    _receipt,  # ruff: ignore[import-private-name] - shared synthetic fixture receipt
)

import global_medicines_atlas.mbs_historical_comparison as producer
from global_medicines_atlas.australian_source_contracts import (
    mbs_field_contracts,
)
from global_medicines_atlas.historical_comparison import (
    compare_native_snapshots,
)
from global_medicines_atlas.mbs_historical_comparison import (
    MbsComparisonCohort,
    MbsNativeKey,
    build_mbs_comparison_cohort,
)
from global_medicines_atlas.receipts import EvidenceClass


def xml(*rows):
    return ("<MBS_XML>" + "".join(rows) + "</MBS_XML>").encode()


def data(item="001", sub="<SubItemNum>00</SubItemNum>", extra=""):
    return f"<Data><ItemNum>{item}</ItemNum>{sub}{extra}</Data>"


def key(item="001", state="value", value="00"):
    return MbsNativeKey(
        item_num=item, sub_item_state=state, sub_item_value=value
    )


def build(payload, keys=None, **changes):
    return build_mbs_comparison_cohort(
        payload,
        _receipt(payload),
        selected_native_keys=(key(),) if keys is None else keys,
        table=changes.pop("table", "fees"),
        schema_era=changes.pop("schema_era", "synthetic-mbs-xml-v1"),
        expected_source_revision=changes.pop(
            "expected_source_revision", "synthetic-iso-v1"
        ),
        **changes,
    )


def test_scope_manifest_is_order_independent_and_identity_is_literal():
    payload = xml(data(), data("1"), data("001 "))
    selected = (key(), key("1"))
    first = build(payload, selected)
    second = build(payload, selected[::-1])
    assert first == second
    assert first.source_record_count == 3
    assert first.omitted_record_count == 1
    assert first.source_ordinals == (0, 1)
    assert first.snapshot.declared_rows == 2
    assert first.snapshot.complete is True
    assert first.snapshot.b1_sha256 == _receipt(payload).digest()
    assert first.snapshot.b2_sha256 == sha256(payload).hexdigest()
    assert first.snapshot.dimension == "service_benefit"
    assert first.snapshot.scope_id.startswith("mbs-native-keys-v1:")


def test_different_monthly_revisions_with_same_declared_schema_compare():
    # Both payloads are constructed fixtures; LIVE exercises metadata only.
    snapshots = []
    for revision, fee in (("2026-01", "1.00"), ("2026-02", "2.00")):
        payload = xml(data(extra=f"<ScheduleFee>{fee}</ScheduleFee>"))
        receipt = _receipt(payload)
        receipt = receipt.model_copy(
            update={
                "source": receipt.source.model_copy(
                    update={"catalog_version": revision}
                ),
                "evidence_class": EvidenceClass.LIVE,
            }
        )
        snapshots.append(
            build_mbs_comparison_cohort(
                payload,
                receipt,
                table="fees",
                selected_native_keys=(key(),),
                schema_era="mbs-xml-fields-v1",
                expected_source_revision=revision,
                cohort="historical",
            ).snapshot
        )
    result = compare_native_snapshots(*snapshots)
    assert result.outcome == "compared"
    assert result.left.source_revision == "2026-01"
    assert result.right.source_revision == "2026-02"
    assert (
        result.left.schema_era == result.right.schema_era == "mbs-xml-fields-v1"
    )
    assert result.left.b1_sha256 != result.right.b1_sha256
    assert result.left.b2_sha256 != result.right.b2_sha256
    assert any(event.kind == "field_changed" for event in result.differences)


def test_different_declared_schema_eras_abstain_without_revision_inference():
    payload = xml(data())
    left = build(payload, schema_era="mbs-xml-v1")
    right = build(payload, schema_era="mbs-xml-v2")
    result = compare_native_snapshots(left.snapshot, right.snapshot)
    assert result.outcome == "abstained"
    assert result.reasons == ("incompatible_profile",)
    assert result.left.source_revision == result.right.source_revision


@pytest.mark.parametrize("name", ["schema_era", "expected_source_revision"])
@pytest.mark.parametrize("value", ["", " ", " padded", "padded "])
def test_schema_era_and_revision_declarations_are_not_silently_normalized(
    name, value
):
    with pytest.raises(ValueError, match=r"schema era|source revision"):
        build(xml(data()), **{name: value})


def test_source_revision_mismatch_rejects_before_parsing(monkeypatch):
    def forbid_parse(*_args):
        pytest.fail("source parsed before revision mismatch rejected")

    monkeypatch.setattr(producer, "parse_mbs_source_xml", forbid_parse)
    with pytest.raises(ValueError, match="source revision"):
        build(xml(data()), expected_source_revision="wrong-revision")


def test_same_revision_label_does_not_replace_content_identity():
    left = build(xml(data(extra="<ScheduleFee>1.00</ScheduleFee>")))
    right = build(xml(data(extra="<ScheduleFee>2.00</ScheduleFee>")))
    result = compare_native_snapshots(left.snapshot, right.snapshot)
    assert result.outcome == "compared"
    assert result.left.source_revision == result.right.source_revision
    assert result.left.b1_sha256 != result.right.b1_sha256
    assert result.left.b2_sha256 != result.right.b2_sha256


def test_all_duplicate_occurrences_survive_then_comparison_abstains():
    payload = xml(data(), data("other"), data())
    cohort = build(payload)
    assert cohort.source_ordinals == (0, 2)
    assert len(cohort.snapshot.rows) == 2
    assert (
        cohort.snapshot.rows[0].occurrence_id
        != cohort.snapshot.rows[1].occurrence_id
    )
    result = compare_native_snapshots(cohort.snapshot, cohort.snapshot)
    assert result.reasons == ("ambiguous_identity",)


def test_different_selection_abstains_even_when_observed_rows_same():
    payload = xml(data())
    left = build(payload)
    right = build(payload, (key(), key("absent")))
    result = compare_native_snapshots(left.snapshot, right.snapshot)
    assert result.reasons == ("incompatible_profile",)


def test_source_larger_than_buffer_is_fully_counted_not_truncated():
    payload = xml(*(data(str(index)) for index in range(4100)))
    cohort = build(payload, (key("4099"),))
    assert cohort.source_record_count == 4100
    assert cohort.omitted_record_count == 4099
    assert cohort.source_ordinals == (4099,)


def test_missing_null_and_value_subitem_keys_do_not_alias():
    payload = xml(
        data(sub=""),
        data(sub="<SubItemNum/>"),
        data(sub="<SubItemNum> </SubItemNum>"),
    )
    keys = (
        key(state="missing", value=None),
        key(state="null", value=None),
        key(value=" "),
    )
    cohort = build(payload, keys)
    assert len({row.native_id for row in cohort.snapshot.rows}) == 3


@pytest.mark.parametrize("table", TABLES)
def test_table_fields_follow_existing_native_contracts(table):
    cohort = build(
        xml(data(extra="<ScheduleFee>01.00</ScheduleFee>")), table=table
    )
    fields = cohort.snapshot.rows[0].fields
    assert {field.name for field in fields} == {
        c.native_name for c in mbs_field_contracts() if c.target_table == table
    }
    assert all(
        field.state == "missing"
        for field in fields
        if field.name not in {"ItemNum", "SubItemNum", "ScheduleFee"}
    )


def test_rejects_receipt_source_and_revision_mismatch():
    payload = xml(data())
    with pytest.raises(ValueError, match="source revision"):
        build(payload, expected_source_revision="other-revision")
    with pytest.raises(ValueError, match="source bytes"):
        build_mbs_comparison_cohort(
            payload + b" ",
            _receipt(payload),
            table="fees",
            schema_era="synthetic-mbs-xml-v1",
            expected_source_revision="synthetic-iso-v1",
            selected_native_keys=(key(),),
        )
    receipt = _receipt(payload)
    receipt = receipt.model_copy(
        update={
            "source": receipt.source.model_copy(
                update={"source_id": "au-mbs-p7-legacy-workbook"}
            )
        }
    )
    with pytest.raises(ValueError, match="source_id"):
        build_mbs_comparison_cohort(
            payload,
            receipt,
            table="fees",
            schema_era="synthetic-mbs-xml-v1",
            expected_source_revision="synthetic-iso-v1",
            selected_native_keys=(key(),),
        )


def test_unselected_malformed_tail_is_not_ignored():
    with pytest.raises(ValueError, match="unknown native field"):
        build(xml(data(), data("unselected", extra="<Unknown/>")))


def test_selection_is_nonempty_unique_and_state_aware():
    with pytest.raises(ValidationError):
        key(state="missing", value="")
    with pytest.raises(ValueError, match="selection"):
        build(xml(data()), ())
    with pytest.raises(ValueError, match="selection"):
        build(xml(data()), (key(), key()))


@pytest.mark.parametrize("cohort", ["legacy", "historical", "current"])
def test_live_classification_requires_explicit_non_synthetic_cohort(cohort):
    # Constructed synthetic bytes exercise classification only, not LIVE evidence.
    payload = xml(data())
    receipt = _receipt(payload).model_copy(
        update={"evidence_class": EvidenceClass.LIVE}
    )
    result = build_mbs_comparison_cohort(
        payload,
        receipt,
        table="fees",
        schema_era="synthetic-mbs-xml-v1",
        expected_source_revision="synthetic-iso-v1",
        selected_native_keys=(key(),),
        cohort=cohort,
    )
    assert result.snapshot.cohort == cohort
    assert result.evidence_class == "live"
    with pytest.raises(ValueError, match="cohort"):
        build_mbs_comparison_cohort(
            payload,
            receipt,
            table="fees",
            schema_era="synthetic-mbs-xml-v1",
            expected_source_revision="synthetic-iso-v1",
            selected_native_keys=(key(),),
        )


@pytest.mark.parametrize("ordinal", [True, 0.0, "0", -1, 1])
def test_source_ordinals_are_strict(ordinal):
    result = build(xml(data()))
    payload = result.model_dump()
    payload["source_ordinals"] = [ordinal]
    with pytest.raises(ValidationError):
        MbsComparisonCohort.model_validate(payload)


def test_table_and_occurrence_lineage_cannot_be_substituted():
    result = build(xml(data(), data("ignored")))
    original = result.model_dump()
    bad = result.model_dump()
    bad["snapshot"]["rows"][0]["fields"] = []
    with pytest.raises(ValidationError, match="native fields"):
        MbsComparisonCohort.model_validate(bad)
    original["source_ordinals"] = [1]
    with pytest.raises(ValidationError, match="occurrence"):
        MbsComparisonCohort.model_validate(original)


def test_key_encoding_is_collision_free_for_native_delimiters():
    first = key("a:b", value="c")
    second = key("a", value="b:c")
    assert first.content_id() != second.content_id()
    cohort = build(
        xml(
            data("a:b", sub="<SubItemNum>c</SubItemNum>"),
            data("a", sub="<SubItemNum>b:c</SubItemNum>"),
        ),
        (first, second),
    )
    assert len(cohort.snapshot.rows) == 2


def test_selection_row_limit_is_checked_before_next_row(monkeypatch):
    monkeypatch.setattr(producer, "MAX_ROWS", 1)
    assert len(build(xml(data())).snapshot.rows) == 1
    with pytest.raises(ValueError, match="selected row/field"):
        build(xml(data(), data()))


def test_selection_field_limit_is_inclusive(monkeypatch):
    count = len(build(xml(data())).snapshot.rows[0].fields)
    monkeypatch.setattr(producer, "MAX_SNAPSHOT_FIELDS", count)
    assert len(build(xml(data())).snapshot.rows) == 1
    with pytest.raises(ValueError, match="selected row/field"):
        build(xml(data(), data()))


def test_selection_byte_limit_is_inclusive(monkeypatch):
    payload = xml(data(extra="<ScheduleFee>é</ScheduleFee>"))
    native = build(payload).snapshot.rows[0]
    size = len(native.native_id.encode()) + len(native.occurrence_id.encode())
    size += sum(
        len(field.name.encode()) + len((field.value or "").encode())
        for field in native.fields
    )
    monkeypatch.setattr(producer, "MAX_NATIVE_BYTES", size)
    assert len(build(payload).snapshot.rows) == 1
    monkeypatch.setattr(producer, "MAX_NATIVE_BYTES", size - 1)
    with pytest.raises(ValueError, match="native byte"):
        build(payload)


def test_absent_selected_keys_preserve_full_source_denominator():
    cohort = build(xml(data()), (key("absent"),))
    assert cohort.snapshot.rows == ()
    assert cohort.source_record_count == 1
    assert cohort.omitted_record_count == 1
    assert cohort.snapshot.complete is True


@pytest.mark.parametrize(
    "evidence_class",
    [EvidenceClass.DRY_RUN, EvidenceClass.UNAVAILABLE, EvidenceClass.FIXTURE],
)
def test_unsupported_classifications_are_rejected(evidence_class):
    payload = xml(data())
    receipt = _receipt(payload).model_copy(
        update={"evidence_class": evidence_class}
    )
    with pytest.raises(ValueError, match="successful"):
        build_mbs_comparison_cohort(
            payload,
            receipt,
            table="fees",
            selected_native_keys=(key(),),
            schema_era="synthetic-mbs-xml-v1",
            expected_source_revision="synthetic-iso-v1",
        )


def test_synthetic_receipt_cannot_claim_current_cohort():
    with pytest.raises(ValueError, match="synthetic evidence"):
        build(xml(data()), cohort="current")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scope_id", "whole_source"),
        ("source_id", "other"),
        ("dimension", "funding"),
        ("identity_profile", "other"),
        ("table", "other"),
        ("complete", False),
        ("declared_rows", 0),
        ("cohort", "historical"),
    ],
)
def test_cohort_snapshot_forgery_is_rejected(field, value):
    payload = build(xml(data())).model_dump()
    payload["snapshot"][field] = value
    with pytest.raises(ValidationError):
        MbsComparisonCohort.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("omitted_record_count", 1),
        ("source_ordinals", []),
    ],
)
def test_cohort_count_forgery_is_rejected(field, value):
    payload = build(xml(data())).model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        MbsComparisonCohort.model_validate(payload)


def test_keys_and_rows_cannot_escape_manifest():
    original = build(xml(data(), data("other")), (key(), key("other")))
    payload = original.model_dump()
    payload["selected_native_keys"] = payload["selected_native_keys"][::-1]
    with pytest.raises(ValidationError, match="selection identity"):
        MbsComparisonCohort.model_validate(payload)
    payload = original.model_dump()
    payload["snapshot"]["rows"][0]["native_id"] = "outside"
    with pytest.raises(ValidationError, match="outside"):
        MbsComparisonCohort.model_validate(payload)
    payload = original.model_dump()
    payload["source_ordinals"] = [1, 0]
    with pytest.raises(ValidationError, match="source order"):
        MbsComparisonCohort.model_validate(payload)


def test_constructed_mutable_cohort_inputs_are_normalized():
    original = build(xml(data()))
    mutable = original.snapshot.model_copy(
        update={"rows": list(original.snapshot.rows)}
    )
    payload = original.model_dump()
    payload["snapshot"] = mutable
    result = MbsComparisonCohort.model_validate(payload)
    mutable.rows.clear()
    assert len(result.snapshot.rows) == 1
    assert (
        MbsComparisonCohort.model_validate_json(result.model_dump_json())
        == result
    )


def test_no_receipt_uri_is_copied_to_candidate():
    result = build(xml(data()))
    assert "fixtures.invalid" not in result.model_dump_json()


def test_derivable_native_key_fields_and_occurrence_cannot_disagree():
    cohort = build(
        xml(data(extra="<ItemStartDate>uninterpreted</ItemStartDate>")),
        table="services",
    )
    payload = cohort.model_dump()
    fields = payload["snapshot"]["rows"][0]["fields"]
    for field in fields:
        if field["name"] == "ItemNum":
            field["value"] = "different"
    with pytest.raises(ValidationError, match="identity field"):
        MbsComparisonCohort.model_validate(payload)
    payload = cohort.model_dump()
    payload["snapshot"]["rows"][0]["occurrence_id"] = "wrong-prefix:0"
    with pytest.raises(ValidationError, match="occurrence"):
        MbsComparisonCohort.model_validate(payload)
