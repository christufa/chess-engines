"""Against the real, pinned Stockfish (STOCKFISH_PATH). CI runs these on every PR."""

import concurrent.futures

import pytest
from conftest import START

pytestmark = pytest.mark.engine

MATE_IN_ONE = [
    # (fen, the mating move in SAN)
    ("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", "Rd8#"),  # back rank
    ("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 0 1", "Qxf7#"),  # scholar's mate
    ("3r2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1", "Rd1#"),  # Black mates
]


def analyse(client, **body):
    response = client.post("/v1/analyse", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_reports_stockfish_19(stockfish_client):
    [engine] = stockfish_client.get("/v1/engines").json()["engines"]
    assert engine["id"].startswith("Stockfish 19")


@pytest.mark.parametrize(("fen", "san"), MATE_IN_ONE)
def test_mate_in_one(stockfish_client, fen, san):
    body = analyse(stockfish_client, fen=fen, depth=8)
    best = body["lines"][0]
    assert best["san"] == san
    assert best["score"] == {"cp": None, "mate": 1}
    # White's point of view: positive when White mates, negative when Black does.
    assert best["white_score"]["mate"] == (1 if body["turn"] == "white" else -1)


def test_multipv_ordering_from_the_start(stockfish_client):
    body = analyse(stockfish_client, fen=START, depth=14, multipv=5)
    lines = body["lines"]
    assert [line["rank"] for line in lines] == [1, 2, 3, 4, 5]
    assert len({line["uci"] for line in lines}) == 5  # different first moves
    scores = [line["score"]["cp"] for line in lines]
    assert scores == sorted(scores, reverse=True)
    assert all(line["depth"] >= 14 for line in lines)
    assert all(-100 < s < 100 for s in scores)  # the start is roughly level
    assert lines[0]["san"] in {"e4", "d4", "Nf3", "c4"}
    assert all(len(line["pv"]) == len(line["pv_san"]) >= 2 for line in lines)


def test_multipv_beyond_legal_moves(stockfish_client):
    # The rook on g2 covers g1 and h2: Kxg2 is the only legal move.
    body = analyse(stockfish_client, fen="7k/8/8/8/8/8/6r1/7K w - - 0 1", depth=6, multipv=10)
    assert [line["san"] for line in body["lines"]] == ["Kxg2"]


def test_movetime(stockfish_client):
    body = analyse(stockfish_client, fen=START, movetime_ms=300, multipv=2)
    assert body["limit"] == {"depth": None, "movetime_ms": 300, "nodes": None}
    assert len(body["lines"]) == 2
    assert body["time_ms"] < 5000


def test_nodes(stockfish_client):
    body = analyse(stockfish_client, fen=START, nodes=20_000)
    assert body["limit"] == {"depth": None, "movetime_ms": None, "nodes": 20_000}
    assert 0 < body["lines"][0]["nodes"] <= 25_000  # Stockfish stops close to the budget


def test_deterministic_at_fixed_depth(stockfish_client):
    a = analyse(stockfish_client, fen=START, depth=12, multipv=3)
    b = analyse(stockfish_client, fen=START, depth=12, multipv=3)
    assert [(line["uci"], line["score"]) for line in a["lines"]] == \
           [(line["uci"], line["score"]) for line in b["lines"]]


def test_concurrent_requests_queue(stockfish_client):
    # More requests than engine processes (2): the rest wait in the queue.
    with concurrent.futures.ThreadPoolExecutor(5) as ex:
        results = list(ex.map(lambda _: stockfish_client.post(
            "/v1/analyse", json={"fen": START, "depth": 10, "multipv": 2}), range(5)))
    assert [r.status_code for r in results] == [200] * 5
