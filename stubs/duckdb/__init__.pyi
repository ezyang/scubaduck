from __future__ import annotations

from typing import Any, Mapping, Sequence
from os import PathLike

class DuckDBPyRelation:
    def fetchall(self) -> list[tuple[Any, ...]]: ...

class DuckDBPyConnection:
    def execute(
        self, query: str, parameters: Sequence[Any] | Mapping[str, Any] | None = ...
    ) -> DuckDBPyRelation: ...

def connect(
    database: str | PathLike[str] | None = ...,
    *,
    read_only: bool = ...,
    config: Mapping[str, Any] | None = ...,
) -> DuckDBPyConnection: ...
