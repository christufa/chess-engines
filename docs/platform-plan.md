# Going public: environments and security

chess-engines started as a private service inside the openings cluster. This is the plan
for running it as a public service with separate dev, UAT and prod environments.

## Decisions

| Question | Decision |
|---|---|
| Hosting | Its own lean AKS, built like lichess-delta-kube (bootstrap, platform, compute and gitops Terraform stacks; Argo CD; GitHub-hosted CI with OIDC). Public traffic, spot quota and blast radius stay apart from the openings and lichess clusters. |
| Environments | Two clusters. **Non-prod** holds `dev` and `uat` as namespaces; **prod** is on its own. Each environment has its own identities, Key Vault, Cloudflare app and deploy state. |
| Public access | Anonymous, with no sign-in. Cloudflare WAF, rate limits and Turnstile protect the analyse API, and anonymous requests get tight engine limits. Known clients, such as openings-research, use a token and get higher limits. |
| Engine CPU | The playground runs Stockfish (WebAssembly) in the browser for live analysis. The server handles deep or cached analysis and API clients, behind a position cache. |

## Target shape

```
            ┌──────────── Cloudflare ─────────────┐
 browsers ─▶│ WAF · rate limits · Turnstile        │── tunnel ─▶ prod cluster
 API clients│ static assets cached at the edge     │            chess-engines (public)
            └──────────────────────────────────────┘
 owner ────▶ Access (Microsoft sign-in) ── tunnel ─▶ non-prod cluster
                                                      ├─ dev  (every merge to main)
                                                      └─ uat  (promoted, load tests)

 images.yml ─▶ one ACR, signed digests ─▶ deploy-state: dev ─▶ uat ─▶ prod
                                                     (auto)  (auto after smoke) (approval)
```

No cluster has a public IP or load balancer. The only way in is the Cloudflare tunnel,
so the origin can't be reached around the WAF.

## Phases

Each phase lands as one or more PRs. Phases 1 and 2 cost nothing to run and can start
now; phase 3 is the first one that creates cloud resources.

### 1. Make the repository ready to be public

- **Licence.** Stockfish is GPL-3.0. The image already ships it, and serving
  `stockfish.wasm` to browsers distributes it too. Licensing this repository as GPL-3.0 is
  the simplest compatible choice; a permissive licence for our own code also works if the
  Stockfish files keep their own licence and source offer. (Your call; see the open
  questions.)
- `SECURITY.md` (how to report a vulnerability, using GitHub private vulnerability
  reporting), `CODEOWNERS`, and secret scanning with push protection.
- Pin every GitHub Action to a commit SHA; Dependabot keeps them current.
- OpenSSF Scorecard in CI, plus an SBOM and SLSA build provenance attached to each image
  next to the cosign signature.
- GitHub environments `dev`, `uat` and `prod`. The Azure OIDC credentials trust a subject
  per environment (`…:environment:prod`), not the branch, and `prod` needs your approval.

### 2. Make the app safe for anonymous traffic

- **Tiers.** `anonymous` gets small limits (for example depth ≤ 20, time ≤ 2 s, lines ≤ 3);
  `client` (a token) gets today's limits. The registry defines them per engine.
- **Turnstile.** The playground gets a Turnstile token; the server checks it with
  Cloudflare before running an anonymous server-side analysis. Token clients skip it.
- **Position cache.** Results are deterministic for a FEN, engine and limit, so they can
  be cached under that key (Redis in the cluster, with a TTL). Popular positions, mostly
  openings, never reach an engine twice.
- **Browser engine.** The playground runs single-threaded Stockfish WASM in a Web Worker
  for live analysis, and asks the server only for deeper or cached analysis. Multi-threaded
  WASM needs cross-origin isolation (COOP and COEP headers); add it later if it's worth it.
- **Hardening.** Request body size limits, strict input validation (already there for
  FENs and limits), no stack traces in responses, structured JSON logs without client IPs
  beyond what rate limiting needs, and a Prometheus `/metrics` endpoint that isn't routed
  through the tunnel.

### 3. Build the clusters

New Terraform stacks under `infra/` in this repository, with the same layout as
lichess-delta-kube. All deployment-specific values stay in gitignored tfvars.

- **bootstrap:** state storage and budget alerts per environment.
- **shared:** one ACR. Images are built once and promoted by digest, never rebuilt.
- **compute (per cluster):**
  - a small on-demand system pool and a spot engine pool;
  - Entra ID auth with local accounts disabled;
  - an API server limited to authorised IP ranges;
  - workload identity;
  - KEDA and Cilium.
- **gitops (per cluster):** Argo CD, the tunnel, DNS and Cloudflare configuration.
- **Admission:** only images from our ACR that carry a valid signature from `images.yml`
  run (Kyverno `verifyImages` or Ratify). Pods run with the restricted Pod Security
  Standard, and every namespace has default-deny network policies.
- **Egress:** engines need no internet. Egress is limited to DNS and the in-cluster cache.

### 4. Promotion

- `images.yml` publishes and signs, then writes `deploy-state/dev.yaml`.
- A smoke test runs against dev; if it passes, a workflow writes the same digest to
  `deploy-state/uat.yaml`.
- Promoting to prod is a manual workflow on the `prod` environment, so it needs your
  approval. It writes `deploy-state/prod.yaml` with a digest that has already run in uat.
- Rolling back is promoting the previous digest.

### 5. The edge

- **prod:** `chess-engines.generops.dev` (or a new domain) is public through the tunnel.
  - WAF managed rules and bot protection.
  - Rate limits on `/v1/analyse`: per IP for anonymous traffic, higher for clients with
    a token.
  - Static assets are cached at the edge.
- **dev and uat:** `chess-engines-dev` and `chess-engines-uat` are behind Access, with
  your Microsoft sign-in and service tokens for tests.

### 6. Operations

- **Monitoring:** metrics, logs and dashboards per cluster, with alerts on error rate,
  p99 latency, queue saturation and engine restarts.
- **Load tests:** k6 against uat in the stages from the stress-test plan. Each release
  candidate gets a short run before promotion.
- **Cost:** budget alerts per environment, with the spot engine pool's maximum size as the
  hard cost cap.
- **Runbooks:** incidents, key and token rotation, and rollback.

### 7. Cut over

1. openings-research calls prod chess-engines through Cloudflare with a client token.
2. Once evaluate-book and the research jobs have run against it, remove chess-engines from
   the openings cluster: its Argo CD app, network policy, Access app and tunnel route.

## Open questions

- **Licence:** GPL-3.0 for the whole repository, or a permissive licence for our own code?
- **Domain:** keep `chess-engines.generops.dev`, or use a new domain for the public service?
- **Prod availability:** AKS free tier (no uptime SLA) and one system node, or the
  Standard tier and two nodes across zones? The second roughly doubles prod's fixed cost.
- **Monthly budget:** a figure per environment, so the alerts and the engine pool's maximum
  size can be set to match.
