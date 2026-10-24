import type { Analysis } from "../api";
import { formatProbability, formatScore, numberMoves } from "../model";

interface Props {
  fen: string;
  analysis: Analysis | null;
  loading: boolean;
  onHover: (index: number | null) => void;
  /** Play the first `count` moves of line `index`. */
  onPlay: (index: number, count: number) => void;
}

/** Half-moves of each variation to show; the rest are hidden to keep rows short. */
const SHOWN_PLIES = 12;

/** The engine's lines, best first: score (or, for Maia, how likely a human is to play the move),
 *  depth and the variation; click a move to play to it. */
export function Lines({ fen, analysis, loading, onHover, onPlay }: Props) {
  if (analysis?.outcome) {
    return <p className="px-3 py-4 text-sm text-strong capitalize">{analysis.outcome}.</p>;
  }
  if (!analysis) {
    return <p className="px-3 py-4 text-sm text-muted">{loading ? "Thinking…" : "No analysis yet."}</p>;
  }
  return (
    <ol className={`divide-y divide-line ${loading ? "opacity-60" : ""}`} aria-label="Engine lines">
      {analysis.lines.map((line, i) => (
        <li
          key={i}
          className="flex gap-2 px-3 py-2 text-sm hover:bg-raised"
          onMouseEnter={() => onHover(i)}
          onMouseLeave={() => onHover(null)}
        >
          <button
            className={`w-14 shrink-0 rounded px-1 text-left font-mono font-semibold ${
              i === 0 ? "text-book" : "text-strong"
            }`}
            title={`Play ${line.san}`}
            onClick={() => onPlay(i, 1)}
          >
            {line.probability !== null ? formatProbability(line.probability) : formatScore(line.white_score)}
          </button>
          <span className="min-w-0 flex-1 leading-6">
            {numberMoves(fen, line.pv_san.slice(0, SHOWN_PLIES)).map((m) => (
              <span key={m.index}>
                {m.number && <span className="text-muted">{m.number} </span>}
                <button
                  className={`rounded px-0.5 hover:bg-accent hover:text-white ${m.index === 0 ? "text-strong" : ""}`}
                  onClick={() => onPlay(i, m.index + 1)}
                >
                  {m.san}
                </button>{" "}
              </span>
            ))}
            {line.pv_san.length > SHOWN_PLIES && <span className="text-muted">…</span>}
          </span>
          {line.probability === null && (
            <span className="shrink-0 text-right text-xs leading-6 text-muted tabular-nums" title="depth/seldepth">
              d{line.depth}
              {line.seldepth ? `/${line.seldepth}` : ""}
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}
