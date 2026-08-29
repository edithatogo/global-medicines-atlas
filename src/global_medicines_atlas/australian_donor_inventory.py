"""Deterministic inventory of the two pinned Australian donor repositories."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Git objects are the evidence boundary
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

Disposition = Literal[
    "adopt",
    "adapt",
    "replace-with-equivalent",
    "retain-legacy",
    "supersede",
    "exclude-with-reason",
    "unclassified",
]


class InventoryCompletenessError(ValueError):
    """Raised when an inventory no longer matches its pinned Git objects."""


class DonorRepository(BaseModel):
    """A local Git object database and the immutable donor revision to inspect."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    repository: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_dir: Path


class DonorFile(BaseModel):
    repository: str
    revision: str
    path: str
    mode: str
    git_object: str
    byte_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    language: str
    roles: tuple[str, ...]
    implementation_state: str
    disposition: Disposition
    disposition_reason: str


class DonorFunction(BaseModel):
    repository: str
    path: str
    qualified_name: str
    line: int = Field(ge=1)
    is_async: bool
    disposition: Disposition


class DonorWorkflow(BaseModel):
    repository: str
    path: str
    job: str
    disposition: Disposition


class RoadmapCapability(BaseModel):
    capability: str
    implementation_state: Literal["roadmap-only"] = "roadmap-only"
    successor_track: str
    disposition: Literal["retain-legacy"] = "retain-legacy"


class DonorSnapshot(BaseModel):
    repository: str
    revision: str
    reachable_commit_count: int = Field(ge=1)
    root_commits: tuple[str, ...]
    code_license: Literal["Apache-2.0"] = "Apache-2.0"
    license_path: str
    license_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AustralianDonorInventory(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    repositories: tuple[DonorSnapshot, ...]
    files: tuple[DonorFile, ...]
    functions: tuple[DonorFunction, ...]
    workflows: tuple[DonorWorkflow, ...]
    roadmap_capabilities: tuple[RoadmapCapability, ...]
    denominator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class InventoryValidationResult(BaseModel):
    file_count: int
    function_count: int
    workflow_count: int
    data_object_count: int
    denominator_sha256: str


_LANGUAGES = {
    ".csv": "CSV",
    ".html": "HTML",
    ".ipynb": "Jupyter Notebook",
    ".json": "JSON",
    ".md": "Markdown",
    ".py": "Python",
    ".toml": "TOML",
    ".xml": "XML",
    ".xlsx": "Excel workbook",
    ".yaml": "YAML",
    ".yml": "YAML",
}

_ROADMAP_CAPABILITIES = (
    (
        "Neo4j schema, loading, and Cypher service",
        "federated_medallion_frontier_experiments_20260829",
    ),
    (
        "SNOMED CT-AU RF2 acquisition and graph loading",
        "australian_benefits_silver_gold_20260829",
    ),
    (
        "complete AMT and ATC hierarchy acquisition",
        "australian_benefits_silver_gold_20260829",
    ),
    (
        "official AMT and SNOMED mapping ingestion",
        "australian_benefits_silver_gold_20260829",
    ),
    (
        "NLP and NER over MBS and PBS text",
        "federated_medallion_frontier_experiments_20260829",
    ),
    (
        "temporal MBS and PBS evidence graph",
        "australian_benefits_silver_gold_20260829",
    ),
    (
        "Spark distributed processing",
        "federated_medallion_frontier_experiments_20260829",
    ),
    (
        "Airflow orchestration",
        "federated_medallion_frontier_experiments_20260829",
    ),
    (
        "production application programming interface",
        "federated_medicines_platinum_20260829",
    ),
    ("production user interface", "federated_medicines_platinum_20260829"),
)


def _git_bytes(donor: DonorRepository, *arguments: str) -> bytes:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ["git", *arguments],  # ruff: ignore[start-process-with-partial-path]
        cwd=donor.git_dir,
        check=True,
        capture_output=True,
    ).stdout


def _git_text(donor: DonorRepository, *arguments: str) -> str:
    return _git_bytes(donor, *arguments).decode("utf-8").strip()


def _roles(path: str, byte_count: int) -> tuple[str, ...]:
    pure = PurePosixPath(path)
    roles: set[str] = {"tracked_file"}
    if path.startswith(".github/workflows/") and pure.suffix in {
        ".yml",
        ".yaml",
    }:
        roles.add("workflow")
    if "fixtures" in pure.parts:
        roles.add("fixture")
    if pure.suffix.lower() in {".csv", ".html", ".xml", ".xlsx"} and (
        "data" in pure.parts
        or "fixtures" in pure.parts
        or "parsing" in pure.parts
    ):
        roles.add("data_object")
    if pure.suffix == ".ipynb" or (byte_count == 0 and path.endswith(".xml")):
        roles.add(
            "legacy_placeholder" if byte_count == 0 else "legacy_artifact"
        )
    if pure.suffix == ".py":
        roles.add("code")
    if pure.name.lower() in {"roadmap.md", "todo.md"}:
        roles.add("roadmap")
    if pure.suffix == ".md":
        roles.add("documentation")
    return tuple(sorted(roles))


def _classification(  # ruff: ignore[too-many-return-statements] - exhaustive disposition policy
    path: str, roles: tuple[str, ...], payload: bytes
) -> tuple[str, Disposition, str]:
    if "legacy_placeholder" in roles:
        return (
            "empty-placeholder",
            "retain-legacy",
            "Preserve the exact empty historical path without a data claim.",
        )
    if "data_object" in roles:
        if "fixtures" in roles:
            return (
                "fixture",
                "adapt",
                "Retain as a characterized compatibility fixture behind GMA safety contracts.",
            )
        return (
            "source-data",
            "retain-legacy",
            "Preserve exact source bytes and provenance for governed replay.",
        )
    if "workflow" in roles:
        return (
            "workflow",
            "replace-with-equivalent",
            "Retain intent while replacing green-with-no-data automation.",
        )
    if path.endswith("parse_pbs_xml.py") and payload.rstrip().endswith(b"```"):
        return (
            "defective-code",
            "replace-with-equivalent",
            "The donor Python is syntactically invalid and must not be promoted.",
        )
    if path.endswith("parse_mbs_xml.py"):
        return (
            "defective-code",
            "replace-with-equivalent",
            "The parser assumes the wrong repeated MBS element.",
        )
    if path.endswith(("processor.py", "main.py")):
        return (
            "partially-defective-code",
            "replace-with-equivalent",
            "Preserve behavior through typed contracts without the path/type defect.",
        )
    if "code" in roles:
        return (
            "implemented-code",
            "adapt",
            "Retain useful behavior behind GMA typing, safety, and provenance controls.",
        )
    if "roadmap" in roles:
        return (
            "roadmap",
            "retain-legacy",
            "Preserve design intent and route it to explicit successor tracks.",
        )
    if "documentation" in roles:
        return (
            "documentation",
            "retain-legacy",
            "Preserve repository and design provenance.",
        )
    return (
        "repository-metadata",
        "supersede",
        "The canonical repository provides the maintained equivalent.",
    )


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.functions: list[tuple[str, int, bool]] = []

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        name = ".".join((*self.stack, node.name))
        self.functions.append((
            name,
            node.lineno,
            isinstance(node, ast.AsyncFunctionDef),
        ))
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def _python_functions(payload: bytes) -> tuple[tuple[str, int, bool], ...]:
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError:
        return ()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        if not source.rstrip().endswith("```"):
            return ()
        try:
            tree = ast.parse(source.rstrip()[:-3].rstrip() + "\n")
        except SyntaxError:
            return ()
    visitor = _FunctionVisitor()
    visitor.visit(tree)
    return tuple(visitor.functions)


def _workflow_jobs(payload: bytes) -> tuple[str, ...]:
    loaded = cast("object", yaml.safe_load(payload))
    if not isinstance(loaded, dict):
        return ()
    document = cast("dict[str, object]", loaded)
    jobs_value = document.get("jobs")
    if not isinstance(jobs_value, dict):
        return ()
    jobs = cast("dict[str, object]", jobs_value)
    return tuple(sorted(str(job) for job in jobs))


def _tree_rows(donor: DonorRepository) -> tuple[tuple[str, str, int, str], ...]:
    output = _git_bytes(
        donor,
        "ls-tree",
        "-r",
        "-z",
        "--long",
        donor.revision,
    )
    rows: list[tuple[str, str, int, str]] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        header, path_bytes = raw.split(b"\t", 1)
        mode, _kind, object_id, size = header.decode("ascii").split()
        rows.append((mode, object_id, int(size), path_bytes.decode("utf-8")))
    return tuple(rows)


def _identity(items: tuple[BaseModel, ...]) -> set[str]:
    return {
        json.dumps(
            item.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        for item in items
    }


def build_inventory(
    donors: tuple[DonorRepository, ...],
) -> AustralianDonorInventory:
    """Build a deterministic inventory directly from immutable Git objects."""
    files: list[DonorFile] = []
    functions: list[DonorFunction] = []
    workflows: list[DonorWorkflow] = []
    for donor in sorted(donors, key=lambda item: item.repository):
        for mode, object_id, byte_count, path in _tree_rows(donor):
            payload = _git_bytes(donor, "show", f"{donor.revision}:{path}")
            if len(payload) != byte_count:
                raise InventoryCompletenessError(
                    f"Git byte count drifted for {donor.repository}:{path}"
                )
            roles = _roles(path, byte_count)
            state, disposition, reason = _classification(path, roles, payload)
            files.append(
                DonorFile(
                    repository=donor.repository,
                    revision=donor.revision,
                    path=path,
                    mode=mode,
                    git_object=object_id,
                    byte_count=byte_count,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    language=_LANGUAGES.get(
                        PurePosixPath(path).suffix.lower(), "Other"
                    ),
                    roles=roles,
                    implementation_state=state,
                    disposition=disposition,
                    disposition_reason=reason,
                )
            )
            if path.endswith(".py"):
                functions.extend(
                    DonorFunction(
                        repository=donor.repository,
                        path=path,
                        qualified_name=name,
                        line=line,
                        is_async=is_async,
                        disposition=disposition,
                    )
                    for name, line, is_async in _python_functions(payload)
                )
            if "workflow" in roles:
                workflows.extend(
                    DonorWorkflow(
                        repository=donor.repository,
                        path=path,
                        job=job,
                        disposition="replace-with-equivalent",
                    )
                    for job in _workflow_jobs(payload)
                )
    capabilities = tuple(
        RoadmapCapability(capability=capability, successor_track=successor)
        for capability, successor in _ROADMAP_CAPABILITIES
    )
    repositories = tuple(
        DonorSnapshot(
            repository=donor.repository,
            revision=donor.revision,
            reachable_commit_count=int(
                _git_text(donor, "rev-list", "--count", donor.revision)
            ),
            root_commits=tuple(
                sorted(
                    _git_text(
                        donor,
                        "rev-list",
                        "--max-parents=0",
                        donor.revision,
                    ).splitlines()
                )
            ),
            license_path="LICENSE",
            license_sha256=next(
                item.sha256
                for item in files
                if item.repository == donor.repository
                and item.path == "LICENSE"
            ),
        )
        for donor in sorted(donors, key=lambda item: item.repository)
    )
    denominator = {
        "repositories": [item.model_dump(mode="json") for item in repositories],
        "files": [item.model_dump(mode="json") for item in files],
        "functions": [item.model_dump(mode="json") for item in functions],
        "workflows": [item.model_dump(mode="json") for item in workflows],
        "roadmap_capabilities": [
            item.model_dump(mode="json") for item in capabilities
        ],
    }
    digest = hashlib.sha256(
        json.dumps(denominator, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return AustralianDonorInventory(
        repositories=repositories,
        files=tuple(files),
        functions=tuple(functions),
        workflows=tuple(workflows),
        roadmap_capabilities=capabilities,
        denominator_sha256=digest,
    )


def validate_inventory(
    inventory: AustralianDonorInventory | dict[str, Any],
    donors: tuple[DonorRepository, ...],
) -> InventoryValidationResult:
    """Fail closed unless every pinned file, function, and workflow is present."""
    try:
        observed = (
            inventory
            if isinstance(inventory, AustralianDonorInventory)
            else AustralianDonorInventory.model_validate(inventory)
        )
    except ValidationError as error:
        section = str(error.errors()[0].get("loc", ("inventory",))[0])
        raise InventoryCompletenessError(
            f"{section} inventory is invalid"
        ) from error
    expected = build_inventory(donors)
    for section in ("files", "functions", "workflows", "roadmap_capabilities"):
        observed_items = getattr(observed, section)
        expected_items = getattr(expected, section)
        if _identity(observed_items) != _identity(expected_items):
            raise InventoryCompletenessError(
                f"{section} inventory is incomplete"
            )
    if observed.denominator_sha256 != expected.denominator_sha256:
        raise InventoryCompletenessError("inventory denominator digest drifted")
    return InventoryValidationResult(
        file_count=len(observed.files),
        function_count=len(observed.functions),
        workflow_count=len(observed.workflows),
        data_object_count=sum(
            "data_object" in item.roles for item in observed.files
        ),
        denominator_sha256=observed.denominator_sha256,
    )
