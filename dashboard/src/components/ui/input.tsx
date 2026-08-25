import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-md border border-line bg-abyss px-3 py-1 text-sm text-ink placeholder:text-faint focus-visible:outline-none focus-visible:border-info/60 transition-colors disabled:opacity-40",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn("text-[11px] font-mono uppercase tracking-[0.14em] text-muted", className)}
      {...props}
    />
  )
);
Label.displayName = "Label";

export { Input, Label };
