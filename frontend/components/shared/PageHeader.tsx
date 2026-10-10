import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col justify-between gap-4 border-b border-border pb-6 sm:flex-row sm:items-end">
      <div className="min-w-0">
        <p className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-primary">
          <span
            aria-hidden="true"
            className="h-3.5 w-1 rounded-full bg-gradient-to-b from-primary to-[hsl(var(--brand-contrast))]"
          />
          {eyebrow}
        </p>
        <h1 className="font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
      {actions && <div className="flex flex-none items-center gap-2">{actions}</div>}
    </div>
  );
}