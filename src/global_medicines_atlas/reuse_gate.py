"""Pre-acquisition reuse gate for public medicine payloads.

Search local clones, maintainer GitHub repositories, Hugging Face, and the
source registry before any acquire/download. Explicitly choose one of
reuse | link | mirror | extend | fork | acquire-new so independent copies of
the same public data do not accumulate.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field

from .models import FrozenModel
from .source_catalog import MedicineDataSource, load_source_catalog

SEARCH_SURFACES: tuple[str, ...] = (
    "local_clones",
    "github",
    "hugging_face",
    "source_registry",
)
DISPOSITION_PRIORITY: tuple[str, ...] = (
    "reuse",
    "link",
    "mirror",
    "extend",
    "fork",
    "acquire-new",
)
HF_CATALOGUE_REPOSITORY = "edithatogo/global-medicines-atlas-catalogue"
HF_CATALOGUE_REVISION = "760723adc9c2f8e8946eebe9bcada7aff212095e"
ECOSYSTEM_RELATIVE = ".context/ecosystem.toml"
CATALOGUE_RELATIVE = (
    "src/global_medicines_atlas/data/medicine_source_catalog.json"
)
SurfaceName = Literal[
    "local_clones",
    "github",
    "hugging_face",
    "source_registry",
]


class ReuseDisposition(StrEnum):
    """Explicit choice after searching maintainer-owned copies."""

    REUSE = "reuse"
    LINK = "link"
    MIRROR = "mirror"
    EXTEND = "extend"
    FORK = "fork"
    ACQUIRE_NEW = "acquire-new"


class ReuseCandidateKind(StrEnum):
    """What a search hit actually found."""

    PAYLOAD = "payload"
    REGISTRY = "registry"
    SCHEMA = "schema"
    RELATED = "related"


class ReuseCandidate(FrozenModel):
    """One hit from a required search surface."""

    surface: SurfaceName
    locator: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    kind: ReuseCandidateKind
    digest: str | None = None


class ReuseGateDecision(FrozenModel):
    """Recorded reuse choice bound to an acquisition."""

    source_id: str = Field(min_length=1)
    disposition: ReuseDisposition
    searched_surfaces: tuple[str, ...]
    candidates: tuple[ReuseCandidate, ...]
    rationale: str = Field(min_length=1)
    catalogue_revision: str = HF_CATALOGUE_REVISION

    @property
    def payload_candidates(self) -> tuple[ReuseCandidate, ...]:
        """Hits that already hold source bytes."""

        return tuple(
            item
            for item in self.candidates
            if item.kind is ReuseCandidateKind.PAYLOAD
        )


class ReuseGateRequiredError(ValueError):
    """Raised when acquisition is attempted without the reuse gate."""


class AcquireNewNotLastResortError(ValueError):
    """Raised when acquire-new is chosen despite an existing payload."""


HuggingFaceIndex = Mapping[str, Sequence[str]]
GitHubIndex = Mapping[str, Sequence[str]]


def load_ecosystem_document(root: Path) -> dict[str, object]:
    """Load the maintainer-owned ecosystem registry."""

    path = root / ECOSYSTEM_RELATIVE
    with path.open("rb") as stream:
        document = tomllib.load(stream)
    if document.get("policy") != "reuse-before-build":
        raise ValueError("ecosystem registry must be reuse-before-build")
    return document


def _tables(
    document: Mapping[str, object],
    key: str,
) -> tuple[dict[str, object], ...]:
    value = document.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def search_local_clones(
    source_id: str,
    *,
    repository_root: Path,
    ecosystem: Mapping[str, object] | None = None,
) -> tuple[ReuseCandidate, ...]:
    """Search this clone, local boundaries, and sibling maintainer clones."""

    hits: list[ReuseCandidate] = []
    root = repository_root.resolve()
    needle = source_id.replace("_", "-")
    fixture_roots = (
        root / "tests" / "fixtures",
        root / "src" / "global_medicines_atlas" / "data",
    )
    for fixture_root in fixture_roots:
        if not fixture_root.is_dir():
            continue
        for path in fixture_root.rglob("*"):
            if not path.is_file():
                continue
            text = str(path.relative_to(root)).replace("_", "-").lower()
            name = path.name.replace("_", "-").lower()
            slug = needle.lower()
            suffix = "-".join(slug.split("-")[1:]) or slug
            if slug not in text and suffix not in name and slug not in name:
                continue
            hits.append(
                ReuseCandidate(
                    surface="local_clones",
                    locator=str(path),
                    source_id=source_id,
                    kind=ReuseCandidateKind.PAYLOAD,
                )
            )

    document = ecosystem or {}
    for resource in _tables(document, "github"):
        boundary = resource.get("local_boundary")
        if not isinstance(boundary, str) or not boundary:
            continue
        blob = " ".join(
            str(resource.get(key, ""))
            for key in ("id", "authority", "local_boundary")
        )
        if source_id not in blob and source_id.replace("-", " ") not in blob:
            continue
        path = root / boundary
        if path.exists():
            hits.append(
                ReuseCandidate(
                    surface="local_clones",
                    locator=str(path),
                    source_id=source_id,
                    kind=ReuseCandidateKind.RELATED,
                )
            )

    parent = root.parent
    for resource in _tables(document, "github"):
        repository = resource.get("repository")
        if not isinstance(repository, str) or "/" not in repository:
            continue
        name = repository.split("/", 1)[1]
        sibling = parent / name
        if sibling.is_dir() and sibling.resolve() != root:
            hits.append(
                ReuseCandidate(
                    surface="local_clones",
                    locator=str(sibling),
                    source_id=source_id,
                    kind=ReuseCandidateKind.RELATED,
                )
            )
    return tuple(hits)


def search_github_repos(
    source_id: str,
    *,
    ecosystem: Mapping[str, object],
    github_index: GitHubIndex | None = None,
) -> tuple[ReuseCandidate, ...]:
    """Search declared maintainer GitHub authorities, not a live scrape."""

    hits: list[ReuseCandidate] = []
    extra = github_index or {}
    needle = source_id.replace("-", " ")
    for resource in _tables(ecosystem, "github"):
        repository = str(resource.get("repository", ""))
        url = str(resource.get("url", repository))
        blob = " ".join(
            str(resource.get(key, ""))
            for key in ("id", "repository", "authority", "local_boundary")
        ).replace("-", " ")
        indexed = extra.get(repository, ())
        if source_id in indexed:
            kind = ReuseCandidateKind.PAYLOAD
        elif needle in blob:
            kind = ReuseCandidateKind.SCHEMA
        else:
            continue
        hits.append(
            ReuseCandidate(
                surface="github",
                locator=url,
                source_id=source_id,
                kind=kind,
            )
        )
    return tuple(hits)


def search_hugging_face(
    source_id: str,
    *,
    ecosystem: Mapping[str, object],
    huggingface_index: HuggingFaceIndex | None = None,
) -> tuple[ReuseCandidate, ...]:
    """Search declared HF datasets including the medicines catalogue."""

    hits: list[ReuseCandidate] = []
    extra = huggingface_index or {}
    found_catalogue = False
    for resource in _tables(ecosystem, "hugging_face"):
        repository = str(resource.get("repository", ""))
        url = str(resource.get("url", repository))
        paths = extra.get(repository, ())
        kind = ReuseCandidateKind.RELATED
        if any(source_id in path for path in paths):
            kind = ReuseCandidateKind.PAYLOAD
        elif repository != HF_CATALOGUE_REPOSITORY:
            continue
        if repository == HF_CATALOGUE_REPOSITORY:
            found_catalogue = True
            kind = (
                ReuseCandidateKind.PAYLOAD
                if kind is ReuseCandidateKind.PAYLOAD
                else ReuseCandidateKind.REGISTRY
            )
            url = (
                f"{url}/tree/{HF_CATALOGUE_REVISION}"
                if "huggingface.co" in url
                else url
            )
        hits.append(
            ReuseCandidate(
                surface="hugging_face",
                locator=url,
                source_id=source_id,
                kind=kind,
            )
        )
    if not found_catalogue:
        paths = extra.get(HF_CATALOGUE_REPOSITORY, ())
        kind = (
            ReuseCandidateKind.PAYLOAD
            if any(source_id in path for path in paths)
            else ReuseCandidateKind.REGISTRY
        )
        hits.append(
            ReuseCandidate(
                surface="hugging_face",
                locator=(
                    "https://huggingface.co/datasets/"
                    f"{HF_CATALOGUE_REPOSITORY}/tree/{HF_CATALOGUE_REVISION}"
                ),
                source_id=source_id,
                kind=kind,
            )
        )
    return tuple(hits)


def search_source_registry(
    source_id: str,
    *,
    catalog: Iterable[MedicineDataSource] | None = None,
) -> tuple[ReuseCandidate, ...]:
    """Search the governed medicine source catalog."""

    sources = load_source_catalog() if catalog is None else tuple(catalog)
    hits: list[ReuseCandidate] = []
    for source in sources:
        if source.source_id != source_id:
            continue
        locator = str(
            source.download_url or source.api_url or source.landing_page
        )
        hits.append(
            ReuseCandidate(
                surface="source_registry",
                locator=locator,
                source_id=source_id,
                kind=ReuseCandidateKind.REGISTRY,
            )
        )
    return tuple(hits)


def choose_disposition(
    candidates: Sequence[ReuseCandidate],
    *,
    requested: ReuseDisposition | None = None,
) -> ReuseDisposition:
    """Choose the strongest justified disposition; acquire-new is last."""

    payload_surfaces = {
        item.surface
        for item in candidates
        if item.kind is ReuseCandidateKind.PAYLOAD
    }
    if "local_clones" in payload_surfaces:
        chosen = ReuseDisposition.REUSE
    elif "hugging_face" in payload_surfaces:
        chosen = ReuseDisposition.LINK
    elif "github" in payload_surfaces:
        chosen = ReuseDisposition.MIRROR
    elif any(item.kind is ReuseCandidateKind.SCHEMA for item in candidates):
        chosen = ReuseDisposition.EXTEND
    elif any(item.kind is ReuseCandidateKind.RELATED for item in candidates):
        chosen = ReuseDisposition.FORK
    else:
        chosen = ReuseDisposition.ACQUIRE_NEW

    if requested is None:
        return chosen
    if (
        requested is ReuseDisposition.ACQUIRE_NEW
        and chosen is not ReuseDisposition.ACQUIRE_NEW
        and any(item.kind is ReuseCandidateKind.PAYLOAD for item in candidates)
    ):
        raise AcquireNewNotLastResortError(
            "acquire-new is last resort when a payload copy already exists"
        )
    return requested


def evaluate_reuse_gate(
    source_id: str,
    *,
    repository_root: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    huggingface_index: HuggingFaceIndex | None = None,
    github_index: GitHubIndex | None = None,
    requested: ReuseDisposition | None = None,
) -> ReuseGateDecision:
    """Search all required surfaces and record an explicit disposition."""

    if not source_id.strip():
        raise ValueError("source_id is required")
    ecosystem = load_ecosystem_document(repository_root)
    candidates = (
        *search_local_clones(
            source_id,
            repository_root=repository_root,
            ecosystem=ecosystem,
        ),
        *search_github_repos(
            source_id,
            ecosystem=ecosystem,
            github_index=github_index,
        ),
        *search_hugging_face(
            source_id,
            ecosystem=ecosystem,
            huggingface_index=huggingface_index,
        ),
        *search_source_registry(source_id, catalog=catalog),
    )
    searched = SEARCH_SURFACES
    disposition = choose_disposition(candidates, requested=requested)
    rationale = f"chose {disposition.value} after searching " + ", ".join(
        SEARCH_SURFACES
    )
    return ReuseGateDecision(
        source_id=source_id,
        disposition=disposition,
        searched_surfaces=searched,
        candidates=candidates,
        rationale=rationale,
        catalogue_revision=HF_CATALOGUE_REVISION,
    )


def require_reuse_decision(
    decision: ReuseGateDecision | None,
    source_id: str,
) -> ReuseGateDecision:
    """Fail closed when acquisition skipped the reuse gate."""

    if decision is None:
        raise ReuseGateRequiredError(
            f"reuse gate required before acquiring {source_id}"
        )
    if decision.source_id != source_id:
        raise ReuseGateRequiredError(
            "reuse gate source_id does not match acquisition"
        )
    missing = [
        surface
        for surface in SEARCH_SURFACES
        if surface not in decision.searched_surfaces
    ]
    if missing:
        raise ReuseGateRequiredError(
            "reuse gate must search " + ", ".join(SEARCH_SURFACES)
        )
    if (
        decision.disposition is ReuseDisposition.ACQUIRE_NEW
        and decision.payload_candidates
    ):
        raise AcquireNewNotLastResortError(
            "acquire-new is last resort when a payload copy already exists"
        )
    return decision


def acquire_new_decision(source_id: str) -> ReuseGateDecision:
    """Test and last-resort decision after all surfaces were searched."""

    return ReuseGateDecision(
        source_id=source_id,
        disposition=ReuseDisposition.ACQUIRE_NEW,
        searched_surfaces=SEARCH_SURFACES,
        candidates=(),
        rationale="no payload copy found; acquire-new is last resort",
        catalogue_revision=HF_CATALOGUE_REVISION,
    )


ReuseSearcher = Callable[[str], ReuseGateDecision]
