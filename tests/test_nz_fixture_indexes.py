from __future__ import annotations

import locale
import os
import time
from pathlib import Path

import pytest
from scripts.generate_nz_fixture_indexes import (
    build_indexes,
    build_medication_index,
    main,
    verify_indexes,
    write_indexes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "nzmedicines"
WARFARIN_ROOT = VENDOR_ROOT / "medications" / "10194111000116109-warfarin"


@pytest.mark.integration
def test_generated_indexes_exactly_reproduce_immutable_vendor_snapshot() -> (
    None
):
    outputs = build_indexes(VENDOR_ROOT)

    assert set(outputs) == {
        Path("document-references/index.txt"),
        Path("substance/substance.txt"),
        Path("medications/10194111000116109-warfarin/_index.json"),
    }
    assert verify_indexes(VENDOR_ROOT) == ()
    assert all(
        payload == (VENDOR_ROOT / relative).read_bytes()
        for relative, payload in outputs.items()
    )


@pytest.mark.unit
def test_reversed_input_order_is_byte_invariant() -> None:
    inputs = tuple(
        path
        for path in WARFARIN_ROOT.glob("*.json")
        if not path.name.startswith("_")
    )

    assert build_medication_index(inputs) == build_medication_index(
        reversed(inputs)
    )


@pytest.mark.edge
def test_duplicate_resource_id_is_rejected(tmp_path: Path) -> None:
    source = WARFARIN_ROOT / "generic.json"
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(source.read_bytes())

    with pytest.raises(ValueError, match="duplicate Medication resource id"):
        build_medication_index((source, duplicate))


@pytest.mark.edge
@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{", "malformed JSON"),
        (b"[]", "must be a JSON object"),
        (
            b'{"resourceType":"Bundle","type":"batch","entry":[]}',
            "collection Bundle",
        ),
        (
            b'{"resourceType":"Bundle","type":"collection","entry":[]}',
            "at least one Medication",
        ),
    ],
)
def test_malformed_inputs_are_rejected(
    tmp_path: Path, payload: bytes, message: str
) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_bytes(payload)

    with pytest.raises(ValueError, match=message):
        build_medication_index((malformed,))


@pytest.mark.property
def test_locale_and_timezone_do_not_affect_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tuple(
        path
        for path in WARFARIN_ROOT.glob("*.json")
        if not path.name.startswith("_")
    )
    baseline = build_medication_index(inputs)
    original_locale = locale.setlocale(locale.LC_ALL)
    original_timezone = os.environ.get("TZ")
    try:
        for timezone in ("UTC", "Pacific/Auckland", "America/New_York"):
            monkeypatch.setenv("TZ", timezone)
            if hasattr(time, "tzset"):
                time.tzset()
            locale.setlocale(locale.LC_ALL, "C")
            assert build_medication_index(inputs) == baseline
    finally:
        locale.setlocale(locale.LC_ALL, original_locale)
        if original_timezone is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_timezone)
        if hasattr(time, "tzset"):
            time.tzset()


@pytest.mark.integration
def test_generation_writes_only_to_separate_output_tree(tmp_path: Path) -> None:
    before = {
        path: path.read_bytes()
        for path in VENDOR_ROOT.rglob("*")
        if path.is_file()
    }
    output_root = tmp_path / "generated"

    written = write_indexes(VENDOR_ROOT, output_root)

    assert written
    assert all(output_root in path.parents for path in written)
    assert before == {
        path: path.read_bytes()
        for path in VENDOR_ROOT.rglob("*")
        if path.is_file()
    }
    with pytest.raises(ValueError, match="outside the immutable vendor"):
        write_indexes(VENDOR_ROOT, VENDOR_ROOT / "generated")


@pytest.mark.edge
def test_generation_rejects_nested_directory_symlink(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "generated"
    output_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    nested_link = output_root / "document-references"
    try:
        nested_link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks are unavailable: {error}")

    with pytest.raises(ValueError, match="contains a symlink"):
        write_indexes(VENDOR_ROOT, output_root)

    assert not (outside / "index.txt").exists()


@pytest.mark.edge
def test_generation_rejects_nested_file_symlink(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "generated"
    substance = output_root / "substance"
    substance.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("preserve", encoding="utf-8")
    nested_link = substance / "substance.txt"
    try:
        nested_link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")

    with pytest.raises(ValueError, match="contains a symlink"):
        write_indexes(VENDOR_ROOT, output_root)

    assert outside.read_text(encoding="utf-8") == "preserve"


@pytest.mark.smoke
def test_check_mode_is_read_only_and_reports_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--vendor-root", str(VENDOR_ROOT), "--check"]) == 0
    assert "verified 3 indexes" in capsys.readouterr().out


@pytest.mark.edge
def test_check_mode_reports_drift_without_writing(tmp_path: Path) -> None:
    fixture = tmp_path / "nzmedicines"
    fixture.mkdir()
    for relative, payload in build_indexes(VENDOR_ROOT).items():
        target = fixture / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    drifted = fixture / "substance" / "substance.txt"
    drifted.write_text("changed", encoding="utf-8")

    assert main(["--vendor-root", str(fixture), "--check"]) == 1
    assert drifted.read_text(encoding="utf-8") == "changed"
