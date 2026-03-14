import { cn } from "@/lib/utils";

const BUDGET_CONFIG: Record<string, { label: string; color: string }> = {
  tier1k: { label: "\u22641k", color: "bg-green-500" },
  tier1_1k: { label: "1-1.1k", color: "bg-lime-500" },
  tier1_2k: { label: "1.1-1.2k", color: "bg-yellow-500" },
  tier1_3k: { label: "1.2-1.3k", color: "bg-orange-500" },
  tier1_3k_plus: { label: ">1.3k", color: "bg-red-500" },
};

interface BudgetChipProps {
  status: string | null;
  totalCost: number | null;
  price: number | null;
}

export function BudgetChip({ status, totalCost, price }: BudgetChipProps) {
  const config = BUDGET_CONFIG[status || ""];

  if (config && totalCost != null) {
    return (
      <span
        className={cn(
          "text-sm font-bold text-white px-3 py-1 rounded-full",
          config.color
        )}
      >
        {"€"}{Math.round(totalCost).toLocaleString()}/mo
      </span>
    );
  }

  if (price != null) {
    return (
      <span className="text-sm font-bold text-white px-3 py-1 rounded-full bg-zinc-600">
        {"€"}{price.toLocaleString()} + ?
      </span>
    );
  }

  return null;
}
