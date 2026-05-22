import { cn } from "../../lib/utils.js";

export function Input({ className, type, ...props }) {
  return (
    <input
      type={type}
      className={cn(
        "flex h-8 w-full rounded-sm border border-input bg-card px-3 text-[12px] text-foreground font-[inherit] tracking-normal outline-none placeholder:text-[var(--text-faint)] focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
