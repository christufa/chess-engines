"""HTTP API: UCI engine analysis over HTTP. See docs/api.md."""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import chess
import chess.engine
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .models import (
    AnalyseRequest,
    AnalyseResponse,
    EngineEntry,
    EngineInfo,
    EngineLimits,
    EnginesResponse,
    Line,
    Load,
    Problem,
    Score,
    SearchLimitOut,
)
from .pool import EngineHung, EnginePool, QueueFull, QueueTimeout, SearchLimit
from .registry import Registry, load_registry

log = logging.getLogger(__name__)

# The playground UI (web/), built into the package by docker/Dockerfile.
WEB_DIR = Path(os.environ.get("CHESS_ENGINES_WEB_DIR", Path(__file__).parent / "web"))

# For the playground's pages: its own scripts and styles only. Not on /docs, which loads
# Swagger UI from a CDN.
PLAYGROUND_CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)

ERRORS = {
    404: {"model": Problem, "description": "Unknown engine"},
    422: {"description": "Invalid FEN, or a limit out of bounds"},
    503: {"model": Problem, "description": "Queue full or no engine free in time; retry after Retry-After"},
    504: {"model": Problem, "description": "The engine hung or crashed and is being restarted; retry"},
}


def create_app(registry: Registry | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.registry = registry or load_registry()
        app.state.pools = {}
        try:
            for spec in app.state.registry.engines:
                pool = EnginePool(spec)
                app.state.pools[spec.name] = pool
                await pool.start()
            yield
        finally:
            for pool in app.state.pools.values():
                await pool.stop()

    app = FastAPI(
        title="chess-engines",
        version=__version__,
        description="Shared chess-engine analysis: UCI engines (Stockfish) over HTTP.",
        lifespan=lifespan,
    )

    def pools(request: Request) -> dict[str, EnginePool]:
        return request.app.state.pools

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        """The process is up."""
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"], responses={503: {"description": "An engine has no live process"}})
    async def readyz(request: Request):
        """Every registered engine has at least one live process."""
        down = [name for name, pool in pools(request).items() if pool.alive_workers == 0]
        if down:
            return JSONResponse({"status": "not ready", "engines_down": down}, status_code=503)
        return {"status": "ready"}

    @app.get("/v1/engines", response_model=EnginesResponse, tags=["engines"])
    async def engines(request: Request) -> EnginesResponse:
        """The registered engines, their versions and request limits."""
        reg: Registry = request.app.state.registry
        return EnginesResponse(engines=[
            EngineEntry(
                name=spec.name, version=spec.version, id=pools(request)[spec.name].engine_id,
                default=spec.name == reg.default_engine, workers=spec.workers, options=spec.options,
                limits=EngineLimits(**spec.limits.model_dump(include=set(EngineLimits.model_fields))),
            )
            for spec in reg.engines
        ])

    @app.get("/v1/load", response_model=Load, tags=["health"])
    async def load(request: Request) -> Load:
        """This pod's load (KEDA polls it to scale)."""
        in_flight = sum(p.in_flight for p in pools(request).values())
        queued = sum(p.waiting for p in pools(request).values())
        workers = sum(len(p.workers) for p in pools(request).values())
        return Load(utilization=round((in_flight + queued) / workers, 3), in_flight=in_flight,
                    queued=queued, workers=workers)

    @app.post("/v1/analyse", response_model=AnalyseResponse, response_model_exclude_none=False,
              responses=ERRORS, tags=["analysis"])
    async def analyse(body: AnalyseRequest, request: Request) -> AnalyseResponse:
        """Analyse a position and return the best `multipv` lines, best first."""
        reg: Registry = request.app.state.registry
        name = body.engine or reg.default_engine
        spec = reg.get(name)
        if spec is None:
            raise HTTPException(404, f"unknown engine {name!r}; see GET /v1/engines")
        lim = spec.limits

        board = parse_fen(body.fen)
        if body.depth is not None and body.depth > lim.max_depth:
            raise HTTPException(422, f"depth must be at most {lim.max_depth} for {name}")
        if body.movetime_ms is not None and body.movetime_ms > lim.max_movetime_ms:
            raise HTTPException(422, f"movetime_ms must be at most {lim.max_movetime_ms} for {name}")
        if body.multipv > lim.max_multipv:
            raise HTTPException(422, f"multipv must be at most {lim.max_multipv} for {name}")
        limit = SearchLimit(depth=body.depth, movetime_ms=body.movetime_ms)
        if limit.depth is None and limit.movetime_ms is None:
            limit.depth = lim.default_depth

        pool = pools(request)[name]
        info = EngineInfo(name=name, version=spec.version, id=pool.engine_id)
        response = dict(
            fen=board.fen(), turn="white" if board.turn else "black", engine=info,
            limit=SearchLimitOut(depth=limit.depth, movetime_ms=limit.movetime_ms), multipv=body.multipv,
        )
        if not any(board.legal_moves):
            outcome = "checkmate" if board.is_check() else "stalemate"
            return AnalyseResponse(**response, outcome=outcome, lines=[], time_ms=0)

        started = time.monotonic()
        try:
            infos = await pool.analyse(board, limit, body.multipv)
        except (QueueFull, QueueTimeout) as exc:
            raise HTTPException(503, f"{name} is busy; retry later", headers={"Retry-After": "5"}) from exc
        except EngineHung as exc:
            raise HTTPException(504, f"{name} did not answer in time and is being restarted; retry",
                                headers={"Retry-After": "5"}) from exc
        elapsed = int((time.monotonic() - started) * 1000)
        return AnalyseResponse(**response, lines=to_lines(board, infos), time_ms=elapsed)

    if WEB_DIR.is_dir():
        @app.middleware("http")
        async def playground_headers(request: Request, call_next):
            response = await call_next(request)
            path = request.url.path
            if not path.startswith(("/v1/", "/docs", "/redoc", "/openapi.json", "/healthz", "/readyz")):
                response.headers["Content-Security-Policy"] = PLAYGROUND_CSP
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["Referrer-Policy"] = "no-referrer"
            return response

        # Last, so the API routes above take precedence.
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="playground")

    return app


def parse_fen(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen.strip())
    except ValueError as exc:
        raise HTTPException(422, f"invalid FEN: {exc}") from None
    status = board.status()
    if status != chess.STATUS_VALID:
        problems = [flag.name.lower() for flag in chess.Status if flag and flag in status]
        raise HTTPException(422, f"illegal position: {', '.join(problems)}")
    return board


def to_score(pov: chess.engine.PovScore | None, color: chess.Color) -> Score:
    score = pov.pov(color)
    if score.is_mate():
        return Score(mate=score.mate())
    return Score(cp=score.score())


def to_lines(board: chess.Board, infos: list[chess.engine.InfoDict]) -> list[Line]:
    lines = []
    for rank, info in enumerate(infos, start=1):
        pv = info.get("pv") or []
        if not pv or "score" not in info:
            continue  # nothing usable (a search stopped before its first iteration)
        san_board = board.copy(stack=False)
        pv_san = []
        for move in pv:
            pv_san.append(san_board.san(move))
            san_board.push(move)
        lines.append(Line(
            rank=rank, uci=pv[0].uci(), san=pv_san[0],
            score=to_score(info["score"], board.turn), white_score=to_score(info["score"], chess.WHITE),
            depth=info.get("depth", 0), seldepth=info.get("seldepth"), nodes=info.get("nodes"),
            pv=[m.uci() for m in pv], pv_san=pv_san,
        ))
    return lines
