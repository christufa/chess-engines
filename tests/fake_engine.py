"""A tiny UCI engine for tests that don't need Stockfish.

`fake_engine.py ok`: answers every `go` at once with the first legal moves, scored
100, 90, 80... `fake_engine.py hang`: answers the handshake, then never answers `go`.
"""

import sys

import chess

mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
board = chess.Board()
multipv = 1


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


for raw in sys.stdin:
    cmd = raw.split()
    if not cmd:
        continue
    if cmd[0] == "uci":
        say("id name FakeEngine 1.0")
        say("option name Threads type spin default 1 min 1 max 512")
        say("option name Hash type spin default 16 min 1 max 1024")
        say("option name MultiPV type spin default 1 min 1 max 256")
        say("uciok")
    elif cmd[0] == "isready":
        say("readyok")
    elif cmd[:4] == ["setoption", "name", "MultiPV", "value"]:
        multipv = int(cmd[4])
    elif cmd[0] == "position":
        if cmd[1] == "startpos":
            board = chess.Board()
            rest = cmd[2:]
        else:
            board = chess.Board(" ".join(cmd[2:8]))
            rest = cmd[8:]
        for uci in rest[1:] if rest[:1] == ["moves"] else []:
            board.push_uci(uci)
    elif cmd[0] == "go":
        if mode == "hang":
            continue
        moves = list(board.legal_moves)[:multipv]
        for i, move in enumerate(moves, start=1):
            say(f"info depth 5 seldepth 7 multipv {i} score cp {110 - 10 * i} nodes 1000 pv {move.uci()}")
        say(f"bestmove {moves[0].uci()}")
    elif cmd[0] == "quit":
        break
