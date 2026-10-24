// The service's own API (docs/api.md), called from the same origin.

export interface Score {
  cp: number | null;
  mate: number | null;
}

export interface Line {
  rank: number;
  uci: string;
  san: string;
  score: Score;
  white_score: Score;
  depth: number;
  seldepth: number | null;
  nodes: number | null;
  pv: string[];
  pv_san: string[];
  /** Lc0 engines such as Maia: how likely a player at that level is to play the move. */
  probability: number | null;
}

export interface Analysis {
  fen: string;
  turn: "white" | "black";
  engine: { name: string; version: string; id: string };
  limit: { depth: number | null; movetime_ms: number | null; nodes: number | null };
  multipv: number;
  outcome: "checkmate" | "stalemate" | null;
  lines: Line[];
  time_ms: number;
}

export type Search = "depth" | "movetime" | "nodes";

export interface Engine {
  name: string;
  title: string;
  version: string;
  id: string;
  default: boolean;
  workers: number;
  limits: {
    searches: Search[];
    default_search: "depth" | "nodes";
    default_depth: number;
    max_depth: number;
    max_movetime_ms: number;
    default_nodes: number;
    max_nodes: number;
    max_multipv: number;
  };
}

export interface AnalyseRequest {
  fen: string;
  engine: string;
  depth?: number;
  movetime_ms?: number;
  nodes?: number;
  multipv: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfter: number | null,
  ) {
    super(message);
  }
}

async function check(response: Response): Promise<Response> {
  if (response.ok) return response;
  let detail = response.statusText;
  try {
    const body = await response.json();
    detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    // not JSON (e.g. an Access or proxy page)
  }
  const retry = Number(response.headers.get("retry-after"));
  throw new ApiError(detail, response.status, Number.isFinite(retry) && retry > 0 ? retry : null);
}

export async function listEngines(): Promise<Engine[]> {
  const response = await check(await fetch("/v1/engines"));
  return (await response.json()).engines;
}

export async function analyse(request: AnalyseRequest, signal?: AbortSignal): Promise<Analysis> {
  const response = await check(
    await fetch("/v1/analyse", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
      signal,
    }),
  );
  return response.json();
}

/** Analyse, retrying a busy (503) or restarted (504) engine a few times as the API asks. */
export async function analyseWithRetry(request: AnalyseRequest, signal?: AbortSignal): Promise<Analysis> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await analyse(request, signal);
    } catch (e) {
      if (!(e instanceof ApiError) || ![503, 504].includes(e.status) || attempt >= 3) throw e;
      await new Promise((resolve) => setTimeout(resolve, (e.retryAfter ?? 2) * 1000));
      if (signal?.aborted) throw e;
    }
  }
}
