import { cn } from "@/lib/utils";
import * as React from "react";

function Separator({ className, vertical }: { className?: string; vertical?: boolean }) {
  return (
    <div
      role="separator"
      className={cn("bg-line", vertical ? "w-px self-stretch" : "h-px w-full", className)}
    />
  );
}

/** Big monospace numeric readout with label — the ops-console signature. */
function StatBlock({
  label,
  value,
  sub,
  tone = "text-ink",
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-faint">{label}</span>
      <span className={cn("font-mono text-xl font-semibold tabular-nums leading-none", tone)}>
        {value}
      </span>
      {sub && <span className="text-[10px] text-faint font-mono">{sub}</span>}
    </div>
  );
}

/** Pulsing live dot */
function LiveDot({ tone = "bg-go", label = "LIVE" }: { tone?: string; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-muted">
      <span className="relative flex h-2 w-2">
        <span className={cn("absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping", tone)} />
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", tone)} />
      </span>
      {label}
    </span>
  );
}

export { Separator, StatBlock, LiveDot };
