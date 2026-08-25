import { Link } from 'react-router-dom';

/** Persistent top bar across pages. */
export default function TopBar({ right }: { right?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-void/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-4 px-5">
        <Link to="/" className="group flex items-center gap-2.5">
          <span className="relative flex h-6 w-6 items-center justify-center">
            <span className="absolute inset-0 rounded-full border border-emergency/40" />
            <span className="h-2 w-2 rounded-full bg-emergency shadow-[0_0_12px_rgba(255,61,81,0.9)] group-hover:scale-125 transition-transform" />
          </span>
          <span className="font-display text-lg font-bold tracking-tight">
            FIRST<span className="text-emergency">BREATH</span>
          </span>
          <span className="hidden rounded border border-line px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest text-faint sm:block">
            golden hour net
          </span>
        </Link>
        <nav className="ml-auto flex items-center gap-1 font-mono text-xs">
          <Link
            to="/history"
            className="rounded px-3 py-1.5 text-muted transition-colors hover:bg-panel hover:text-ink"
          >
            history
          </Link>
          <Link
            to="/new"
            className="rounded bg-emergency/10 border border-emergency/40 px-3 py-1.5 text-emergency transition-all hover:bg-emergency/20 hover:shadow-[0_0_16px_-4px_rgba(255,61,81,0.6)]"
          >
            + emergency
          </Link>
        </nav>
        {right}
      </div>
    </header>
  );
}
