import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chess_engines.app import create_app
from chess_engines.registry import Registry, load_registry

FAKE = str(Path(__file__).with_name("fake_engine.py"))
START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def registry(engines: list[dict], default: str) -> Registry:
    return Registry.model_validate({"default_engine": default, "engines": engines})


def fake(name: str = "fake", mode: str = "ok", **overrides) -> dict:
    return {"name": name, "path": sys.executable, "args": [FAKE, mode], "version": "1.0",
            "options": {"Threads": 1, "Hash": 16}, **overrides}


@pytest.fixture
def fake_client():
    with TestClient(create_app(registry([fake()], "fake"))) as client:
        yield client


@pytest.fixture(scope="session")
def stockfish_path() -> str:
    path = os.environ.get("STOCKFISH_PATH")
    if not path or not Path(path).exists():
        if os.environ.get("CHESS_ENGINES_REQUIRE_STOCKFISH") == "1":
            pytest.fail("STOCKFISH_PATH must point to a Stockfish binary here")
        pytest.skip("STOCKFISH_PATH not set (engines/stockfish/fetch.sh downloads the pinned release)")
    return path


@pytest.fixture(scope="session")
def stockfish_client(stockfish_path):
    reg = registry([{
        "name": "stockfish", "path": stockfish_path, "version": "19", "workers": 2,
        "options": {"Threads": 1, "Hash": 32},
        "limits": {"default_depth": 12, "max_depth": 30, "max_movetime_ms": 5000, "max_multipv": 10},
    }], "stockfish")
    with TestClient(create_app(reg)) as client:
        yield client


@pytest.fixture(scope="session")
def maia_client():
    """Three Maia levels on the real Lc0 (LC0_PATH) and nets (MAIA_DIR), set up as
    engines/engines.yaml sets them up."""
    lc0, nets = os.environ.get("LC0_PATH"), os.environ.get("MAIA_DIR")
    if not (lc0 and nets and Path(lc0).exists() and Path(nets).is_dir()):
        if os.environ.get("CHESS_ENGINES_REQUIRE_STOCKFISH") == "1":
            pytest.fail("LC0_PATH and MAIA_DIR must point to Lc0 and the Maia nets here")
        pytest.skip("LC0_PATH and MAIA_DIR not set (engines/lc0/build.sh, engines/maia/fetch.sh)")
    shipped = load_registry(Path(__file__).parents[1] / "engines" / "engines.yaml")
    engines = []
    for level in (1100, 1500, 1900):
        spec = shipped.get(f"maia-{level}").model_dump()
        spec.update(path=lc0, args=[f"--weights={Path(nets) / f'maia-{level}.pb.gz'}"])
        engines.append(spec)
    with TestClient(create_app(registry(engines, "maia-1500"))) as client:
        yield client
