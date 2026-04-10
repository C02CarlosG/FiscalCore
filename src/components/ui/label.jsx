import * as React from "react";
import { cn } from "../../lib/utils";

const Label = React.forwardRef(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("text-[10px] font-bold font-mono tracking-widest uppercase text-muted-foreground block mb-1.5", className)}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
