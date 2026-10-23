import { useState } from "react";
import { numberMoves } from "../model";

interface Props {
  startFen: string;
  sans: string[];
  /** Number of moves played to reach the shown position. */
  cursor: number;
  fen: string;
  onJump: (cursor: number) => void;
  onLoadFen: (fen: string) => string | null;
}

const nav = "rounded bg-raised px-2.5 py-1 text-strong disabled:opacity-40";

/** The game so far (click a move to go there), navigation, and the FEN to copy or replace. */
export function MoveList({ startFen, sans, cursor, fen, onJump, onLoadFen }: Props) {
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="grid gap-2 px-3 py-3">
      <div className="flex flex-wrap gap-1.5" aria-label="Navigation">
        <button className={nav} onClick={() => onJump(0)} disabled={cursor === 0} aria-label="First move">
          «
        </button>
        <button className={nav} onClick={() => onJump(cursor - 1)} disabled={cursor === 0} aria-label="Previous move">
          ‹
        </button>
        <button className={nav} onClick={() => onJump(cursor + 1)} disabled={cursor >= sans.length} aria-label="Next move">
          ›
        </button>
        <button className={nav} onClick={() => onJump(sans.length)} disabled={cursor >= sans.length} aria-label="Last move">
          »
        </button>
      </div>

      <p className="min-h-6 text-sm leading-6" aria-label="Moves">
        {sans.length === 0 && <span className="text-muted">Make a move on the board, or click an engine move.</span>}
        {numberMoves(startFen, sans).map((m) => (
          <span key={m.index}>
            {m.number && <span className="text-muted">{m.number} </span>}
            <button
              className={`rounded px-0.5 ${m.index + 1 === cursor ? "bg-accent text-white" : "hover:bg-raised"}`}
              onClick={() => onJump(m.index + 1)}
            >
              {m.san}
            </button>{" "}
          </span>
        ))}
      </p>

      <form
        className="flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft === null) return;
          const problem = onLoadFen(draft);
          setError(problem);
          if (!problem) setDraft(null);
        }}
      >
        <input
          className="min-w-0 flex-1 rounded bg-raised px-2 py-1 font-mono text-xs text-strong outline-none focus:ring-2 focus:ring-accent"
          value={draft ?? fen}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="FEN"
          spellCheck={false}
        />
        <button type="submit" className={nav} disabled={draft === null}>
          Load
        </button>
        <button type="button" className={nav} onClick={() => navigator.clipboard?.writeText(fen)}>
          Copy
        </button>
      </form>
      {error && <p className="text-xs text-poor">{error}</p>}
    </div>
  );
}
