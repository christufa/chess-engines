import { Chess } from "chess.js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type Analysis, type AnalyseRequest, ApiError, analyseWithRetry, type Engine, listEngines } from "./api";
import { Board } from "./components/Board";
import { Controls, type Settings } from "./components/Controls";
import { EvalBar } from "./components/EvalBar";
import { Lines } from "./components/Lines";
import { MoveList } from "./components/MoveList";
import { lineArrows, positions, sanMoves, searchFor, START_FEN, validFen } from "./model";

function initialFen(): string {
  const fen = new URLSearchParams(location.hash.slice(1)).get("fen");
  return fen && validFen(fen) === null ? fen : START_FEN;
}

function requestFor(fen: string, engine: string, engines: Engine[], s: Settings, multipv: number): AnalyseRequest {
  const spec = engines.find((e) => e.name === engine);
  return {
    fen,
    engine,
    multipv: spec ? Math.min(multipv, spec.limits.max_multipv) : multipv,
    ...searchFor(spec, s),
  };
}

const keyOf = (r: AnalyseRequest) => JSON.stringify(r);

export default function App() {
  const [engines, setEngines] = useState<Engine[]>([]);
  const [settings, setSettings] = useState<Settings>({
    engine: "stockfish", limit: "depth", depth: 18, movetimeMs: 1000, multipv: 3,
    auto: true, engineSide: null, opponent: "stockfish", promotion: "q",
  });
  const [startFen, setStartFen] = useState(initialFen);
  const [moves, setMoves] = useState<string[]>([]);
  const [cursor, setCursor] = useState(0);
  const [orientation, setOrientation] = useState<"white" | "black">("white");
  const [hover, setHover] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cache = useRef(new Map<string, Analysis>());
  const inflight = useRef<AbortController | null>(null);

  const fens = useMemo(() => positions(startFen, moves), [startFen, moves]);
  const sans = useMemo(() => sanMoves(startFen, moves), [startFen, moves]);
  const fen = fens[cursor];
  const turn = fen.split(" ")[1] === "w" ? "white" : "black";
  const gameOver = useMemo(() => new Chess(fen).isGameOver(), [fen]);
  const engineToMove = settings.engineSide === turn && !gameOver;

  useEffect(() => {
    listEngines()
      .then((list) => {
        setEngines(list);
        const engine = list.find((e) => e.default) ?? list[0];
        // A human-like opponent where there is one: Maia at a middling level.
        const opponent = list.find((e) => e.name === "maia-1500") ?? engine;
        if (engine) {
          setSettings((s) => ({
            ...s, engine: engine.name, opponent: opponent.name, depth: Math.min(s.depth, engine.limits.max_depth),
          }));
        }
      })
      .catch((e) => setError(`Couldn't list engines: ${e instanceof Error ? e.message : e}`));
  }, []);

  // The position is in the URL, so it can be shared; a pasted or edited link loads its FEN.
  // (replaceState doesn't fire hashchange, so this only reacts to the user.)
  useEffect(() => {
    history.replaceState(null, "", `#fen=${encodeURIComponent(fen)}`);
  }, [fen]);
  useEffect(() => {
    const onHash = () => {
      setStartFen(initialFen());
      setMoves([]);
      setCursor(0);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const play = useCallback(
    (ucis: string[]) => {
      setMoves((prev) => {
        // Following the game already recorded keeps the rest of it (like a takeback and replay).
        const ahead = prev.slice(cursor, cursor + ucis.length);
        return ahead.length === ucis.length && ahead.every((m, i) => m === ucis[i])
          ? prev
          : [...prev.slice(0, cursor), ...ucis];
      });
      setCursor((c) => c + ucis.length);
      setHover(null);
    },
    [cursor],
  );

  const run = useCallback(
    (request: AnalyseRequest, then?: (a: Analysis) => void) => {
      inflight.current?.abort();
      const cached = cache.current.get(keyOf(request));
      if (cached) {
        setAnalysis(cached);
        setBusy(false);
        then?.(cached);
        return;
      }
      const controller = new AbortController();
      inflight.current = controller;
      setBusy(true);
      setError(null);
      analyseWithRetry(request, controller.signal)
        .then((result) => {
          if (controller.signal.aborted) return;
          cache.current.set(keyOf(request), result);
          setAnalysis(result);
          then?.(result);
        })
        .catch((e) => {
          if (controller.signal.aborted) return;
          setError(e instanceof ApiError ? `${e.status}: ${e.message}` : String(e));
        })
        .finally(() => {
          if (inflight.current === controller) setBusy(false);
        });
    },
    [],
  );

  // The engine's move when it is its turn; otherwise analyse the position if asked to.
  useEffect(() => {
    if (engineToMove) {
      const timer = setTimeout(
        () => run(requestFor(fen, settings.opponent, engines, settings, 1),
          (a) => a.fen === fen && a.lines[0] && play([a.lines[0].uci])),
        300,
      );
      return () => clearTimeout(timer);
    }
    if (!settings.auto) return;
    const timer = setTimeout(() => run(requestFor(fen, settings.engine, engines, settings, settings.multipv)), 250);
    return () => clearTimeout(timer);
  }, [fen, settings, engines, engineToMove, run, play]);

  // Keyboard: arrows walk the game, f flips the board.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.key === "ArrowLeft") setCursor((c) => Math.max(0, c - 1));
      else if (e.key === "ArrowRight") setCursor((c) => Math.min(moves.length, c + 1));
      else if (e.key === "f") setOrientation((o) => (o === "white" ? "black" : "white"));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [moves.length]);

  const current = analysis && analysis.fen.split(" ").slice(0, 4).join(" ") === fen.split(" ").slice(0, 4).join(" ")
    ? analysis
    : null;
  const shown = current ?? (busy ? analysis : null);
  const lastMove = cursor > 0 ? moves[cursor - 1] : null;
  const titleOf = (name: string) => engines.find((e) => e.name === name)?.title ?? name;
  // Maia's lines carry move probabilities; its score is a rough value head, not an evaluation.
  const evaluated = current?.lines[0] && current.lines[0].probability === null ? current.lines[0] : undefined;

  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col gap-4 p-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-lg font-semibold text-strong">Engine playground</h1>
        <nav className="flex gap-4 text-sm text-muted">
          {current && (
            <span className="tabular-nums">
              {titleOf(current.engine.name)} · {current.time_ms} ms
            </span>
          )}
          <a className="hover:text-strong" href="/docs">
            API
          </a>
        </nav>
      </header>

      <main className="grid gap-4 md:grid-cols-[minmax(0,1fr)_380px]">
        <section className="min-w-0">
          <div className="flex gap-2">
            <EvalBar score={evaluated?.white_score} orientation={orientation} />
            <div className="min-w-0 flex-1">
              <Board
                fen={fen}
                orientation={orientation}
                arrows={current ? lineArrows(current.lines, hover) : []}
                lastMove={lastMove}
                promotion={settings.promotion}
                disabled={engineToMove || (settings.engineSide !== null && busy)}
                onMove={(uci) => play([uci])}
              />
            </div>
          </div>
          <div className="ml-8 mt-2 flex flex-wrap gap-2 text-sm">
            <button
              className="rounded bg-raised px-2.5 py-1 text-strong"
              onClick={() => setOrientation((o) => (o === "white" ? "black" : "white"))}
            >
              Flip board
            </button>
            <button
              className="rounded bg-raised px-2.5 py-1 text-strong"
              onClick={() => {
                setStartFen(START_FEN);
                setMoves([]);
                setCursor(0);
              }}
            >
              New game
            </button>
            <span className="self-center text-muted">
              {gameOver ? "Game over" : engineToMove ? "Engine to move…" : `${turn === "white" ? "White" : "Black"} to move`}
            </span>
          </div>
        </section>

        <aside className="flex min-w-0 flex-col divide-y divide-line overflow-hidden rounded bg-panel">
          <Controls
            engines={engines}
            settings={settings}
            onChange={setSettings}
            onAnalyse={() => run(requestFor(fen, settings.engine, engines, settings, settings.multipv))}
            busy={busy}
          />
          {error && (
            <p className="px-3 py-2 text-sm text-poor" role="alert">
              {error}
            </p>
          )}
          {/* On phones the lines come first, right under the board. */}
          <div className="max-md:order-first">
            <Lines
              fen={fen}
              analysis={shown}
              loading={busy}
              onHover={setHover}
              onPlay={(i, count) => current && play(current.lines[i].pv.slice(0, count))}
            />
          </div>
          <MoveList
            startFen={startFen}
            sans={sans}
            cursor={cursor}
            fen={fen}
            onJump={(c) => setCursor(Math.max(0, Math.min(moves.length, c)))}
            onLoadFen={(text) => {
              const problem = validFen(text);
              if (problem) return problem;
              setStartFen(new Chess(text.trim()).fen());
              setMoves([]);
              setCursor(0);
              return null;
            }}
          />
        </aside>
      </main>
    </div>
  );
}
