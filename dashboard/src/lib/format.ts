/** Formatting utilities — all system data speaks mono + tabular. */

export function fmtClock(minutes: number): string {
  const m = Math.max(0, minutes);
  const mm = Math.floor(m);
  const ss = Math.floor((m - mm) * 60);
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

export function fmtTPlus(minutes: number): string {
  return `T+${fmtClock(minutes)}`;
}

export function fmtCoord(n: number): string {
  return n.toFixed(4);
}

export function titleCase(s?: string | null): string {
  if (!s) return "";
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
