import * as React from "react";
import { cva } from "class-variance-authority";
import { cn } from "../../lib/utils.js";

const alertVariants = cva(
  "relative w-full rounded-lg border px-4 py-3 text-sm [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-3.5 [&>svg+div]:pl-6",
  {
    variants: {
      variant: {
        default:     "bg-secondary border-border text-foreground",
        destructive: "bg-risk-critical/10 border-risk-critical/30 text-risk-critical",
        success:     "bg-risk-low/10 border-risk-low/30 text-risk-low",
        warning:     "bg-risk-medium/10 border-risk-medium/30 text-risk-medium",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

const Alert = React.forwardRef(({ className, variant, ...props }, ref) => (
  <div ref={ref} role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
));
Alert.displayName = "Alert";

const AlertDescription = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("text-sm font-sans", className)} {...props} />
));
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertDescription };
