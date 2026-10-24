"""A tiny UCI engine for tests that don't need Stockfish.

`fake_engine.py ok`: answers every `go` at once with the first legal moves, scored
100, 90, 80... `fake_engine.py hang`: answers the handshake, then never answers `go`.
`fake_engine.py policy`: like ok, plus an Lc0-style `info string` per legal move with its
policy probability (P), the first move 40%, the next 20%, then 10%, 5%...
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
        if mode == "policy":
            # Lc0 lists the least likely move first.
            for i, move in reversed(list(enumerate(board.legal_moves))):
                p = 40 / 2**i
                say(f"info string {move.uci():<5} ({i:<4}) N:       0 (+ 0) (P: {p:5.2f}%) (Q: -0.03354)")
        say(f"bestmove {moves[0].uci()}")
    elif cmd[0] == "quit":
        break
