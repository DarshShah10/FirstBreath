import * as React from "react";
import { cn } from "@/lib/utils";

const Panel = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { glow?: boolean }
>(({ className, glow, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border border-line bg-panel/80 backdrop-blur-sm relative overflow-hidden",
      glow && "shadow-[0_0_40px_-18px_rgba(77,163,255,0.35)]",
      className
    )}
    {...props}
  />
));
Panel.displayName = "Panel";

const PanelHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex items-center gap-2 border-b border-line px-4 py-2.5 text-[11px] font-mono uppercase tracking-[0.18em] text-muted",
      className
    )}
    {...props}
  />
));
PanelHeader.displayName = "PanelHeader";

const PanelTitle = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("text-ink font-sans font-semibold text-sm tracking-normal normal-case", className)} {...props} />
));
PanelTitle.displayName = "PanelTitle";

const PanelContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-4", className)} {...props} />
));
PanelContent.displayName = "PanelContent";

export { Panel, PanelHeader, PanelTitle, PanelContent };
