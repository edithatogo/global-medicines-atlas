"""Bind declared MBS schema profiles to existing federation v4 records.

The binding is a read-side compatibility object.  It does not qualify the
declared profile, admit bytes, grant rights, or change the v4 contract.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, cast

from pydantic import ConfigDict

from .federation import validate_federation_semantics
from .historical_comparison import Digest, ProfileName
from .mbs_schema_profile import MbsSchemaProfileDeclaration
from .models import FrozenModel

MAX_FEDERATION_DOCUMENT_BYTES = 1024 * 1024
FederationCohort = Literal["legacy", "current", "synthetic"]


class MbsFederationProfileBinding(FrozenModel):
    """Immutable declaration-to-v4 binding, never profile qualification."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.mbs-federation-profile"] = (
        "global-medicines-atlas.mbs-federation-profile"
    )
    schema_version: Literal[1] = 1
    status: Literal["declared"] = "declared"
    federation_version: Literal["4.0.0"] = "4.0.0"
    federation_document_sha256: Digest
    dataset: str
    revision: ProfileName
    path: str
    object_sha256: Digest
    comparison_cohort: FederationCohort
    source_revision: ProfileName
    comparison_schema_profile: ProfileName
    b1_sha256: Digest
    b2_sha256: Digest
    legacy_schema_era_meaning: Literal["source_release_revision"] = (
        "source_release_revision"
    )


def bind_mbs_profile_to_federation(
    declaration: MbsSchemaProfileDeclaration,
    federation_document: dict[str, Any],
) -> MbsFederationProfileBinding:
    """Bind an MBS declaration to one already schema-validated v4 document.

    The v4 ``schema_era`` remains the source release revision.  The separately
    declared comparison profile is retained only in this versioned sidecar.
    In particular, the native comparison cohort ``historical`` is rejected;
    callers must not silently map it to v4 ``legacy`` or ``current``.

    Args:
        declaration: Receipt-bound declaration read from an MBS Silver batch.
        federation_document: A v4 document already checked against its pinned
            JSON Schema with format validation.

    Returns:
        An immutable, content-bound compatibility declaration.

    Raises:
        ValueError: The declaration, document, or their identities disagree.
    """
    try:
        return _bind(declaration, federation_document)
    except KeyError, TypeError, ValueError, AttributeError, OverflowError:
        raise ValueError("invalid MBS federation profile binding") from None


def _bind(
    declaration: MbsSchemaProfileDeclaration,
    document: object,
) -> MbsFederationProfileBinding:
    declaration = MbsSchemaProfileDeclaration.model_validate(
        declaration.model_dump(warnings=False)
    )
    if type(document) is not dict:
        raise TypeError
    copied = cast("dict[str, Any]", document)
    encoded = json.dumps(
        copied,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    if not encoded or len(encoded) > MAX_FEDERATION_DOCUMENT_BYTES:
        raise ValueError
    source = copied["source"]
    location = copied["location"]
    identities = (
        (copied["version"], "4.0.0"),
        (source["source_id"], declaration.source_id),
        (source["layer"], "silver"),
        (source["bronze_stratum"], None),
        (source["representation"], "projection"),
        (source["schema_era"], declaration.source_revision),
    )
    if any(observed != expected for observed, expected in identities):
        raise ValueError
    cohort = source["comparison_cohort"]
    if cohort not in {"legacy", "current", "synthetic"}:
        raise ValueError
    if (cohort == "synthetic") != (copied["evidence_kind"] == "synthetic"):
        raise ValueError
    validate_federation_semantics(copied)
    return MbsFederationProfileBinding(
        federation_document_sha256=hashlib.sha256(encoded).hexdigest(),
        dataset=location["dataset"],
        revision=location["revision"],
        path=location["path"],
        object_sha256=location["sha256"],
        comparison_cohort=cohort,
        source_revision=declaration.source_revision,
        comparison_schema_profile=declaration.comparison_schema_profile,
        b1_sha256=declaration.b1_sha256,
        b2_sha256=declaration.b2_sha256,
    )
