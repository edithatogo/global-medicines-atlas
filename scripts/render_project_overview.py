"""Render accessible project diagrams from the existing acceptance ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, cast
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- gma-progress:start -->"
END = "<!-- gma-progress:end -->"


def text(x: int, y: int, value: str, size: int = 16) -> str:
    """Emit escaped, readable SVG text with a fixed system font."""
    return f'<text x="{x}" y="{y}" font-size="{size}">{escape(value)}</text>'


def box(x: int, y: int, width: int, height: int, color: str) -> str:
    """Emit a high-contrast panel or progress segment."""
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="10" fill="{color}"/>'
    )


def svg(title: str, description: str, height: int, body: str) -> str:
    """Wrap a standalone diagram with equivalent accessible text."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" '
        f'height="{height}" viewBox="0 0 1100 {height}" role="img" '
        'aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title>'
        f'<desc id="desc">{escape(description)}</desc>'
        "<style>text{font-family:system-ui,sans-serif;fill:#14283f}</style>"
        + box(0, 0, 1100, height, "#f5f8fc")
        + body
        + "</svg>\n"
    )


def medallion() -> str:
    """Show the actual four layers and three internal Bronze strata."""
    body = text(26, 40, "Global Medicines Atlas · evidence to products", 27)
    body += text(
        26,
        70,
        "Regulatory approval, funding, formulary and terminology remain independent.",
    )
    body += box(24, 104, 330, 365, "#f6e6d6")
    body += text(42, 137, "BRONZE · source evidence", 20)
    for y, label, first, second in (
        (
            157,
            "B0 · Source index",
            "Authorities, datasets and URLs",
            "Indexing does not mean acquisition",
        ),
        (
            253,
            "B1 · Acquisition metadata",
            "Digests, rights, dates and receipts",
            "Append-only provenance",
        ),
        (
            349,
            "B2 · Raw evidence",
            "Native bytes or a lawful reference",
            "Immutable; retain licence exclusions",
        ),
    ):
        body += box(38, y, 302, 86, "#fffaf4")
        body += text(50, y + 25, label, 17)
        body += text(50, y + 49, first, 14) + text(50, y + 70, second, 14)
    panels = (
        (
            382,
            "#e1e8f0",
            "SILVER · typed data",
            (
                "Source-faithful MBS / PBS",
                "Identifiers and schema eras",
                "Native unresolved values",
                "Selected MBS tables qualified",
                "PBS projection is public",
                "Broader semantics open",
            ),
        ),
        (
            618,
            "#f5e7b5",
            "GOLD · reviewed links",
            (
                "Temporal evidence graph",
                "Method and confidence",
                "Positive / negative controls",
                "Candidate links stay labelled",
                "No inferred equivalence",
                "Qualification is partial",
            ),
        ),
        (
            854,
            "#d9ecea",
            "PLATINUM · products",
            (
                "CLI · API · Atlas · exports",
                "Pinned revisions and provenance",
                "Validity and uncertainty",
                "Software candidate delivered",
                "Exact cohorts exercised",
                "Live service gates open",
            ),
        ),
    )
    for x, color, title, lines in panels:
        body += box(x, 104, 222, 365, color) + text(x + 12, 137, title, 17)
        for i, line in enumerate(lines):
            body += text(x + 12, 190 + i * 38, line, 13)
    for x in (357, 594, 830):
        body += text(x, 300, "→", 23)
    body += text(
        26,
        505,
        "GitHub: contracts, code, CI and evidence   ↔   Hugging Face: approved public archives and pinned objects",
        16,
    )
    body += text(
        26,
        539,
        "Parquet and catalogues are rebuildable projections; B1/B2 retain evidentiary truth.",
        15,
    )
    body += text(
        26,
        570,
        "Publication · semantics · admission · recovery · release each retain separate acceptance gates.",
        15,
    )
    return svg(
        "The GMA medallion architecture",
        "Four layers: Bronze contains B0 source index, B1 acquisition metadata and B2 immutable raw evidence. Silver preserves typed source values. Gold records reviewed links. Platinum supplies products. Qualification remains partial.",
        600,
        body,
    )


def replace_progress(document: str, body: str) -> str:
    """Replace exactly one bounded section, preserving all surrounding prose."""
    if document.count(START) != 1 or document.count(END) != 1:
        raise ValueError("progress section needs exactly one marker pair")
    start = document.index(START) + len(START)
    end = document.index(END)
    if end < start:
        raise ValueError("progress markers are reversed")
    return document[:start] + "\n" + body.strip() + "\n" + document[end:]


def progress_documents(snapshot: dict[str, Any]) -> dict[Path, str]:
    """Keep the same scope-qualified progress statement on all four surfaces."""
    # The snapshot is produced locally by outputs, never accepted from a service.
    tracks = cast("dict[str, int]", snapshot["tracks"])
    requirements = cast("dict[str, int]", snapshot["requirements"])
    closed, total = tracks["closed"], tracks["total"]
    verified, required = requirements["verified"], requirements["total"]
    measured = date.fromisoformat(str(snapshot["as_of"]))
    stamp = f"{measured.day} {measured.strftime('%B %Y')}"
    summary = (
        f"**{closed}/{total} delivery tracks closed ({closed / total:.0%}); "
        f"{verified}/{required} tracked Stable v1 requirements verified "
        f"({verified / required:.1%}).** Measured on {stamp}. "
        f"{total - closed} tracks and {required - verified} requirements remain open.\n\n"
        "These are separate, unweighted ledger counts, not worldwide source "
        "coverage, effort or release readiness. A single mandatory gate can block release."
    )
    sections = {
        "README.md": "![Roadmap ledger completion](docs/assets/roadmap.svg)\n\n"
        + summary
        + "\n\nSee the [track registry](conductor/tracks.md), "
        "[qualification contract](quality/qualifications/stable-v1-contract.json), "
        "[roadmap](conductor/roadmap.md) and [snapshot](docs/project-status.json).",
        "conductor/roadmap.md": f"## Measured progress — {stamp}\n\n"
        "![Roadmap ledger completion](../docs/assets/roadmap.svg)\n\n"
        + summary
        + "\n\n[Measurement and reproduction](../docs/project-overview.md) "
        "and the [bound snapshot](../docs/project-status.json) identify the inputs.",
        "docs/publication/huggingface-catalogue-card.md": f"## Roadmap snapshot — {stamp}\n\n"
        "![Roadmap ledger completion](https://huggingface.co/datasets/edithatogo/"
        "global-medicines-atlas-catalogue/resolve/main/assets/roadmap.svg)\n\n"
        + summary
        + "\n\n[Measurement and bound snapshot](https://github.com/edithatogo/"
        "global-medicines-atlas/blob/main/docs/project-overview.md). "
        "Federation, independent recovery and production service qualification retain their gates.",
        "docs/project-overview.md": "| Measure | Complete | Denominator | Proportion |\n"
        "|---|---:|---:|---:|\n"
        f"| Closed delivery tracks | {closed} | {total} | {closed / total:.0%} |\n"
        f"| Verified tracked Stable v1 requirements | {verified} | {required} | {verified / required:.1%} |",
    }
    return {
        ROOT / path: replace_progress(
            (ROOT / path).read_text(encoding="utf-8"), body
        )
        for path, body in sections.items()
    }


def outputs(as_of: date | None = None) -> dict[Path, str]:
    """Bind denominators to ledgers; never turn checklist counts into release approval."""
    as_of = as_of or date.fromisoformat(
        json.loads(
            (ROOT / "docs/project-status.json").read_text(encoding="utf-8")
        )["as_of"]
    )
    tracks = ROOT / "conductor/tracks.md"
    contract = ROOT / "quality/qualifications/stable-v1-contract.json"
    rows = re.findall(
        r"^- \[([x~ ])\] \*\*Track:",
        tracks.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    document = json.loads(contract.read_text(encoding="utf-8"))
    requirements = document["requirements"]
    states = Counter(row["state"] for row in requirements)
    if not rows or not requirements or set(states) - {"verified", "blocked"}:
        raise ValueError(
            "progress inputs need an explicit supported denominator"
        )
    counts = (
        ("Conductor delivery tracks closed", rows.count("x"), len(rows)),
        (
            "Tracked Stable v1 requirements verified",
            states["verified"],
            len(requirements),
        ),
    )
    body = text(26, 40, "Roadmap · measured progress, separate gates", 27)
    body += text(
        26,
        73,
        f"Snapshot {as_of.isoformat()} · unweighted counts from the existing Conductor and Stable v1 ledgers",
    )
    for y, (label, done, total) in zip((125, 265), counts, strict=True):
        body += text(26, y, label, 21)
        body += text(
            26,
            y + 32,
            f"{done} / {total} completed · {done / total:.1%} · {total - done} remaining",
            18,
        )
        body += box(26, y + 48, 1048, 28, "#d7e0ec")
        body += box(26, y + 48, round(1048 * done / total), 28, "#277c83")
    for x, title, status in (
        (26, "Software candidate", "Delivered"),
        (294, "Live federation", "Partial · gate open"),
        (562, "Independent recovery", "Authority gap"),
        (
            830,
            "Stable v1 release",
            str(document["qualification_state"]).capitalize(),
        ),
    ):
        body += box(x, 390, 244, 82, "#e7edf6")
        body += text(x + 12, 421, title, 17) + text(x + 12, 450, status, 16)
    body += text(
        26,
        510,
        "These proportions measure ledger completion, not source coverage, effort or release readiness.",
        16,
    )
    body += text(
        26,
        541,
        "A single unmet mandatory gate can block release regardless of the percentage.",
        16,
    )
    snapshot = {
        "as_of": as_of.isoformat(),
        "measurement": "unweighted_ledger_counts_not_release_readiness",
        "tracks": {"closed": counts[0][1], "total": counts[0][2]},
        "requirements": {"verified": counts[1][1], "total": counts[1][2]},
        "inputs": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (tracks, contract)
        },
        "stable_release_state": document["qualification_state"],
    }
    return {
        **progress_documents(snapshot),
        ROOT / "docs/assets/medallion.svg": medallion(),
        ROOT / "docs/assets/roadmap.svg": svg(
            "GMA roadmap progress",
            f"{counts[0][1]} of {counts[0][2]} tracks closed; {counts[1][1]} of {counts[1][2]} tracked requirements verified. Counts are unweighted. Live federation, independent recovery and Stable v1 remain gated.",
            570,
            body,
        ),
        ROOT / "docs/project-status.json": json.dumps(
            snapshot, indent=2, sort_keys=True
        )
        + "\n",
    }


def main() -> None:
    """Refresh diagrams or check the committed snapshot without changing files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    for path, content in outputs(args.as_of).items():
        if args.check:
            if path.read_text(encoding="utf-8") != content:
                raise ValueError(f"project overview is stale: {path.name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
