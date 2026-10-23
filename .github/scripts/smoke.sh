#!/usr/bin/env bash
# Run the image as the cluster does and analyse the starting position with real Stockfish.
# Used by containers.yml (PRs) and images.yml (main, before publishing).   smoke.sh <image>
set -euo pipefail
image=${1:?usage: smoke.sh <image>}
docker run -d --rm --name chess-engines-smoke --read-only --tmpfs /tmp:rw,size=64m \
  --cap-drop ALL --security-opt no-new-privileges --user 10001:10001 --memory 1g --cpus 2 \
  -p 127.0.0.1:8000:8000 "$image" > /dev/null
trap 'docker logs chess-engines-smoke 2>&1 | tail -20; docker stop chess-engines-smoke > /dev/null' EXIT

for _ in $(seq 30); do curl -fsS 127.0.0.1:8000/readyz > /dev/null 2>&1 && break; sleep 1; done
curl -fsS 127.0.0.1:8000/readyz
curl -fsS 127.0.0.1:8000/openapi.json > /dev/null
curl -fsS 127.0.0.1:8000/v1/engines | jq -e '.engines[0].id | startswith("Stockfish")'

body=$(curl -fsS -X POST 127.0.0.1:8000/v1/analyse -H 'content-type: application/json' \
  -d '{"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "depth": 14, "multipv": 3}')
echo "$body" | jq -c '.lines[] | {rank, san, score, depth}'
echo "$body" | jq -e '(.lines | length) == 3 and .lines[0].depth >= 14 and
  ([.lines[].score.cp] as $s | $s == ($s | sort | reverse))' > /dev/null

# Mate in one, Black to move.
curl -fsS -X POST 127.0.0.1:8000/v1/analyse -H 'content-type: application/json' \
  -d '{"fen": "3r2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1", "depth": 8}' \
  | jq -e '.lines[0].san == "Rd1#" and .lines[0].score.mate == 1 and .lines[0].white_score.mate == -1'

# A bad FEN is a 422, not a 500.
test "$(curl -s -o /dev/null -w '%{http_code}' -X POST 127.0.0.1:8000/v1/analyse \
  -H 'content-type: application/json' -d '{"fen": "nope"}')" = 422
echo "smoke test passed"
