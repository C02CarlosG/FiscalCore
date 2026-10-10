import type { LucideIcon } from "lucide-react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export type StatCardProps = {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: "default" | "critico" | "alto" | "ok";
  delta?: { value: string; direction: "up" | "down"; label: string };
};

const TONE_CLASSES: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "bg-severity-bajo-soft text-severity-bajo",
  critico: "bg-severity-critico-soft text-severity-critico",
  alto: "bg-severity-alto-soft text-severity-alto",
  ok: "bg-status-ok-soft text-status-ok",
};

const TONE_ACCENT: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "from-severity-bajo",
  critico: "from-severity-critico",
  alto: "from-severity-alto",
  ok: "from-status-ok",
};

export function StatCard({ label, value, icon: Icon, tone = "default", delta }: StatCardProps) {
  return (
    <Card className="relative min-w-0 overflow-hidden transition-shadow hover:shadow-md">
      <span
        aria-hidden="true"
        className={`absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r to-transparent ${TONE_ACCENT[tone]}`}
      />
      <CardContent className="p-4 sm:p-5">
        <div className="mb-4 flex items-start justify-between gap-3">
          <span className="text-xs font-semibold text-muted-foreground">{label}</span>
          <span className={`flex h-9 w-9 flex-none items-center justify-center rounded-md ${TONE_CLASSES[tone]}`}>
            <Icon className="h-4 w-4" />
          </span>
        </div>
        <p className="truncate font-mono text-xl font-semibold tabular-nums text-foreground sm:text-2xl">{value}</p>
        {delta && (
          <p
            className={`mt-2 flex flex-wrap items-center gap-1 text-xs font-semibold ${
              delta.direction === "up" ? "text-status-ok" : "text-status-error"
            }`}
          >
            {delta.direction === "up" ? (
              <ArrowUp className="h-3 w-3" />
            ) : (
              <ArrowDown className="h-3 w-3" />
            )}
            {delta.value}
            <span className="font-normal text-muted-foreground">{delta.label}</span>
          </p>
        )}
      </CardContent>
    </Card>
  );
}
