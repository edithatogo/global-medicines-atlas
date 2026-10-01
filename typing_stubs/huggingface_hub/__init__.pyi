from collections.abc import Iterable
from typing import Any

class CollectionItem:
    item_id: str
    item_object_id: str
    item_type: str
    note: str | None

class Collection:
    slug: str
    title: str
    description: str
    private: bool
    items: list[CollectionItem]

class DatasetInfo:
    sha: str

class CommitInfo:
    oid: str

class CommitOperationAdd:
    def __init__(
        self, *, path_in_repo: str, path_or_fileobj: bytes | str
    ) -> None: ...

class HfApi:
    def __init__(self, *, token: str | bool | None = ...) -> None: ...
    def dataset_info(self, repo_id: str) -> DatasetInfo: ...
    def create_commit(
        self,
        *,
        repo_id: str,
        operations: Iterable[CommitOperationAdd],
        commit_message: str,
        commit_description: str | None = ...,
        token: str | bool | None = ...,
        repo_type: str | None = ...,
        revision: str | None = ...,
        parent_commit: str | None = ...,
    ) -> CommitInfo: ...

def add_collection_item(
    collection_slug: str,
    item_id: str,
    item_type: str,
    *,
    note: str | None = ...,
    exists_ok: bool = ...,
    token: str | bool | None = ...,
) -> Collection: ...
def get_collection(
    collection_slug: str, *, token: str | bool | None = ...
) -> Collection: ...
def hf_hub_download(
    repo_id: str,
    filename: str,
    *,
    repo_type: str | None = ...,
    revision: str | None = ...,
    token: str | bool | None = ...,
) -> str: ...
def update_collection_item(
    collection_slug: str,
    item_object_id: str,
    *,
    note: str | None = ...,
    position: int | None = ...,
    token: str | bool | None = ...,
) -> None: ...
def update_collection_metadata(
    collection_slug: str,
    *,
    title: str | None = ...,
    description: str | None = ...,
    position: int | None = ...,
    private: bool | None = ...,
    theme: str | None = ...,
    token: str | bool | None = ...,
) -> Collection: ...
def whoami(*, token: str | bool | None = ...) -> dict[str, Any]: ...
