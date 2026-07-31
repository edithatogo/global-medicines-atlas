"""Update the governed Mojo manifest, Pixi requirement, channel, and lock."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
from pathlib import Path
from typing import Any, cast

from contract_update import replace_files_atomically

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "quality" / "tool-versions.json"
PIXI_MANIFEST = ROOT / "pixi.toml"
PIXI_LOCK = ROOT / "pixi.lock"


def replace_exact(text: str, old: str, new: str) -> str:
    """Replace one governed literal, accepting a pre-updated Renovate value."""
    if old == new and text.count(new) == 1:
        return text
    if text.count(old) == 1 and text.count(new) == 0:
        return text.replace(old, new)
    if text.count(old) == 0 and text.count(new) == 1:
        return text
    if text.count(old) != 1:
        raise ValueError(f"expected exactly one governed literal: {old}")
    raise ValueError(f"ambiguous governed literals: {old}, {new}")


def update(version: str, channel: str) -> None:
    """Prepare and transactionally publish one coherent Mojo/Pixi update."""
    payload = cast(
        "dict[str, Any]", json.loads(MANIFEST.read_text(encoding="utf-8"))
    )
    versions = cast("dict[str, str]", payload["versions"])
    pixi_text = PIXI_MANIFEST.read_text(encoding="utf-8")
    pixi_text = replace_exact(
        pixi_text,
        f"https://conda.modular.com/{versions['mojo_channel']}",
        f"https://conda.modular.com/{channel}",
    )
    pixi_text = replace_exact(
        pixi_text,
        f'mojo = "=={versions["mojo"]}"',
        f'mojo = "=={version}"',
    )
    versions["mojo"] = version
    versions["mojo_channel"] = channel

    with tempfile.TemporaryDirectory(prefix="gma-mojo-contract-") as temporary:
        temporary_root = Path(temporary)
        temporary_manifest = temporary_root / "pixi.toml"
        temporary_manifest.write_text(pixi_text, encoding="utf-8")
        pixi = shutil.which("pixi")
        if pixi is None:
            raise RuntimeError("pixi executable is required")
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [
                pixi,
                "lock",
                "--manifest-path",
                str(temporary_manifest),
            ],
            check=True,
        )
        lock = (temporary_root / "pixi.lock").read_text(encoding="utf-8")

    if (
        f"/{channel}/" not in lock
        or f"/mojo-{version}-release.conda" not in lock
    ):
        raise ValueError("generated Pixi lock does not contain governed Mojo")
    replace_files_atomically({
        MANIFEST: (json.dumps(payload, indent=2) + "\n").encode(),
        PIXI_MANIFEST: pixi_text.encode(),
        PIXI_LOCK: lock.encode(),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--channel", default="max-nightly")
    arguments = parser.parse_args()
    update(arguments.version, arguments.channel)


if __name__ == "__main__":
    main()
