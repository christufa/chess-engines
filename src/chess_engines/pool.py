"""Engine processes and the queue in front of them.

Each registered engine gets `workers` UCI processes. A request takes a free one, waiting in
a bounded queue if none is free, and gives it back afterwards. A search that runs past its
own limit plus a grace period means the process hung: it is killed and started again, and
the request fails with a timeout. A crashed process is restarted the same way.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass

import chess
import chess.engine

from .registry import EngineSpec

log = logging.getLogger(__name__)


class QueueFull(Exception):
    """Too many requests are already waiting for this engine."""


class QueueTimeout(Exception):
    """No engine process became free in time."""


class EngineHung(Exception):
    """The engine didn't answer in time, or died; it is being restarted."""


@dataclass
class SearchLimit:
    depth: int | None = None
    movetime_ms: int | None = None


class Worker:
    def __init__(self, spec: EngineSpec, index: int):
        self.spec = spec
        self.index = index
        self.transport: asyncio.SubprocessTransport | None = None
        self.engine: chess.engine.UciProtocol | None = None

    async def start(self) -> None:
        self.transport, self.engine = await chess.engine.popen_uci(self.spec.command)
        await self.engine.configure(self.spec.options)
        await self.engine.ping()
        log.info("%s worker %d started (%s)", self.spec.name, self.index, self.engine.id.get("name"))

    @property
    def alive(self) -> bool:
        return self.engine is not None and not self.engine.returncode.done()

    async def stop(self) -> None:
        """Ask the engine to quit, then kill it if it doesn't."""
        engine, transport = self.engine, self.transport
        self.engine = self.transport = None
        if engine is not None and not engine.returncode.done():
            with contextlib.suppress(Exception):
                await asyncio.wait_for(engine.quit(), timeout=2)
        if transport is not None:
            with contextlib.suppress(ProcessLookupError):
                transport.kill()
            transport.close()

    async def restart(self) -> None:
        await self.stop()
        await self.start()


class EnginePool:
    def __init__(self, spec: EngineSpec):
        self.spec = spec
        self.workers = [Worker(spec, i) for i in range(spec.workers)]
        self._idle: asyncio.Queue[Worker] = asyncio.Queue()
        self.waiting = 0
        self.in_flight = 0
        self.engine_id = ""

    async def start(self) -> None:
        for worker in self.workers:
            await worker.start()
            self._idle.put_nowait(worker)
        self.engine_id = self.workers[0].engine.id.get("name", "")

    async def stop(self) -> None:
        await asyncio.gather(*(w.stop() for w in self.workers))

    @property
    def alive_workers(self) -> int:
        return sum(w.alive for w in self.workers)

    async def analyse(
        self, board: chess.Board, limit: SearchLimit, multipv: int
    ) -> list[chess.engine.InfoDict]:
        limits = self.spec.limits
        if self.waiting >= limits.max_queue and self._idle.empty():
            raise QueueFull(self.spec.name)
        self.waiting += 1
        try:
            worker = await asyncio.wait_for(self._idle.get(), timeout=limits.queue_timeout_s)
        except TimeoutError:
            raise QueueTimeout(self.spec.name) from None
        finally:
            self.waiting -= 1

        self.in_flight += 1
        try:
            return await self._search(worker, board, limit, multipv)
        finally:
            self.in_flight -= 1
            self._idle.put_nowait(worker)

    async def _search(
        self, worker: Worker, board: chess.Board, limit: SearchLimit, multipv: int
    ) -> list[chess.engine.InfoDict]:
        limits = self.spec.limits
        if limit.movetime_ms is not None:
            engine_limit = chess.engine.Limit(time=limit.movetime_ms / 1000)
            budget = limit.movetime_ms / 1000
        else:
            # The engine itself stops a deep search at max_search_s and reports what it has.
            engine_limit = chess.engine.Limit(depth=limit.depth, time=limits.max_search_s)
            budget = limits.max_search_s
        started = time.monotonic()
        try:
            if not worker.alive:
                await worker.restart()
            # A new game per request: no hash carried over, so the same request gets the
            # same answer (with Threads=1 and a depth limit).
            return await asyncio.wait_for(
                worker.engine.analyse(board, engine_limit, multipv=multipv, game=object(),
                                      info=chess.engine.INFO_ALL),
                timeout=budget + limits.hang_grace_s,
            )
        except (TimeoutError, chess.engine.EngineTerminatedError, chess.engine.EngineError) as exc:
            log.warning("%s worker %d failed after %.1fs (%r); restarting",
                        self.spec.name, worker.index, time.monotonic() - started, exc)
            try:
                await worker.restart()
            except Exception:
                log.exception("%s worker %d did not restart", self.spec.name, worker.index)
            raise EngineHung(self.spec.name) from exc
