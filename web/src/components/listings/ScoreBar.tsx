import { cn } from "@/lib/utils";

interface ScoreBarProps {
  score: number | null | undefined;
  label: string;
}

export function ScoreBar({ score, label }: ScoreBarProps) {
  if (score == null) return null;

  const color =
    score >= 70
      ? "bg-green-500"
      : score >= 40
        ? "bg-orange-500"
        : "bg-red-500";

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-zinc-500 w-18 text-right shrink-0">
        {label}
      </span>
      <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full", color)}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs font-semibold text-zinc-400 w-7">
        {score}
      </span>
    </div>
  );
}
