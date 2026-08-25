import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold",
  {
    variants: {
      tone: {
        neutral: "border-line bg-panel-2 text-muted",
        emergency: "border-emergency/50 bg-emergency/10 text-emergency",
        critical: "border-critical/50 bg-critical/10 text-critical",
        warn: "border-warn/50 bg-warn/10 text-warn",
        go: "border-go/50 bg-go/10 text-go",
        info: "border-info/50 bg-info/10 text-info",
        teal: "border-teal/50 bg-teal/10 text-teal",
        violet: "border-violet/50 bg-violet/10 text-violet",
      },
    },
    defaultVariants: { tone: "neutral" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export { Badge, badgeVariants };
