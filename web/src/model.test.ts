import { describe, expect, it } from "vitest";
import type { Line } from "./api";
import { formatScore, lineArrows, numberMoves, positions, sanMoves, START_FEN, validFen, whitePercent } from "./model";

const line = (uci: string, cp: number): Line => ({
  rank: 1, uci, san: "", score: { cp, mate: null }, white_score: { cp, mate: null },
  depth: 10, seldepth: 12, nodes: 1000, pv: [uci], pv_san: [""],
});

describe("formatScore", () => {
  it("formats centipawns as pawns with a sign", () => {
    expect(formatScore({ cp: 31, mate: null })).toBe("+0.31");
    expect(formatScore({ cp: -120, mate: null })).toBe("-1.20");
    expect(formatScore({ cp: 0, mate: null })).toBe("0.00");
  });
  it("formats mates", () => {
    expect(formatScore({ cp: null, mate: 3 })).toBe("#3");
    expect(formatScore({ cp: null, mate: -2 })).toBe("-#2");
  });
});

describe("whitePercent", () => {
  it("is even at 0 and without a score", () => {
    expect(whitePercent({ cp: 0, mate: null })).toBe(50);
    expect(whitePercent(undefined)).toBe(50);
  });
  it("leans with the score and saturates", () => {
    expect(whitePercent({ cp: 300, mate: null })).toBeGreaterThan(75);
    expect(whitePercent({ cp: -300, mate: null })).toBeLessThan(25);
    expect(whitePercent({ cp: 5000, mate: null })).toBeLessThan(100);
    expect(whitePercent({ cp: null, mate: 4 })).toBe(100);
    expect(whitePercent({ cp: null, mate: -1 })).toBe(0);
  });
});

describe("numberMoves", () => {
  it("numbers a line from White's move", () => {
    const moves = numberMoves(START_FEN, ["e4", "e5", "Nf3"]);
    expect(moves.map((m) => m.number)).toEqual(["1.", null, "2."]);
  });
  it("starts with an ellipsis when Black is to move", () => {
    const fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3".replace(" w ", " b ");
    const moves = numberMoves(fen, ["Nf6", "Bc4"]);
    expect(moves.map((m) => m.number)).toEqual(["3...", "4."]);
  });
});

describe("lineArrows", () => {
  it("draws one arrow per distinct first move, the best first", () => {
    const arrows = lineArrows([line("e2e4", 30), line("d2d4", 25), line("e2e4", 20)], null);
    expect(arrows).toHaveLength(2);
    expect(arrows[0]).toMatchObject({ startSquare: "e2", endSquare: "e4" });
  });
  it("puts the highlighted line on top", () => {
    const arrows = lineArrows([line("e2e4", 30), line("d2d4", 25)], 1);
    expect(arrows[arrows.length - 1]).toMatchObject({ startSquare: "d2" });
  });
});

describe("games", () => {
  it("replays moves, including promotion", () => {
    const fen = "8/P7/8/8/8/8/k7/7K w - - 0 1";
    expect(sanMoves(fen, ["a7a8q"])).toEqual(["a8=Q+"]); // checks the king on a2
    expect(positions(fen, ["a7a8q"])[1].startsWith("Q7/")).toBe(true);
  });
  it("validates FENs", () => {
    expect(validFen(START_FEN)).toBeNull();
    expect(validFen("nonsense")).not.toBeNull();
  });
});
