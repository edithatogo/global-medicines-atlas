"""Render the governed Phase 1 academic protocol without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "research/protocol/academic-protocol-v1.json"
DEFAULT_OUTPUT = ROOT / "docs/research/academic-protocol.md"


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def build_protocol_markdown(protocol: dict[str, Any]) -> str:
    """Return a deterministic Markdown projection of the protocol contract."""
    estimands = "\n\n".join(
        "\n".join((
            f"### {item['estimand_id']}: {item['outcome']}",
            "",
            f"- Target: {item['target']}",
            f"- Unit: {item['unit']}",
            f"- Summary measure: {item['summary_measure']}",
            f"- Interpretation: {item['interpretation']}",
        ))
        for item in protocol["estimands"]
    )
    selection = protocol["source_selection"]
    census = selection["census"]
    semantics = protocol["comparison_semantics"]
    dimensions = "\n".join(
        f"- {name.title()}: {semantics[name]['definition']}"
        for name in (
            "entity",
            "indication",
            "population",
            "temporal",
            "mapping",
        )
    )
    trace = protocol["traceability"]
    return f"""# Global Medicines Atlas academic protocol

> Generated offline from `research/protocol/academic-protocol-v1.json`.
> Status: `{protocol["status"]}`. This Phase 1 protocol is not an OSF
> registration and does not report study results.

## Title

{protocol["title"]}

## Objectives

{_bullets(protocol["objectives"])}

## Intended users and non-clinical scope

{_bullets(protocol["users"])}

Permitted uses:

{_bullets(protocol["scope"]["permitted_uses"])}

Prohibited claims:

{_bullets(protocol["scope"]["prohibited_claims"])}

The protocol does not provide clinical decision support, support individual
patient inference, or claim exhaustive global coverage.

## Estimands

{estimands}

Regulatory and funding outcomes are separate estimands. Absence or uncovered
data is not interpreted as unapproved or unfunded.

## Jurisdiction and source census

The governed denominator is catalog schema v{census["catalog_schema_version"]}
at `{census["authority"]}`: {len(census["jurisdictions"])} jurisdictions and
{len(census["source_ids"])} source surfaces. {census["denominator_rule"]}

### Jurisdiction inclusion

{_bullets([item["rule"] for item in selection["jurisdiction_inclusion"]])}

### Source inclusion

{_bullets([item["rule"] for item in selection["source_inclusion"]])}

### Source exclusion

{_bullets([item["rule"] for item in selection["source_exclusion"]])}

### Rights boundary

Restricted and rights-unknown payloads are excluded from public packages.
Metadata and retrieval code may be retained; payload redistribution requires
source-specific permission. This protocol does not grant source-data rights.

## Comparison semantics

{dimensions}

Permitted M-090 validity states are: {", ".join(semantics["validity_states"])}.
{semantics["material_mismatch_rule"]}

Validity qualifies only the stated status comparison. It never establishes
clinical equivalence, substitutability, therapeutic interchangeability, or
equal benefit.

## Traceability

- Requirements: {", ".join(trace["requirements"])}
- Design sections: {", ".join(trace["design_sections"])}
- GitHub methods issue: [{trace["github_issue"].rsplit("/", maxsplit=1)[-1]}]({trace["github_issue"]})
- Governed repository paths:
{_bullets([f"`{path}`" for path in trace["repository_paths"]])}
"""


def main() -> None:
    """Render the committed protocol projection."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    protocol = json.loads(arguments.input.read_text(encoding="utf-8"))
    rendered = build_protocol_markdown(protocol)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
