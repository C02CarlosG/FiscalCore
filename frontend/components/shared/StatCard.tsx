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

export function StatCard({ label, value, icon: Icon, tone = "default", delta }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-4.5">
        <div className="mb-2.5 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground">{label}</span>
          <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${TONE_CLASSES[tone]}`}>
            <Icon className="h-3.5 w-3.5" />
          </span>
        </div>
        <p className="font-mono text-2xl font-semibold tracking-tight">{value}</p>
        {delta && (
          <p
            className={`mt-1.5 flex items-center gap-1 text-xs font-semibold ${
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
