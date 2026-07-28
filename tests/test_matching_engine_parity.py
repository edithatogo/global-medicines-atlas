from pathlib import Path


def test_unpromoted_engines_are_documented():
    decision = Path(
        "conductor/decisions/0003-matching-kernel-promotion.md"
    ).read_text(encoding="utf-8")
    assert "Python 3.14 is the authoritative" in decision
    assert "Mojo, Rust and" in decision
    assert "Tantivy are not promoted" in decision
    assert "representative production-scale corpus" in decision
