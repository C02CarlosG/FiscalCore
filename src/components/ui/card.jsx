import { cn } from "../../lib/utils.js";

export function Card({ className, ...props }) {
  return <div className={cn("bg-card border border-border rounded-md shadow-2xs", className)} {...props} />;
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("flex items-center gap-3 px-4 py-3 border-b border-border", className)} {...props} />;
}

export function CardContent({ className, ...props }) {
  return <div className={cn("p-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }) {
  return <h3 className={cn("text-[13px] font-semibold tracking-tight", className)} {...props} />;
}

export function CardFooter({ className, ...props }) {
  return <div className={cn("px-4 py-3 border-t border-border flex items-center gap-2", className)} {...props} />;
}

export function CardDescription({ className, ...props }) {
  return <p className={cn("text-xs text-muted-foreground", className)} {...props} />;
}
