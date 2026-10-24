// Pure helpers for the playground: formatting scores, the eval bar, and turning engine
// lines into move text and board arrows. No React here, so it is unit-tested directly.
import { Chess } from "chess.js";
import type { AnalyseRequest, Engine, Line, Score } from "./api";

export const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/** "+0.31", "-1.20", "0.00", "#3" (White mates in 3), "-#2" (Black mates in 2). */
export function formatScore(score: Score): string {
  if (score.mate !== null) return score.mate > 0 ? `#${score.mate}` : `-#${-score.mate}`;
  const pawns = (score.cp ?? 0) / 100;
  if (pawns === 0) return "0.00";
  return (pawns > 0 ? "+" : "") + pawns.toFixed(2);
}

/** "18%", "0.4%", "<0.1%": how likely a human is to play a move (Maia). */
export function formatProbability(p: number): string {
  const percent = p * 100;
  if (percent >= 9.95) return `${Math.round(percent)}%`;
  if (percent >= 0.1) return `${percent.toFixed(1)}%`;
  return "<0.1%";
}

/** The search part of a request: the chosen depth or time where the engine accepts it,
 *  clamped to its bounds; nothing (the engine's own default, e.g. Maia's one node) where
 *  it doesn't. */
export function searchFor(
  engine: Engine | undefined,
  choice: { limit: "depth" | "movetime"; depth: number; movetimeMs: number },
): Pick<AnalyseRequest, "depth" | "movetime_ms"> {
  const limits = engine?.limits;
  if (!limits) return choice.limit === "depth" ? { depth: choice.depth } : { movetime_ms: choice.movetimeMs };
  if (choice.limit === "depth" && limits.searches.includes("depth")) {
    return { depth: Math.min(choice.depth, limits.max_depth) };
  }
  if (choice.limit === "movetime" && limits.searches.includes("movetime")) {
    return { movetime_ms: Math.min(choice.movetimeMs, limits.max_movetime_ms) };
  }
  return {};
}

/** White's share of the eval bar, 0-100. Mates fill it; centipawns follow lichess's curve. */
export function whitePercent(score: Score | undefined): number {
  if (!score) return 50;
  if (score.mate !== null) return score.mate > 0 ? 100 : 0;
  const cp = Math.max(-1000, Math.min(1000, score.cp ?? 0));
  const winningChance = 2 / (1 + Math.exp(-0.00368208 * cp)) - 1; // -1..1
  return 50 + 50 * winningChance;
}

export interface PvMove {
  san: string;
  /** e.g. "12." before a White move, "12..." before a line that starts with Black. */
  number: string | null;
  /** Index into the line's moves: play pv[0..=index] to reach this move. */
  index: number;
}

/** Number a variation: "1. e4 e5 2. Nf3", or "3... Nc6 4. Bb5" when Black is to move. */
export function numberMoves(fen: string, sans: string[]): PvMove[] {
  const parts = fen.split(" ");
  let white = parts[1] !== "b";
  let moveNo = Number(parts[5]) || 1;
  return sans.map((san, index) => {
    const number = white ? `${moveNo}.` : index === 0 ? `${moveNo}...` : null;
    if (!white) moveNo += 1;
    white = !white;
    return { san, number, index };
  });
}

export interface Arrow {
  startSquare: string;
  endSquare: string;
  color: string;
}

/** One arrow per line's first move: the best line solid, the rest fainter; a highlighted
 *  line (hovered in the list) stands out. */
export function lineArrows(lines: Line[], highlight: number | null): Arrow[] {
  const seen = new Set<string>();
  const arrows: Arrow[] = [];
  let top: Arrow | null = null;
  lines.forEach((line, i) => {
    const key = line.uci.slice(0, 4);
    if (seen.has(key)) return;
    seen.add(key);
    const arrow = {
      startSquare: line.uci.slice(0, 2),
      endSquare: line.uci.slice(2, 4),
      color: i === 0 ? "rgba(76, 175, 125, 0.9)" : `rgba(160, 160, 160, ${Math.max(0.25, 0.6 - i * 0.08)})`,
    };
    if (highlight === i) top = { ...arrow, color: "rgba(54, 146, 231, 0.95)" };
    else arrows.push(arrow);
  });
  // The highlighted arrow last, so it draws on top.
  return top ? [...arrows, top] : arrows;
}

/** Check a FEN locally before asking the engine (the server validates again). */
export function validFen(fen: string): string | null {
  try {
    new Chess(fen.trim());
    return null;
  } catch (e) {
    return e instanceof Error ? e.message : "invalid FEN";
  }
}

/** Positions along a game: index 0 is the start, index i is after moves[0..i). */
export function positions(startFen: string, moves: string[]): string[] {
  const game = new Chess(startFen);
  const fens = [game.fen()];
  for (const uci of moves) {
    game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] });
    fens.push(game.fen());
  }
  return fens;
}

/** SAN for each move of a game, for the move list. */
export function sanMoves(startFen: string, moves: string[]): string[] {
  const game = new Chess(startFen);
  return moves.map((uci) => game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san);
}
