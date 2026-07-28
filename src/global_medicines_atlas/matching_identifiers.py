"""Deterministic identifier matching with explicit evidence."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from .models import FrozenModel, Identifier


class IdentifierEvidence(FrozenModel):
    system: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_identifier_type: str | None = None
    target_identifier_type: str | None = None


def identifier_key(identifier: Identifier) -> tuple[str, str]:
    return (
        identifier.system.strip().casefold().rstrip("/"),
        identifier.value.strip().casefold(),
    )


def shared_identifiers(
    source: Iterable[Identifier], target: Iterable[Identifier]
) -> tuple[IdentifierEvidence, ...]:
    target_index = {identifier_key(item): item for item in target}
    evidence: list[IdentifierEvidence] = []
    for item in source:
        key = identifier_key(item)
        matched = target_index.get(key)
        if matched is not None:
            evidence.append(
                IdentifierEvidence(
                    system=key[0],
                    value=key[1],
                    source_identifier_type=item.identifier_type,
                    target_identifier_type=matched.identifier_type,
                )
            )
    unique: dict[str, IdentifierEvidence] = {
        item.model_dump_json(): item for item in evidence
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.system,
                item.value,
                item.source_identifier_type or "",
                item.target_identifier_type or "",
            ),
        )
    )
