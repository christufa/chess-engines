import type { Engine } from "../api";

export interface Settings {
  /** The engine that analyses. */
  engine: string;
  limit: "depth" | "movetime";
  depth: number;
  movetimeMs: number;
  multipv: number;
  auto: boolean;
  /** Which side the opponent plays, or null for analysis only. */
  engineSide: "white" | "black" | null;
  /** The engine that plays that side, e.g. a Maia level, while `engine` analyses. */
  opponent: string;
  promotion: "q" | "r" | "b" | "n";
}

interface Props {
  engines: Engine[];
  settings: Settings;
  onChange: (settings: Settings) => void;
  onAnalyse: () => void;
  busy: boolean;
}

const label = "flex items-center justify-between gap-3 text-sm";
const input = "rounded bg-raised px-2 py-1 text-strong outline-none focus:ring-2 focus:ring-accent";

/** Engine, search limit, number of lines, auto-analysis and play-against-the-engine. */
export function Controls({ engines, settings, onChange, onAnalyse, busy }: Props) {
  const engine = engines.find((e) => e.name === settings.engine);
  const limits = engine?.limits;
  const set = <K extends keyof Settings>(key: K, value: Settings[K]) => onChange({ ...settings, [key]: value });
  // Depth and time, where the engine takes them; Maia plays from one node and takes neither.
  const kinds = (["depth", "movetime"] as const).filter((k) => !limits || limits.searches.includes(k));
  const limit = kinds.includes(settings.limit) ? settings.limit : kinds[0];

  return (
    <div className="grid gap-2.5 px-3 py-3" aria-label="Engine settings">
      <label className={label}>
        Engine
        <select
          className={input}
          value={settings.engine}
          onChange={(e) => set("engine", e.target.value)}
          aria-label="Engine"
        >
          {engines.map((e) => (
            <option key={e.name} value={e.name}>
              {e.title}
            </option>
          ))}
        </select>
      </label>

      {kinds.length === 0 && (
        <p className="text-xs text-muted">
          {engine?.title} predicts the move a human at its level plays, from one node: no search to set. Lines
          show how likely each move is.
        </p>
      )}

      {kinds.length > 0 && (
        <div className={label}>
          <span>Search</span>
          <div className="flex overflow-hidden rounded bg-raised text-xs" role="radiogroup" aria-label="Search limit">
            {kinds.map((kind) => (
              <button
                key={kind}
                role="radio"
                aria-checked={limit === kind}
                className={`px-2.5 py-1 ${limit === kind ? "bg-accent text-white" : "text-text"}`}
                onClick={() => set("limit", kind)}
              >
                {kind === "depth" ? "Depth" : "Time"}
              </button>
            ))}
          </div>
        </div>
      )}

      {limit === "depth" && (
        <label className={label}>
          <span>
            Depth <span className="tabular-nums text-strong">{settings.depth}</span>
          </span>
          <input
            type="range"
            min={1}
            max={limits?.max_depth ?? 30}
            value={settings.depth}
            onChange={(e) => set("depth", Number(e.target.value))}
            className="w-40 accent-accent"
            aria-label="Depth"
          />
        </label>
      )}
      {limit === "movetime" && (
        <label className={label}>
          <span>
            Time <span className="tabular-nums text-strong">{(settings.movetimeMs / 1000).toFixed(1)} s</span>
          </span>
          <input
            type="range"
            min={100}
            max={limits?.max_movetime_ms ?? 10000}
            step={100}
            value={settings.movetimeMs}
            onChange={(e) => set("movetimeMs", Number(e.target.value))}
            className="w-40 accent-accent"
            aria-label="Move time"
          />
        </label>
      )}

      <label className={label}>
        <span>
          Lines <span className="tabular-nums text-strong">{settings.multipv}</span>
        </span>
        <input
          type="range"
          min={1}
          max={limits?.max_multipv ?? 10}
          value={settings.multipv}
          onChange={(e) => set("multipv", Number(e.target.value))}
          className="w-40 accent-accent"
          aria-label="Lines"
        />
      </label>

      <label className={label}>
        Play against the engine
        <select
          className={input}
          value={settings.engineSide ?? "off"}
          aria-label="Play against the engine"
          onChange={(e) => set("engineSide", e.target.value === "off" ? null : (e.target.value as "white" | "black"))}
        >
          <option value="off">Off (analysis)</option>
          <option value="black">Engine plays Black</option>
          <option value="white">Engine plays White</option>
        </select>
      </label>

      {settings.engineSide !== null && (
        <label className={label}>
          Opponent
          <select
            className={input}
            value={settings.opponent}
            onChange={(e) => set("opponent", e.target.value)}
            aria-label="Opponent"
          >
            {engines.map((e) => (
              <option key={e.name} value={e.name}>
                {e.title}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className={label}>
        Promote to
        <select
          className={input}
          value={settings.promotion}
          onChange={(e) => set("promotion", e.target.value as Settings["promotion"])}
        >
          <option value="q">Queen</option>
          <option value="r">Rook</option>
          <option value="b">Bishop</option>
          <option value="n">Knight</option>
        </select>
      </label>

      <div className="flex items-center justify-between gap-3 pt-1">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={settings.auto} onChange={(e) => set("auto", e.target.checked)} />
          Analyse every position
        </label>
        <button
          className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          onClick={onAnalyse}
          disabled={busy}
        >
          {busy ? "Thinking…" : "Analyse"}
        </button>
      </div>
    </div>
  );
}
