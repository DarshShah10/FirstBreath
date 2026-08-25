import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtClock(minutes: number): string {
  const m = Math.max(0, minutes);
  const mm = Math.floor(m);
  const ss = Math.floor((m - mm) * 60);
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}
