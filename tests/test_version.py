"""Dynamic-version contract tests."""

from packaging.version import Version

from global_medicines_atlas import __version__
from global_medicines_atlas.version import package_version


def test_runtime_version_is_pep440_and_single_sourced() -> None:
    assert Version(__version__)
    assert __version__ == package_version()
