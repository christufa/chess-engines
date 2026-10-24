# chess-engines

A shared chess-engine analysis service: UCI engines over a small synchronous HTTP API.
Projects send a position and get the engine's best lines back, ranked, with scores in
centipawns or mate, depth, nodes and the principal variation in UCI and SAN.

- **Engines:** Stockfish 19 to start, from a pluggable registry ([`engines/engines.yaml`](engines/engines.yaml)).
- **API:** [`docs/api.md`](docs/api.md), and the OpenAPI document [`docs/openapi.json`](docs/openapi.json).
- **Runs** as one shared instance in the openings cluster (AKS `aks-openings`, namespace
  `chess-engines`), wired up in
  [christufa/chess-openings-researcher](https://github.com/christufa/chess-openings-researcher)
  (`deploy/apps/chess-engines.yaml`).

```http
POST /v1/analyse
{"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "depth": 18, "multipv": 3}
```

## Playground

The service also serves a small UI at `/`: a board to analyse any position with the
registered engines.
- Choose the engine, a depth or move time, and up to 10 lines.
- The lines show as arrows and ranked variations with an eval bar. Click a move in a
  variation to play the line up to it.
- Play against the engine as either colour.
- Move through the game with the arrow keys (`f` flips the board).
- The position is kept in the URL (`#fen=…`), so a link opens the same position.

It calls the same `/v1` API as everyone else, so its limits and queue apply. In the openings
cluster it is at `https://chess-engines.generops.dev/`, behind a Microsoft sign-in for the
owner (other projects keep using service tokens). The source is in `web/` (React, Vite and
Tailwind, like the openings explorer); `docker/Dockerfile` typechecks, tests and builds it
into the image.

```powershell
cd web; npm ci; npm run dev   # http://127.0.0.1:5173, proxying /v1 to a service on :8000
```

## Calling it from another project

| From | URL | Authentication |
|---|---|---|
| A pod in the openings cluster, in an allowed namespace (`openings-research`, `argo`) | `http://chess-engines.chess-engines.svc.cluster.local` | None; the network policy admits only those namespaces |
| Anywhere else | `https://chess-engines.generops.dev` | A Cloudflare Access service token |

The public hostname is not open: Cloudflare Access refuses any request without a valid
service token, and cloudflared checks the Access token again before forwarding. Send the
token's ID and secret as headers:

```powershell
$headers = @{
  'CF-Access-Client-Id'     = $env:CHESS_ENGINES_CLIENT_ID
  'CF-Access-Client-Secret' = $env:CHESS_ENGINES_CLIENT_SECRET
}
$body = @{ fen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'; depth = 18; multipv = 3 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri https://chess-engines.generops.dev/v1/analyse `
  -Headers $headers -ContentType 'application/json' -Body $body
```

```python
import httpx

client = httpx.Client(
    base_url="https://chess-engines.generops.dev",
    headers={"CF-Access-Client-Id": client_id, "CF-Access-Client-Secret": client_secret},
    timeout=60,
)
lines = client.post("/v1/analyse", json={"fen": fen, "depth": 18, "multipv": 3}).raise_for_status().json()["lines"]
```

**Getting a token.** Service tokens are created by Terraform in the openings repository
(`infra/gitops/edge.tf`, variable `chess_engines_service_tokens`, default `shared`), which
also stores each one in the openings Key Vault as `chess-engines-<name>-client-id` and
`chess-engines-<name>-client-secret`. A project in another cluster copies them into its own
secret store (an External Secrets `ExternalSecret`, or a GitHub Actions secret). To give a
project its own token that can be revoked separately, add its name to that variable.

To check the deployment end to end, from inside the cluster and through Access:

```powershell
./scripts/check-deployment.ps1 -KeyVault <vault name>
```

**Batch callers** (for example, precomputing evaluations for an opening tree): run about as
many requests in parallel as there are engine processes (2 per pod, up to 3 pods), and
retry 503 and 504 with backoff. A depth-limited request is reproducible, so results can be
cached by `(fen, engine, version, depth, multipv)`.

## Layout

| Path | What |
|---|---|
| `src/chess_engines/` | FastAPI app (`app.py`), engine process pool and queue (`pool.py`), registry (`registry.py`) |
| `web/` | The playground UI, served at `/` |
| `engines/` | The registry baked into the image, and each engine's pinned, checksum-verified download |
| `docker/Dockerfile` | Digest-pinned base, non-root, runs on a read-only root filesystem |
| `chart/chess-engines/` | Helm chart: Deployment on the spot pool, KEDA ScaledObject, Cilium network policy |
| `.github/workflows/` | `ci.yml` (tests, against real Stockfish too), `containers.yml` (image smoke test, browser smoke of the playground and Trivy on PRs), `images.yml` (publish, sign and release from `main`), `security.yml` (CodeQL, dependency review) |

## How it works

Each pod runs `workers` processes per engine (2 for Stockfish, `Threads=1`, `Hash=64`).
A request takes a free process or waits in a bounded queue (`max_queue`, `queue_timeout_s`);
a full queue is a 503 with `Retry-After`. Every search has a hard deadline: its own limit
(`movetime_ms`, or `max_search_s` for depth searches) plus `hang_grace_s`. An engine that
misses it, or crashes, is killed and started again, and the request gets a 504.

KEDA polls `GET /v1/load` and adds pods (1 to 3) while the engines are busy and requests
queue. Pods run on the cluster's spot `batch` pool. The metrics-api trigger needs a pod to
poll, so the minimum is one pod, which keeps one spot node up; scaling to zero would need
the KEDA HTTP add-on in front of the Service.

## Adding a UCI engine

1. A stage in `docker/Dockerfile` that downloads a pinned release, verifies its checksum
   and installs it under `/opt/engines/<name>` (see `engines/stockfish/fetch.sh`). CPU-only
   engines only: the cluster has no GPUs, so Lc0 is out.
2. An entry in `engines/engines.yaml`: `name`, `path`, `version`, `workers`, UCI `options`
   and `limits`.
3. Tests for it next to `tests/test_stockfish.py`, run in CI against the real binary.

Clients choose it with `"engine": "<name>"`; `GET /v1/engines` lists what is registered.

## Development

```powershell
uv sync
uv run ruff check src tests scripts
uv run pytest            # Stockfish tests skip unless STOCKFISH_PATH is set
uv run python scripts/export_openapi.py   # after changing the API
docker build -f docker/Dockerfile -t chess-engines:dev .
docker run --rm --read-only --tmpfs /tmp -p 8000:8000 chess-engines:dev
```

The Stockfish tests need a Linux binary, so on Windows run them in a container, or let CI
run them. Every change goes through a pull request; `main` requires the Tests, containers,
CodeQL and dependency review checks.

## Releases

Every push to `main` runs `images.yml`: build, smoke test against real Stockfish, Trivy
(fail on fixable criticals), push to the openings cluster's registry with SBOM and
provenance, sign with cosign (keyless, identity `images.yml@refs/heads/main`) and verify.
The `release` job commits the digest to the `deploy-state` branch (`chess-engines.yaml`),
which Argo CD in the openings cluster reads, so the new build rolls out. To roll back,
`git revert` the commit on `deploy-state`.

Verify a published image:

```powershell
cosign verify <registry>/chess-engines@sha256:<digest> `
  --certificate-identity https://github.com/christufa/chess-engines/.github/workflows/images.yml@refs/heads/main `
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

## Security

Report vulnerabilities privately; see [SECURITY.md](SECURITY.md). CI runs CodeQL,
dependency review, Trivy and an OpenSSF Scorecard, and every action is pinned to a commit.

## Licence

The image contains Stockfish, which is GPL-3.0; its licence and the source reference are
in `/opt/engines/stockfish/` in the image (`COPYING`, `SOURCE`).
