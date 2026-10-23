# API

The OpenAPI document is [`openapi.json`](openapi.json) (CI fails if it is stale). A running
service also serves it at `/openapi.json`, with interactive docs at `/docs`.

All bodies are JSON. The API is stable under `/v1`: fields may be added, never renamed or
removed.

## `POST /v1/analyse`

Analyse one position and return the engine's best lines, best first.

| Field | Type | |
|---|---|---|
| `fen` | string | Standard chess FEN, at most 120 characters. Must be a legal position (one king each, the side not to move not in check, consistent castling and en passant). |
| `engine` | string | Registered engine (`GET /v1/engines`). Omitted: the default, `stockfish`. |
| `depth` | int ≥ 1 | Search to this depth. At most the engine's `max_depth` (30). |
| `movetime_ms` | int ≥ 10 | Search for this long instead. At most `max_movetime_ms` (10000). |
| `multipv` | int ≥ 1 | How many lines. Default 1, at most `max_multipv` (10). |

Give `depth` or `movetime_ms`, not both. Neither means `default_depth` (18). A depth search
is also stopped after `max_search_s` (30 s) and returns the deepest completed iteration, so
check each line's `depth`.

```json
{"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "depth": 18, "multipv": 3}
```

Response:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "turn": "white",
  "engine": {"name": "stockfish", "version": "19", "id": "Stockfish 19"},
  "limit": {"depth": 18, "movetime_ms": null},
  "multipv": 3,
  "outcome": null,
  "lines": [
    {
      "rank": 1, "uci": "e2e4", "san": "e4",
      "score": {"cp": 36, "mate": null}, "white_score": {"cp": 36, "mate": null},
      "depth": 18, "seldepth": 24, "nodes": 412345,
      "pv": ["e2e4", "c7c5", "b1c3"], "pv_san": ["e4", "c5", "Nc3"]
    }
  ],
  "time_ms": 345
}
```

- `score` is from the side to move's point of view, as UCI reports it; `white_score` is the
  same score from White's. Exactly one of `cp` (centipawns) and `mate` (moves to mate;
  negative when being mated) is set.
- `lines` has fewer than `multipv` entries when there are fewer legal moves. With no legal
  moves the engine isn't asked: `outcome` is `checkmate` or `stalemate` and `lines` is empty.
- Each request starts a new game in the engine (no hash carried over), and engines run with
  `Threads=1`, so a depth-limited request is reproducible: the same input gives the same
  lines. Time-limited searches are not.

Errors (`{"detail": "..."}`):

| Status | When | What to do |
|---|---|---|
| 404 | Unknown engine | |
| 422 | Invalid FEN or illegal position, a bound exceeded, both limits given, unknown field | Fix the request |
| 503 | Every engine process is busy and the queue is full, or no process freed up within `queue_timeout_s` | Retry after `Retry-After` seconds; more pods are being started |
| 504 | The engine didn't answer within its limit plus `hang_grace_s`, or crashed; it has been restarted | Retry |

## `GET /v1/engines`

The registered engines: `name`, `version` (pinned release), `id` (what the engine reports
over UCI), `default`, `workers` (engine processes per pod), `options` (UCI options such as
`Threads` and `Hash`) and `limits` (`default_depth`, `max_depth`, `max_movetime_ms`,
`max_multipv`).

## Health and load

| Path | |
|---|---|
| `GET /healthz` | 200 while the process is up (liveness) |
| `GET /readyz` | 200 when every engine has a live process, else 503 (readiness) |
| `GET /v1/load` | This pod's `utilization` = (searching + queued) / engine processes; KEDA scales on it |

## Throughput

Each pod runs two Stockfish processes (one core each); requests beyond that queue. From
the start position, depth 18 with `multipv` 3 takes roughly 0.5 to 1 s on one core; time
grows quickly with depth and `multipv`. Batch callers should run about as many requests
in parallel as there are engine processes (2 per pod, up to 3 pods), and retry 503 and 504
with backoff.
