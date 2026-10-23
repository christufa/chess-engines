"""The engine registry: which UCI engines this service runs, and the bounds on requests.

Read from a YAML file (CHESS_ENGINES_CONFIG, default /etc/chess-engines/engines.yaml).
Adding a UCI engine is an entry here plus its binary in the image; see engines.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_CONFIG = "/etc/chess-engines/engines.yaml"


class Limits(BaseModel):
    """Bounds on one request, and on the queue in front of the engine processes."""

    model_config = ConfigDict(extra="forbid")

    default_depth: int = Field(18, ge=1)
    max_depth: int = Field(30, ge=1)
    max_movetime_ms: int = Field(10_000, ge=10)
    max_multipv: int = Field(10, ge=1, le=256)
    # Requests waiting for a free engine process; more are refused with 503.
    max_queue: int = Field(16, ge=0)
    # How long a request may wait for a free engine process.
    queue_timeout_s: float = Field(30, gt=0)
    # A depth search is stopped by the engine after this long and returns what it has.
    max_search_s: float = Field(30, gt=0)
    # Beyond the search's own limit: no answer by then means the engine hung, and it is restarted.
    hang_grace_s: float = Field(10, gt=0)

    @model_validator(mode="after")
    def _default_within_max(self) -> Limits:
        if self.default_depth > self.max_depth:
            raise ValueError("default_depth exceeds max_depth")
        return self


class EngineSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,31}$")
    # The binary; args are appended (an interpreter plus a script in tests, for example).
    path: str
    args: list[str] = []
    version: str
    # Engine processes per pod: requests queue for the next free one.
    workers: int = Field(1, ge=1, le=64)
    # UCI options set at start, e.g. Threads and Hash. MultiPV is set per request.
    options: dict[str, int | str | bool] = {}
    limits: Limits = Limits()

    @property
    def command(self) -> list[str]:
        return [self.path, *self.args]


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_engine: str
    engines: list[EngineSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _names(self) -> Registry:
        names = [e.name for e in self.engines]
        if len(set(names)) != len(names):
            raise ValueError("engine names must be unique")
        if self.default_engine not in names:
            raise ValueError(f"default_engine {self.default_engine!r} is not a registered engine")
        return self

    def get(self, name: str) -> EngineSpec | None:
        return next((e for e in self.engines if e.name == name), None)


def load_registry(path: str | os.PathLike[str] | None = None) -> Registry:
    path = Path(path or os.environ.get("CHESS_ENGINES_CONFIG", DEFAULT_CONFIG))
    with path.open(encoding="utf-8") as f:
        return Registry.model_validate(yaml.safe_load(f))
