import { Chess, type Square } from "chess.js";
import { useMemo, useState } from "react";
import { Chessboard } from "react-chessboard";
import type { Arrow } from "../model";

interface Props {
  fen: string;
  orientation: "white" | "black";
  arrows: Arrow[];
  lastMove: string | null;
  promotion: "q" | "r" | "b" | "n";
  disabled: boolean;
  onMove: (uci: string) => void;
}

/** The board: drag or click to move (legal moves only), engine arrows, last move shown. */
export function Board({ fen, orientation, arrows, lastMove, promotion, disabled, onMove }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const game = useMemo(() => new Chess(fen), [fen]);

  const tryMove = (from: string, to: string): boolean => {
    const candidates = game.moves({ square: from as Square, verbose: true }).filter((m) => m.to === to);
    if (candidates.length === 0) return false;
    const move = candidates.find((m) => !m.promotion || m.promotion === promotion) ?? candidates[0];
    onMove(move.from + move.to + (move.promotion ?? ""));
    setSelected(null);
    return true;
  };

  const squareStyles: Record<string, React.CSSProperties> = {};
  if (lastMove) {
    for (const sq of [lastMove.slice(0, 2), lastMove.slice(2, 4)]) {
      squareStyles[sq] = { backgroundColor: "rgba(155, 199, 0, 0.41)" };
    }
  }
  if (selected) {
    squareStyles[selected] = { backgroundColor: "rgba(20, 85, 30, 0.5)" };
    for (const m of game.moves({ square: selected as Square, verbose: true })) {
      squareStyles[m.to] = {
        ...squareStyles[m.to],
        background: m.captured
          ? "radial-gradient(transparent 0%, transparent 79%, rgba(20, 85, 0, 0.3) 80%)"
          : "radial-gradient(rgba(20, 85, 30, 0.5) 19%, transparent 20%)",
      };
    }
  }

  return (
    <div className="w-full aspect-square" aria-label="Board">
      <Chessboard
        options={{
          id: "playground",
          position: fen,
          boardOrientation: orientation,
          arrows,
          allowDrawingArrows: true,
          clearArrowsOnPositionChange: true,
          allowDragging: !disabled,
          squareStyles,
          darkSquareStyle: { backgroundColor: "#b58863" },
          lightSquareStyle: { backgroundColor: "#f0d9b5" },
          animationDurationInMs: 160,
          onPieceDrop: ({ sourceSquare, targetSquare }) =>
            !disabled && targetSquare !== null && tryMove(sourceSquare, targetSquare),
          onSquareClick: ({ square, piece }) => {
            if (disabled) return;
            if (selected && selected !== square && tryMove(selected, square)) return;
            const own = piece && (piece.pieceType[0] === "w") === (game.turn() === "w");
            setSelected(own && selected !== square ? square : null);
          },
        }}
      />
    </div>
  );
}
