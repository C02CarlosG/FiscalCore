import { CalendarDays } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function PeriodFilter({
  id = "periodo",
  value,
  onChange,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex w-full items-end gap-4 rounded-md border bg-card p-4 sm:w-fit sm:min-w-64">
      <div className="min-w-0 flex-1 space-y-2">
        <Label htmlFor={id} className="text-xs font-semibold">Periodo (YYYY-MM)</Label>
        <Input
          id={id}
          type="month"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="min-w-40"
        />
      </div>
      <CalendarDays className="mb-2.5 h-4 w-4 flex-none text-muted-foreground" aria-hidden="true" />
    </div>
  );
}