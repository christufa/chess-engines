import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chess_engines.app import create_app
from chess_engines.registry import Registry

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
