"""Request and response bodies of the HTTP API (also its OpenAPI schema)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyseRequest(BaseModel):
    """Analyse one position. Give `depth` or `movetime_ms`, not both; neither means the
    engine's default depth. Upper bounds are per engine (`GET /v1/engines`)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "engine": "stockfish",
                 "depth": 18, "multipv": 3}
            ]
        },
    )

    fen: str = Field(max_length=120, description="Position in FEN (standard chess)")
    engine: str | None = Field(None, description="Registered engine name; omitted means the default engine")
    depth: int | None = Field(None, ge=1, description="Search to this depth")
    movetime_ms: int | None = Field(None, ge=10, description="Search for this long")
    multipv: int = Field(1, ge=1, description="Number of best lines to return")

    @model_validator(mode="after")
    def _one_limit(self) -> AnalyseRequest:
        if self.depth is not None and self.movetime_ms is not None:
            raise ValueError("give depth or movetime_ms, not both")
        return self


class Score(BaseModel):
    """Exactly one of cp and mate is set. mate > 0: the side to move (or White, in
    white_score) mates in that many moves; mate < 0: gets mated."""

    cp: int | None = Field(None, description="Centipawns")
    mate: int | None = Field(None, description="Moves to mate")


class Line(BaseModel):
    rank: int = Field(description="1 is the engine's best move")
    uci: str = Field(description="The move in UCI notation, e.g. e2e4")
    san: str = Field(description="The move in SAN, e.g. e4")
    score: Score = Field(description="From the side to move's point of view (as UCI reports it)")
    white_score: Score = Field(description="From White's point of view")
    depth: int
    seldepth: int | None = None
    nodes: int | None = None
    pv: list[str] = Field(description="Principal variation in UCI, starting with this move")
    pv_san: list[str] = Field(description="The same variation in SAN")


class EngineInfo(BaseModel):
    name: str = Field(description="Registry name, used in requests")
    version: str = Field(description="Pinned release in this image")
    id: str = Field(description="What the engine reports over UCI (id name)")


class SearchLimitOut(BaseModel):
    depth: int | None = None
    movetime_ms: int | None = None


class AnalyseResponse(BaseModel):
    fen: str = Field(description="The position, normalised")
    turn: Literal["white", "black"]
    engine: EngineInfo
    limit: SearchLimitOut
    multipv: int
    outcome: Literal["checkmate", "stalemate"] | None = Field(
        None, description="Set when the side to move has no legal moves; lines is then empty")
    lines: list[Line] = Field(description="Best first; fewer than multipv when there are fewer legal moves")
    time_ms: int = Field(description="Wall time spent in the engine, including any queue wait")


class EngineLimits(BaseModel):
    default_depth: int
    max_depth: int
    max_movetime_ms: int
    max_multipv: int


class EngineEntry(EngineInfo):
    default: bool
    workers: int
    options: dict[str, int | str | bool]
    limits: EngineLimits


class EnginesResponse(BaseModel):
    engines: list[EngineEntry]


class Load(BaseModel):
    """This pod's load, for KEDA's metrics-api scaler."""

    utilization: float = Field(description="(searching + queued) / engine processes")
    in_flight: int
    queued: int
    workers: int


class Problem(BaseModel):
    detail: str
