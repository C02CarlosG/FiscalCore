import { cn } from "../../lib/utils.js";

export function Table({ className, ...props }) {
  return <table className={cn("w-full border-collapse text-[12px]", className)} {...props} />;
}

export function TableHeader({ className, ...props }) {
  return <thead className={className} {...props} />;
}

export function TableBody({ className, ...props }) {
  return <tbody className={className} {...props} />;
}

export function TableFooter({ className, ...props }) {
  return <tfoot className={cn("bg-muted font-semibold", className)} {...props} />;
}

export function TableRow({ className, ...props }) {
  return <tr className={cn("border-b border-border hover:[&>td]:bg-muted/50", className)} {...props} />;
}

export function TableHead({ className, ...props }) {
  return (
    <th
      className={cn(
        "h-8 px-3 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider bg-muted sticky top-0 z-10 first:rounded-tl-sm last:rounded-tr-sm",
        className
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }) {
  return <td className={cn("h-8 px-3", className)} {...props} />;
}
