import type { Score } from "../api";
import { formatScore, whitePercent } from "../model";

/** Vertical bar: White's share from the bottom (or top when the board is flipped). */
export function EvalBar({ score, orientation }: { score: Score | undefined; orientation: "white" | "black" }) {
  const white = whitePercent(score);
  const label = score ? formatScore(score) : "–";
  return (
    <div
      className="relative w-6 shrink-0 self-stretch overflow-hidden rounded-sm bg-[#403d39]"
      role="meter"
      aria-label="Evaluation"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(white)}
      aria-valuetext={label}
      title={label}
    >
      <div
        className="absolute inset-x-0 bg-[#f0f0f0] transition-[height] duration-300"
        style={{ height: `${white}%`, [orientation === "white" ? "bottom" : "top"]: 0 }}
      />
      <span
        className={`absolute inset-x-0 text-center text-[10px] font-semibold ${
          white >= 50 ? "text-[#403d39]" : "text-[#f0f0f0]"
        } ${(white >= 50) === (orientation === "white") ? "bottom-1" : "top-1"}`}
      >
        {label.replace(/^\+/, "")}
      </span>
    </div>
  );
}
