"""API behaviour against the fake engine: validation, bounds, the queue and restarts."""

import concurrent.futures
from pathlib import Path

import pytest
from conftest import START, fake, registry
from fastapi.testclient import TestClient

from chess_engines.app import create_app
from chess_engines.registry import Registry, load_registry


def test_health(fake_client):
    assert fake_client.get("/healthz").json() == {"status": "ok"}
    assert fake_client.get("/readyz").status_code == 200


def test_engines_lists_registry(fake_client):
    [engine] = fake_client.get("/v1/engines").json()["engines"]
    assert engine["name"] == "fake"
    assert engine["version"] == "1.0"
    assert engine["id"] == "FakeEngine 1.0"
    assert engine["default"] is True
    assert engine["limits"]["max_depth"] == 30


def test_analyse_shape(fake_client):
    body = fake_client.post("/v1/analyse", json={"fen": START, "multipv": 3}).json()
    assert body["engine"] == {"name": "fake", "version": "1.0", "id": "FakeEngine 1.0"}
    assert body["limit"] == {"depth": 18, "movetime_ms": None}  # the default depth
    assert body["turn"] == "white"
    assert [line["rank"] for line in body["lines"]] == [1, 2, 3]
    first = body["lines"][0]
    assert first["pv"][0] == first["uci"]
    assert first["pv_san"][0] == first["san"]
    assert first["score"] == {"cp": 100, "mate": None}


def test_black_to_move_white_score_flips(fake_client):
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    line = fake_client.post("/v1/analyse", json={"fen": fen}).json()["lines"][0]
    assert line["score"]["cp"] == 100
    assert line["white_score"]["cp"] == -100


@pytest.mark.parametrize("fen", [
    "not a fen",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN w KQkq - 0 1",  # short rank
    "8/8/8/8/8/8/8/8 w - - 0 1",  # no kings
    "4k3/4R3/8/8/8/8/8/4K3 w - - 0 1",  # Black is in check with White to move
    "4k3/8/8/8/8/8/8/R3K2R w KQkq - 0 1",  # castling rights without rooks
    "x" * 121,
])
def test_invalid_fens(fake_client, fen):
    response = fake_client.post("/v1/analyse", json={"fen": fen})
    assert response.status_code == 422, response.text


def test_opposite_check_is_named(fake_client):
    response = fake_client.post("/v1/analyse", json={"fen": "4k3/4R3/8/8/8/8/8/4K3 w - - 0 1"})
    assert "opposite_check" in response.json()["detail"]


@pytest.mark.parametrize("body", [
    {"depth": 31}, {"depth": 0}, {"movetime_ms": 10_001}, {"movetime_ms": 5},
    {"multipv": 11}, {"multipv": 0}, {"depth": 10, "movetime_ms": 100}, {"nodes": 5},
])
def test_bounds(fake_client, body):
    assert fake_client.post("/v1/analyse", json={"fen": START, **body}).status_code == 422


def test_unknown_engine(fake_client):
    assert fake_client.post("/v1/analyse", json={"fen": START, "engine": "lc0"}).status_code == 404


def test_terminal_positions_skip_the_engine(fake_client):
    mated = fake_client.post("/v1/analyse", json={"fen": "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"}).json()
    assert mated["outcome"] == "checkmate" and mated["lines"] == []
    stale = fake_client.post("/v1/analyse", json={"fen": "7k/8/6QK/8/8/8/8/8 b - - 0 1"}).json()
    assert stale["outcome"] == "stalemate" and stale["lines"] == []


def test_hung_engine_is_restarted():
    limits = {"max_search_s": 0.5, "hang_grace_s": 0.5}
    with TestClient(create_app(registry([fake(mode="hang", limits=limits)], "fake"))) as client:
        worker = client.app.state.pools["fake"].workers[0]
        before = worker.transport.get_pid()
        response = client.post("/v1/analyse", json={"fen": START})
        assert response.status_code == 504
        assert response.headers["retry-after"] == "5"
        assert worker.transport.get_pid() != before  # a fresh process
        assert client.get("/readyz").status_code == 200


def test_queue_full_is_503():
    limits = {"max_search_s": 1, "hang_grace_s": 1, "max_queue": 0}
    with TestClient(create_app(registry([fake(mode="hang", limits=limits)], "fake"))) as client, \
            concurrent.futures.ThreadPoolExecutor(1) as ex:
        first = ex.submit(client.post, "/v1/analyse", json={"fen": START})
        # Once the only process is busy, a second request finds no room in the queue.
        for _ in range(200):
            if client.get("/v1/load").json()["in_flight"] == 1:
                break
        second = client.post("/v1/analyse", json={"fen": START})
        assert second.status_code == 503
        assert first.result().status_code == 504


def test_load_reports_utilization(fake_client):
    load = fake_client.get("/v1/load").json()
    assert load == {"utilization": 0.0, "in_flight": 0, "queued": 0, "workers": 1}


def test_registry_rejects_bad_config():
    with pytest.raises(ValueError):
        Registry.model_validate({"default_engine": "x", "engines": [fake("y")]})
    with pytest.raises(ValueError):
        Registry.model_validate({"default_engine": "y", "engines": [fake("y"), fake("y")]})
    with pytest.raises(ValueError):
        Registry.model_validate({"default_engine": "y", "engines": [fake("y", limits={"default_depth": 40})]})


def test_shipped_registry_is_valid():
    reg = load_registry(Path(__file__).parents[1] / "engines" / "engines.yaml")
    assert reg.default_engine == "stockfish"
