import * as React from "react";
import { cva } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-sm px-2 py-0.5 text-[10px] font-bold font-mono tracking-widest uppercase transition-colors",
  {
    variants: {
      variant: {
        default:     "bg-primary/15 text-primary border border-primary/30",
        secondary:   "bg-secondary text-secondary-foreground border border-border",
        destructive: "bg-risk-critical/15 text-risk-critical border border-risk-critical/30",
        outline:     "border border-border text-foreground",
        critical:    "bg-risk-critical/15 text-risk-critical border border-risk-critical/30",
        high:        "bg-risk-high/15 text-risk-high border border-risk-high/30",
        medium:      "bg-risk-medium/15 text-risk-medium border border-risk-medium/30",
        low:         "bg-risk-low/15 text-risk-low border border-risk-low/30",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

function Badge({ className, variant, ...props }) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
