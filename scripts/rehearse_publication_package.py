"""Run an offline clean-room publication rehearsal."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from global_medicines_atlas.clean_room_rehearsal import (  # ruff: ignore[module-import-not-at-top-of-file]
    RehearsalError,
    rehearse_publication,
)


def _deny_network(*_args: object, **_kwargs: object) -> NoReturn:
    raise RehearsalError(
        "network access is forbidden during clean-room rehearsal"
    )


def _audit_network(event: str, _arguments: tuple[object, ...]) -> None:
    if event.startswith(("socket.", "http.client.")):
        _deny_network()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--trust-policy", type=Path, required=True)
    parser.add_argument("--verifier", default="gh")
    parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    sys.addaudithook(_audit_network)
    receipt = rehearse_publication(
        source_root=args.source_root,
        declaration_path=args.declaration,
        trust_policy_path=args.trust_policy,
        receipt_path=args.receipt,
        verifier_command=(args.verifier,),
        python_network_denied=True,
    )
    print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
