"""Append transactions must preserve every existing source object."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from global_medicines_atlas.federation_metadata_append import (
    ObjectDigest,
    prepare_metadata_append,
    verify_metadata_append,
)


def fixture():
    document = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "federation_source_metadata"
            / "valid-pbs.json"
        ).read_text()
    )
    baseline = tuple(
        ObjectDigest(path, 12, digest)
        for path, digest in [
            (
                document["provenance"]["receipt"],
                document["provenance"]["receipt_sha256"],
            ),
            *[
                (item["path"], item["sha256"])
                for item in document["provenance"]["payloads"]
            ],
            ("README.md", "e" * 64),
        ]
    )
    return document, baseline


def test_append_preserves_raw_and_existing_card():
    document, baseline = fixture()
    plan = prepare_metadata_append(document, baseline)
    assert plan.parent_revision == document["revision"]
    assert plan.addition.path.startswith("metadata/source/")
    assert plan.addition.sha256 == hashlib.sha256(plan.payload).hexdigest()
    verify_metadata_append(
        plan,
        dataset=plan.dataset,
        parent_revision=plan.parent_revision,
        revision="f" * 40,
        private=False,
        gated=False,
        observed=(*baseline, plan.addition),
        anonymous_payload=plan.payload,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "remove",
        "replace",
        "extra",
        "parent",
        "private",
        "gated",
        "payload",
        "dataset",
        "revision",
    ],
)
def test_rejects_failed_append_readback(mutation):
    document, baseline = fixture()
    plan = prepare_metadata_append(document, baseline)
    args = {
        "dataset": plan.dataset,
        "parent_revision": plan.parent_revision,
        "revision": "f" * 40,
        "private": False,
        "gated": False,
        "observed": (*baseline, plan.addition),
        "anonymous_payload": plan.payload,
    }
    if mutation == "remove":
        args["observed"] = (plan.addition,)
    elif mutation == "replace":
        args["observed"] = (
            *baseline[:-1],
            ObjectDigest("README.md", 12, "a" * 64),
            plan.addition,
        )
    elif mutation == "extra":
        args["observed"] = (
            *args["observed"],
            ObjectDigest("extra", 1, "a" * 64),
        )
    elif mutation == "parent":
        args["parent_revision"] = "a" * 40
    elif mutation == "revision":
        args["revision"] = plan.parent_revision
    elif mutation in {"private", "gated"}:
        args[mutation] = True
    elif mutation == "dataset":
        args["dataset"] = "other/dataset"
    else:
        args["anonymous_payload"] = b"altered"
    with pytest.raises(ValueError, match=r"differs|differ|requires|public"):
        verify_metadata_append(plan, **args)


def test_missing_source_and_duplicate_baseline_rejected():
    document, baseline = fixture()
    for objects in (baseline[1:], (*baseline, baseline[0])):
        with pytest.raises(ValueError, match=r"baseline|duplicate"):
            prepare_metadata_append(document, objects)


@pytest.mark.parametrize(
    "path", ["../raw", "/raw", "a//b", "a/./b", "a%2fb", "a\\b", "a\nb", ""]
)
def test_unsafe_inventory_path_rejected(path):
    with pytest.raises(ValueError, match="unsafe object path"):
        ObjectDigest(path, 1, "a" * 64)


def test_metadata_cannot_replace_an_existing_object():
    document, baseline = fixture()
    plan = prepare_metadata_append(document, baseline)
    with pytest.raises(ValueError, match="already exists"):
        prepare_metadata_append(document, (*baseline, plan.addition))


@pytest.mark.parametrize(
    ("count", "digest"),
    [(-1, "a" * 64), (True, "a" * 64), (1, "A" * 64), (1, "bad")],
)
def test_rejects_invalid_object_identity(count, digest):
    with pytest.raises(ValueError, match=r"byte count|SHA-256"):
        ObjectDigest("raw/file", count, digest)


def test_rejects_forged_plan():
    document, baseline = fixture()
    plan = prepare_metadata_append(document, baseline)
    forged = replace(plan, dataset="other/source")
    with pytest.raises(ValueError, match="transaction differs"):
        verify_metadata_append(
            forged,
            dataset=forged.dataset,
            parent_revision=plan.parent_revision,
            revision="f" * 40,
            private=False,
            gated=False,
            observed=(*baseline, plan.addition),
            anonymous_payload=plan.payload,
        )


@pytest.mark.parametrize("baseline", [(), (None,), tuple([None] * 10001)])
def test_rejects_unbounded_or_untyped_inventory(baseline):
    document, _ = fixture()
    with pytest.raises(ValueError, match="inventory"):
        prepare_metadata_append(document, baseline)


def test_preparation_reserves_inventory_slot_for_addition():
    document, baseline = fixture()
    at_capacity = (
        *baseline,
        *(
            ObjectDigest(f"extra/{i}", 0, "a" * 64)
            for i in range(10000 - len(baseline))
        ),
    )
    with pytest.raises(ValueError, match="no capacity"):
        prepare_metadata_append(document, at_capacity)
    plan = prepare_metadata_append(document, at_capacity[:-1])
    verify_metadata_append(
        plan,
        dataset=plan.dataset,
        parent_revision=plan.parent_revision,
        revision="f" * 40,
        private=False,
        gated=False,
        observed=(*plan.baseline, plan.addition),
        anonymous_payload=plan.payload,
    )
