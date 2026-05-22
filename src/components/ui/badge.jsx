import { cva } from "class-variance-authority";
import { cn } from "../../lib/utils.js";

const badgeVariants = cva(
  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border whitespace-nowrap",
  {
    variants: {
      variant: {
        default:     "bg-muted text-muted-foreground border-border",
        success:     "bg-[var(--accent-bg)] text-primary border-[var(--accent-border)]",
        danger:      "bg-[var(--danger-bg)] text-destructive border-[var(--danger-border)]",
        warn:        "bg-[var(--warn-bg)] text-[var(--warn)] border-transparent",
        info:        "bg-[var(--info-bg)] text-[var(--info)] border-transparent",
        outline:     "border-border bg-transparent text-foreground",
        dot:         "bg-muted text-muted-foreground border-border",
        secondary:   "bg-secondary text-secondary-foreground border-border",
        destructive: "bg-destructive/20 text-destructive border border-destructive/30",
        critical:    "bg-[var(--danger-bg)] text-destructive border-[var(--danger-border)]",
        high:        "bg-[var(--warn-bg)] text-[var(--warn)] border-transparent",
        medium:      "bg-[var(--info-bg)] text-[var(--info)] border-transparent",
        low:         "bg-muted text-muted-foreground border-border",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export function Badge({ className, variant, dot, children, ...props }) {
  return (
    <span
      className={cn(
        badgeVariants({ variant }),
        dot && "before:content-[''] before:w-1.5 before:h-1.5 before:rounded-full before:bg-current",
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export { badgeVariants };
