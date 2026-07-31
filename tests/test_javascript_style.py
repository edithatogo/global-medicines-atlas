"""Executable contracts for the binding JavaScript style guide."""

from pathlib import Path

import pytest
from scripts.validate_javascript_style import (
    style_problems,
    validate_javascript_style,
)


def test_repository_javascript_satisfies_binding_style() -> None:
    """Every shipped JavaScript source passes the lightweight style gate."""
    files = validate_javascript_style()

    assert files
    assert all(path.suffix == ".js" for path in files)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('const value = "wrong";\n', "single-quoted strings"),
        ("if (ready) return;\n", "requires braces"),
        ("const value = 1;\t\n", "tab character"),
        (f"const value = '{'x' * 70}';\n", "exceeds 80 columns"),
        ("var value = 1;\n", "var declarations"),
        ("eval('value');\n", "dynamic code execution"),
    ],
)
def test_style_gate_fails_closed(
    tmp_path: Path, source: str, message: str
) -> None:
    """Known violations cannot silently pass the style contract."""
    script = tmp_path / "invalid.js"
    script.write_text(source, encoding="utf-8")

    assert any(message in problem for problem in style_problems(script))


def test_style_gate_rejects_an_empty_scope(tmp_path: Path) -> None:
    """A misconfigured path cannot produce a vacuous green result."""
    with pytest.raises(ValueError, match="no JavaScript files"):
        validate_javascript_style(tmp_path)
