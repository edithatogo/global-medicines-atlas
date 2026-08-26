"""Representative pytest workload used by the Scalene test profiler."""

from __future__ import annotations

import pytest


def main() -> int:
    """Run bounded pure-Python contract tests under Scalene."""
    return pytest.main([
        "tests/test_matching_policy.py",
        "tests/test_publication_contracts.py",
        "tests/test_source_receipts.py",
        "tests/test_test_goblin_harness.py",
        "-q",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
