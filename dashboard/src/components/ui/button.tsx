import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-info disabled:pointer-events-none disabled:opacity-40 cursor-pointer select-none active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-emergency text-white hover:bg-[#ff5566] glow-red font-semibold",
        secondary:
          "bg-panel-2 text-ink border border-line hover:border-line-bright hover:bg-[#16203200]",
        ghost: "text-muted hover:text-ink hover:bg-panel-2",
        outline:
          "border border-line bg-transparent text-ink hover:border-teal hover:text-teal",
        go: "bg-go/15 text-go border border-go/30 hover:bg-go/25 font-semibold",
        warn: "bg-warn/15 text-warn border border-warn/30 hover:bg-warn/25",
      },
      size: {
        default: "h-9 px-4",
        sm: "h-7 px-3 text-xs",
        lg: "h-11 px-6 text-base",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props}
    />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
