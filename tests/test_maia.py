"""Against the real Lc0 (LC0_PATH) with the pinned Maia nets (MAIA_DIR). CI runs these on
every PR."""

import pytest
from conftest import START

pytestmark = pytest.mark.engine

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
# Both sides can castle either way; the centre is open to captures.
BOTH_CASTLE = "r3k2r/pppq1ppp/2n1bn2/3pp3/3PP3/2N1BN2/PPPQ1PPP/R3K2R w KQkq - 0 1"


def analyse(client, **body):
    response = client.post("/v1/analyse", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_runs_on_lc0(maia_client):
    engines = maia_client.get("/v1/engines").json()["engines"]
    assert [e["name"] for e in engines] == ["maia-1100", "maia-1500", "maia-1900"]
    assert all(e["id"].startswith("Lc0 v0.32.1") for e in engines)


@pytest.mark.parametrize("level", [1100, 1500, 1900])
def test_human_replies_to_e4(maia_client, level):
    body = analyse(maia_client, fen=AFTER_E4, engine=f"maia-{level}", multipv=5)
    assert body["limit"] == {"depth": None, "movetime_ms": None, "nodes": 1}
    lines = body["lines"]
    assert len(lines) == 5
    probabilities = [line["probability"] for line in lines]
    assert all(p is not None and 0 < p < 1 for p in probabilities)
    assert probabilities == sorted(probabilities, reverse=True)
    assert sum(probabilities) < 1
    # Every level's favourite is one of the common human replies.
    assert lines[0]["san"] in {"e5", "c5", "e6", "d5", "c6", "Nf6", "d6", "Nc6"}


def test_levels_differ(maia_client):
    # The nets are trained on different players, so their move distributions differ.
    first = {
        level: [(line["san"], line["probability"])
                for line in analyse(maia_client, fen=AFTER_E4, engine=f"maia-{level}", multipv=5)["lines"]]
        for level in (1100, 1900)
    }
    assert first[1100] != first[1900]


def test_deterministic(maia_client):
    a = analyse(maia_client, fen=START, engine="maia-1500", multipv=3)["lines"]
    b = analyse(maia_client, fen=START, engine="maia-1500", multipv=3)["lines"]
    def moves(lines):
        return [(line["uci"], line["probability"]) for line in lines]

    assert moves(a) == moves(b)


def test_castling_moves_are_standard_uci(maia_client):
    lines = analyse(maia_client, fen=BOTH_CASTLE, engine="maia-1500", multipv=10)["lines"]
    castles = {line["san"]: line for line in lines if line["san"].startswith("O-O")}
    for san, uci in (("O-O", "e1g1"), ("O-O-O", "e1c1")):
        if san in castles:
            assert castles[san]["uci"] == uci
            assert castles[san]["probability"] is not None


def test_one_node_only(maia_client):
    response = maia_client.post("/v1/analyse", json={"fen": START, "engine": "maia-1500", "depth": 5})
    assert response.status_code == 422
    response = maia_client.post("/v1/analyse", json={"fen": START, "engine": "maia-1500", "nodes": 2})
    assert response.status_code == 422


def test_multipv_beyond_legal_moves(maia_client):
    body = analyse(maia_client, fen="7k/8/8/8/8/8/6r1/7K w - - 0 1", engine="maia-1500", multipv=10)
    assert [line["san"] for line in body["lines"]] == ["Kxg2"]
