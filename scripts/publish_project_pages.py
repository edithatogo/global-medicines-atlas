"""Update only the reviewed catalogue card and diagrams from hosted main."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.data_layer_archive import (
    HuggingFaceAnonymousArtifactVerifier,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    PublicationDestination,
    PublicationTarget,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = "edithatogo/global-medicines-atlas-catalogue"
APPROVAL = ROOT / "docs/publication/project-pages-approval.json"
# Preserve the already-approved packet when the editable overview is refreshed.
FILES = {
    "README.md": "docs/publication/project-pages-approved-20261103/README.md",
    "assets/medallion.svg": "docs/publication/project-pages-approved-20261103/assets/medallion.svg",
    "assets/roadmap.svg": "docs/publication/project-pages-approved-20261103/assets/roadmap.svg",
}


def approved_files() -> tuple[str, tuple[ArtifactBinding, ...]]:
    """Bind an exact three-file metadata scope without accessing credentials."""
    document = json.loads(APPROVAL.read_bytes())
    if (
        document["dataset"] != DATASET
        or document["metadata_update_approved"] is not True
        or set(document["files"]) != set(FILES)
        or not re.fullmatch(r"[0-9a-f]{40}", document["parent_revision"])
    ):
        raise ValueError("project page approval scope differs")
    bindings: list[ArtifactBinding] = []
    for remote, local in FILES.items():
        path = ROOT / local
        if path.is_symlink() or not path.is_file():
            raise ValueError("project page input must be a regular file")
        content = path.read_bytes()
        binding = ArtifactBinding(
            relative_path=remote,
            sha256=hashlib.sha256(content).hexdigest(),
            size=len(content),
        )
        if document["files"][remote] != binding.model_dump(mode="json"):
            raise ValueError("project page bytes differ from reviewed approval")
        bindings.append(binding)
    return document["parent_revision"], tuple(bindings)


def inventory(api: Any, revision: str) -> dict[str, str]:
    """Read public Git object identities without downloading source payloads."""
    info = api.dataset_info(DATASET, revision=revision, files_metadata=True)
    if info.private or info.gated:
        raise ValueError("project page destination is not anonymously public")
    result = {row.rfilename: row.blob_id for row in info.siblings}
    if not result or not all(result.values()):
        raise ValueError("public object inventory is incomplete")
    return result


def publish(exact_commit: str, receipt_path: Path, sdk: Any) -> None:
    """CAS-write exactly three metadata files once, then verify anonymously."""
    require_hosted_main(exact_commit)
    parent, bindings = approved_files()
    public = sdk.HfApi(token=False)
    if public.dataset_info(DATASET).sha != parent:
        raise ValueError("catalogue advanced; reconcile before publication")
    before = inventory(public, parent)
    receipt: dict[str, Any] = {
        "state": "intent",
        "dataset": DATASET,
        "parent_revision": parent,
        "code_commit": exact_commit,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "files": [item.model_dump(mode="json") for item in bindings],
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    result = sdk.HfApi(token=os.environ["HF_TOKEN"]).create_commit(
        repo_id=DATASET,
        repo_type="dataset",
        parent_commit=parent,
        commit_message="Refresh project architecture, roadmap and navigation",
        operations=[
            sdk.CommitOperationAdd(
                path_in_repo=remote, path_or_fileobj=str(ROOT / local)
            )
            for remote, local in FILES.items()
        ],
    )
    revision = str(result.oid)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Hub returned an invalid project page revision")
    receipt.update(state="uploaded", revision=revision)
    receipt_path.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    after = inventory(public, revision)
    if set(after) != set(before) | set(FILES) or any(
        after[path] != blob
        for path, blob in before.items()
        if path not in FILES
    ):
        raise ValueError("catalogue objects outside the page scope changed")
    verifier = HuggingFaceAnonymousArtifactVerifier()
    target = PublicationTarget(
        destination=PublicationDestination.HUGGING_FACE,
        repository=DATASET,
        revision="main",
        public_base_url=f"https://huggingface.co/datasets/{DATASET}",
    )
    for binding in bindings:
        verified = verifier.verify_artifact(
            target=target, revision=revision, artifact=binding
        )
        if verified.sha256 != binding.sha256 or verified.size != binding.size:
            raise ValueError("anonymous page verification differs")
    receipt.update(
        state="anonymously_verified",
        unchanged_other_git_objects=len(set(before) - set(FILES)),
        source_payloads_downloaded=False,
    )
    receipt_path.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Check the local scope, or explicitly publish from exact hosted main."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--exact-commit", default="")
    parser.add_argument(
        "--receipt", type=Path, default=Path("build/project-pages.json")
    )
    args = parser.parse_args()
    if args.publish:
        require_hosted_main(args.exact_commit)
        publish(
            args.exact_commit,
            args.receipt,
            cast("Any", import_module("huggingface_hub")),
        )
    else:
        parent, bindings = approved_files()
        print(
            json.dumps({
                "parent_revision": parent,
                "files": [b.model_dump(mode="json") for b in bindings],
            })
        )


if __name__ == "__main__":
    main()
