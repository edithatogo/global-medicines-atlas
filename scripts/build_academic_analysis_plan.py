"""Render the governed Phase 2 analysis plan without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "research/protocol/academic-analysis-plan-v1.json"
DEFAULT_OUTPUT = ROOT / "docs/research/academic-analysis-plan.md"


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def build_analysis_plan_markdown(plan: dict[str, Any]) -> str:
    """Return a deterministic Markdown projection of the Phase 2 contract."""
    matching = plan["matching_validation"]
    evidence = plan["evidence_handling"]
    analysis = plan["analysis"]
    reproducibility = plan["reproducibility"]
    controls = [
        f"{item['control_id']} ({item['dimension']}): {item['construction']} "
        f"-> `{item['expected_validity']}`"
        for item in matching["negative_controls"]
    ]
    denominators = [
        f"{item['denominator_id']}: {item['definition']}"
        for item in evidence["coverage_denominators"]
    ]
    descriptive = [
        f"{item['analysis_id']} [{item['outcome']}]: {item['summary']}"
        for item in analysis["descriptive"]
    ]
    sensitivity = [
        f"{item['analysis_id']}: {item['variation']} — {item['interpretation']}"
        for item in analysis["sensitivity"]
    ]
    identities = [
        f"{name}: {item['identity']} (verify: {item['verification']})"
        for name, item in reproducibility.items()
    ]
    return f"""# Global Medicines Atlas analysis and validation plan

> Generated offline from `research/protocol/academic-analysis-plan-v1.json`.
> Status: `{plan["status"]}`. This is a prospective methods contract, not a
> report of completed analyses or an external registration.

## Outcome boundary

Regulatory and funding outcomes remain separate. Joint outcome inference is
not planned. Every comparison is qualified using M-090 validity semantics.

## Matching and adjudication

- Candidate generation: {matching["candidate_generation"]}
- Automatic acceptance: `{matching["automatic_acceptance"]}`
- Unresolved evidence: `{matching["unresolved_state"]}`
- Material mismatch: `{matching["material_mismatch_state"]}`
- Adjudication: {matching["adjudication"]["independent_reviewers"]} independent
  reviewers; consensus is required and unresolved disagreements are retained.
- Inter-rater summaries: {", ".join(matching["inter_rater"]["agreement_statistics"])}.
  Agreement is a reliability description, not proof of validity.

### Negative controls

{_bullets(controls)}

## Missingness, conflicts, coverage, and uncertainty

- Absence: `{evidence["missingness"]["absence_interpretation"]}`.
- Conflicts: `{evidence["conflicts"]["resolution"]}`; silent overwrite is forbidden.
- Unknown states are reported separately and uncertainty is not collapsed into
  a negative regulatory or funding status.

Coverage denominators:

{_bullets(denominators)}

## Planned analyses

### Descriptive

{_bullets(descriptive)}

### Sensitivity

{_bullets(sensitivity)}

### Multiplicity boundary

No confirmatory hypothesis tests or p-values are planned. Confidence intervals
describe uncertainty and are not used as significance tests. Unplanned
analyses must be labelled exploratory and entered in the deviation register.

## Immutable reproducibility identities

{_bullets(identities)}

Mutable references are not sufficient evidence for any identity. The random
seed controls only deterministic procedures and does not make uncertain source
evidence certain.

## Deviations

The append-only register is `{plan["deviations"]["register_path"]}`. Changes
after registration are amendments; undeclared outcome switching is prohibited.

## Traceability

- Requirements: {", ".join(plan["traceability"]["requirements"])}
- GitHub analysis issue: [{plan["traceability"]["github_issue"].rsplit("/", maxsplit=1)[-1]}]({plan["traceability"]["github_issue"]})
"""


def main() -> None:
    """Render the committed analysis-plan projection."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    plan = json.loads(arguments.input.read_text(encoding="utf-8"))
    rendered = build_analysis_plan_markdown(plan)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
