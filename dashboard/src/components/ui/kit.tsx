import { cn } from "@/lib/cn";

/* ── Button ─────────────────────────────────────────────────────────── */
export function Button({
  children,
  variant = "solid",
  className,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "solid" | "outline" | "ghost";
}) {
  return (
    <button
      className={cn(
        "group relative inline-flex items-center gap-3 overflow-hidden px-7 py-4 font-mono text-[11px] uppercase tracking-[0.22em] transition-colors duration-300",
        variant === "solid" && "bg-red text-white",
        variant === "outline" &&
          "border border-line2 bg-transparent text-bone hover:border-bone",
        variant === "ghost" && "text-mute hover:text-bone",
        className
      )}
      data-cursor="link"
      {...rest}
    >
      {variant === "solid" && (
        <span className="absolute inset-0 -translate-x-full bg-bone transition-transform duration-400 ease-out group-hover:translate-x-0" />
      )}
      <span
        className={cn(
          "relative z-10 flex items-center gap-3",
          variant === "solid" && "transition-colors duration-300 group-hover:text-red"
        )}
      >
        {children}
      </span>
    </button>
  );
}

/* ── Stamp — status badge, mono, squared ────────────────────────────── */
const TONES: Record<string, string> = {
  neutral: "border-line2 text-mute",
  red: "border-red/60 text-red",
  amber: "border-amber/60 text-amber",
  green: "border-green/60 text-green",
};

export function Stamp({
  tone = "neutral",
  children,
  className,
}: {
  tone?: keyof typeof TONES;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.2em]",
        TONES[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

/* ── Readout — label over a mono value, the ops signature ───────────── */
export function Readout({
  label,
  value,
  sub,
  tone,
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="font-mono text-[9px] uppercase tracking-[0.25em] text-faint">{label}</span>
      <span className={cn("font-mono text-xl font-medium tnum leading-none", tone ?? "text-bone")}>
        {value}
      </span>
      {sub && <span className="font-mono text-[9px] tracking-wide text-faint">{sub}</span>}
    </div>
  );
}

/* ── SectionHead — editorial kicker + rule ──────────────────────────── */
export function Kicker({ index, label }: { index: string; label: string }) {
  return (
    <div className="flex items-center gap-4">
      <span className="font-mono text-[10px] tracking-[0.3em] text-red">{index}</span>
      <span className="h-px w-10 bg-line2" />
      <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-mute">{label}</span>
    </div>
  );
}
