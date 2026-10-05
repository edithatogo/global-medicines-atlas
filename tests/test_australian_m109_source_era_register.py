from pathlib import Path


def test_m109_register_covers_known_source_era_families() -> None:
    document = Path(
        "docs/qualification/australian-m109-source-era-register.md"
    ).read_text(encoding="utf-8")

    for era in (
        "MBS July 2025 XML v3",
        "MBS July 2024 Group P7 workbook",
        "PBS 2026-04-01 XML V3 archive member",
        "PBS G2B XML 1.8",
        "Alternate PBS XML 2.12",
        "PBS XML 3.x historical releases",
        "Current PBS public API / API CSV",
        "Minimal PBS fixture",
    ):
        assert era in document
    assert "PBS XML 2.8\u20132.12" in document


def test_m109_register_preserves_partial_and_rights_boundaries() -> None:
    document = Path(
        "docs/qualification/australian-m109-source-era-register.md"
    ).read_text(encoding="utf-8")

    assert "M-109 remains blocked" in document
    assert "Fixtures are not real-source evidence" in document
    assert "1,276 values are calendar-valid under both DMY and MDY" in document
    assert "no payload requested or acquired" in document
    assert (
        "project retention and external redistribution authority remain unresolved"
        in document
    )
