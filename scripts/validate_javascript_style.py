"""Enforce the repository's lightweight binding JavaScript style contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVASCRIPT_ROOT = ROOT / "src" / "global_medicines_atlas" / "static"
MAX_LINE_LENGTH = 80
CONTROL_WITHOUT_BRACE = re.compile(r"^\s*(?:if|for|while)\s*\([^)]*\)\s+[^\s{]")
DOUBLE_QUOTED_STRING = re.compile(r'(?<![\\\w])"(?:[^"\\]|\\.)*"')


def style_problems(path: Path) -> tuple[str, ...]:
    """Return deterministic style findings for one JavaScript source file."""
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        code = line.split("//", maxsplit=1)[0]
        if "\t" in line:
            problems.append(f"{path}:{line_number}: tab character")
        if line.rstrip() != line:
            problems.append(f"{path}:{line_number}: trailing whitespace")
        if len(line) > MAX_LINE_LENGTH:
            problems.append(f"{path}:{line_number}: exceeds 80 columns")
        if CONTROL_WITHOUT_BRACE.search(code):
            problems.append(
                f"{path}:{line_number}: control block requires braces"
            )
        if DOUBLE_QUOTED_STRING.search(code):
            problems.append(f"{path}:{line_number}: use single-quoted strings")
    if re.search(r"\bvar\s+", text):
        problems.append(f"{path}: var declarations are forbidden")
    if re.search(r"\b(?:eval|Function)\s*\(", text):
        problems.append(f"{path}: dynamic code execution is forbidden")
    return tuple(problems)


def validate_javascript_style(root: Path = JAVASCRIPT_ROOT) -> tuple[Path, ...]:
    """Validate every governed JavaScript file or fail with all findings."""
    files = tuple(sorted(root.rglob("*.js")))
    if not files:
        raise ValueError(f"no JavaScript files found below {root}")
    problems = [problem for path in files for problem in style_problems(path)]
    if problems:
        raise ValueError(
            "JavaScript style validation failed:\n" + "\n".join(problems)
        )
    return files


def main() -> int:
    """Run the JavaScript style gate."""
    validate_javascript_style()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
