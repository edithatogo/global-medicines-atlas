"""Build exact, omission-sensitive inventories of donor Git repositories."""

from __future__ import annotations

import ast
import hashlib
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - read-only Git
from pathlib import Path, PurePosixPath
from typing import cast


class DonorInventoryError(ValueError):
    """Raised when a donor inventory is incomplete or inconsistent."""


_WORKFLOW_PREFIX_LENGTH = 2


def _git(repository: Path, *arguments: str) -> bytes:
    """Run a read-only Git query against ``repository``."""
    executable = shutil.which("git")
    if executable is None:
        raise DonorInventoryError("Git executable is unavailable")
    try:
        completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - arguments never use a shell
            [executable, *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise DonorInventoryError(
            f"Git query failed for {repository}: git {' '.join(arguments)}"
        ) from error
    return completed.stdout


def _resolved_commit(repository: Path, revision: str) -> str:
    resolved = _git(repository, "rev-parse", f"{revision}^{{commit}}")
    return resolved.decode("ascii").strip()


def _tree_entries(repository: Path, commit: str) -> list[tuple[str, str, int]]:
    raw = _git(repository, "ls-tree", "-r", "-z", "-l", commit)
    entries: list[tuple[str, str, int]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", maxsplit=1)
        mode, object_type, _object_id, encoded_size = metadata.split(maxsplit=3)
        if object_type != b"blob":
            continue
        entries.append((
            encoded_path.decode("utf-8", errors="surrogateescape"),
            mode.decode("ascii"),
            int(encoded_size),
        ))
    return sorted(entries)


def _blob(repository: Path, commit: str, path: str) -> bytes:
    return _git(repository, "show", f"{commit}:{path}")


def _language(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    languages = {
        ".csv": "csv",
        ".ipynb": "jupyter-notebook",
        ".json": "json",
        ".md": "markdown",
        ".py": "python",
        ".toml": "toml",
        ".xlsx": "excel-workbook",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".zip": "zip",
    }
    return languages.get(suffix, "binary-or-text")


def _data_role(path: str) -> str:
    pure_path = PurePosixPath(path)
    suffix = pure_path.suffix.lower()
    if suffix in {".csv", ".parquet", ".xls", ".xlsx", ".xml", ".zip"}:
        return "raw_payload"
    if suffix == ".ipynb":
        return "legacy_notebook"
    if len(pure_path.parts) >= _WORKFLOW_PREFIX_LENGTH and pure_path.parts[
        :_WORKFLOW_PREFIX_LENGTH
    ] == (
        ".github",
        "workflows",
    ):
        return "workflow"
    if suffix == ".py":
        return "source_code"
    if suffix == ".md":
        return "documentation_or_design"
    return "repository_support"


def _python_characterization(content: bytes) -> tuple[list[str], str | None]:
    try:
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError) as error:
        return [], f"{type(error).__name__}: {error}"
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    return sorted(functions), None


def _implementation_state(
    path: str,
    content: bytes,
    *,
    parse_error: str | None,
) -> str:
    state = "supporting_artifact"
    if not content:
        state = "zero_byte"
    elif parse_error is not None:
        state = "invalid_syntax"
    pure_path = PurePosixPath(path)
    if content and parse_error is None:
        if pure_path.suffix.lower() == ".py":
            state = "implemented"
        elif _data_role(path) == "raw_payload":
            state = "data_artifact"
        elif pure_path.name.lower() in {"roadmap.md", "todo.md"}:
            state = "design_intent"
        elif _data_role(path) == "workflow":
            state = "workflow"
    return state


def _disposition(data_role: str, implementation_state: str) -> str:
    if implementation_state == "zero_byte":
        return "retain_legacy_evidence"
    if implementation_state == "invalid_syntax":
        return "replace_and_preserve_legacy"
    if data_role == "raw_payload":
        return "retain_exact_in_public_hf"
    if implementation_state == "design_intent":
        return "map_to_successor_capability"
    if data_role in {"source_code", "workflow"}:
        return "adapt_or_replace_with_tests"
    return "preserve_provenance"


def build_donor_inventory(
    repository: Path,
    *,
    repository_name: str,
    expected_commit: str,
    source_url: str,
) -> dict[str, object]:
    """Build a deterministic inventory for one exact donor commit.

    The function reads committed blobs directly, so a dirty donor working tree
    cannot alter the result or be modified by inventory generation.
    """
    repository = repository.resolve()
    head = _resolved_commit(repository, "HEAD")
    try:
        commit = _resolved_commit(repository, expected_commit)
    except DonorInventoryError as error:
        raise DonorInventoryError(
            f"expected commit {expected_commit} is unavailable in {repository}"
        ) from error
    if head != commit:
        raise DonorInventoryError(
            f"repository HEAD {head} does not equal expected commit {commit}"
        )

    files: list[dict[str, object]] = []
    for path, mode, expected_size in _tree_entries(repository, commit):
        content = _blob(repository, commit, path)
        if len(content) != expected_size:
            raise DonorInventoryError(
                f"Git reported {expected_size} bytes for {path}, got {len(content)}"
            )
        functions: list[str] = []
        parse_error: str | None = None
        if PurePosixPath(path).suffix.lower() == ".py" and content:
            functions, parse_error = _python_characterization(content)
        data_role = _data_role(path)
        implementation_state = _implementation_state(
            path,
            content,
            parse_error=parse_error,
        )
        entry: dict[str, object] = {
            "path": path,
            "mode": mode,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "language": _language(path),
            "data_role": data_role,
            "implementation_state": implementation_state,
            "disposition": _disposition(data_role, implementation_state),
            "functions": functions,
        }
        if parse_error is not None:
            entry["parse_error"] = parse_error
        files.append(entry)

    return {
        "schema_version": "1.0",
        "repository": repository_name,
        "source_url": source_url,
        "commit": commit,
        "tree": _git(repository, "rev-parse", f"{commit}^{{tree}}")
        .decode("ascii")
        .strip(),
        "tracked_blob_count": len(files),
        "total_blob_bytes": sum(
            cast("int", item["size_bytes"]) for item in files
        ),
        "files": files,
    }


def _files(document: dict[str, object]) -> list[dict[str, object]]:
    value = document.get("files")
    if not isinstance(value, list):
        raise DonorInventoryError("inventory files must be a list of objects")
    items = cast("list[object]", value)
    if not all(isinstance(item, dict) for item in items):
        raise DonorInventoryError("inventory files must be a list of objects")
    return cast("list[dict[str, object]]", value)


def validate_donor_inventory(
    repository: Path,
    inventory: dict[str, object],
    *,
    expected_repository_name: str,
    expected_source_url: str,
) -> None:
    """Validate an inventory against a pinned identity and every Git blob."""
    for field, expected_identity in (
        ("repository", expected_repository_name),
        ("source_url", expected_source_url),
    ):
        if inventory.get(field) != expected_identity:
            raise DonorInventoryError(
                f"inventory {field} differs from pinned donor identity"
            )
    commit = inventory.get("commit")
    if not isinstance(commit, str):
        raise DonorInventoryError("inventory commit must be a string")
    expected = build_donor_inventory(
        repository,
        repository_name=expected_repository_name,
        expected_commit=commit,
        source_url=expected_source_url,
    )
    actual_files = _files(inventory)
    expected_files = _files(expected)
    if actual_files != expected_files:
        raise DonorInventoryError(
            "inventory file denominator differs from Git tree"
        )
    for field in (
        "schema_version",
        "commit",
        "tree",
        "tracked_blob_count",
        "total_blob_bytes",
    ):
        if inventory.get(field) != expected.get(field):
            raise DonorInventoryError(
                f"inventory {field} differs from Git tree"
            )
