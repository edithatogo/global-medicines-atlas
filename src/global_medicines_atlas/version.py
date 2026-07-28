"""Runtime access to the dynamically generated package version."""

from importlib.metadata import PackageNotFoundError, version
from typing import Final

PACKAGE_NAME: Final = "global-medicines-atlas"


def package_version() -> str:
    """Return installed metadata version or a source-tree fallback."""

    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0+unknown"


__version__: Final = package_version()
