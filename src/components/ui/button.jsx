import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "../../lib/utils.js";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-sm text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-45 cursor-pointer font-[inherit]",
  {
    variants: {
      variant: {
        default:   "bg-card text-foreground border border-border shadow-2xs hover:bg-muted",
        primary:   "bg-primary text-primary-foreground border border-primary shadow-xs hover:brightness-108",
        ghost:     "border-transparent bg-transparent shadow-none hover:bg-muted",
        danger:    "text-destructive border border-[var(--danger-border)] bg-[var(--danger-bg)]",
        outline:   "border border-border bg-background hover:bg-muted",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "bg-destructive/20 text-destructive border border-destructive/30 hover:bg-destructive/30",
        link:      "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-[30px] px-3",
        sm:      "h-6 px-2 text-[11px]",
        lg:      "h-[38px] px-4 text-[13px]",
        icon:    "h-[30px] w-[30px]",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export function Button({ className, variant, size, asChild = false, ...props }) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
