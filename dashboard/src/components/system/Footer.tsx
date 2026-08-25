export default function Footer() {
  return (
    <footer className="border-t border-line bg-void">
      <div className="mx-auto max-w-[1600px] px-6 py-14 md:px-14">
        <div className="flex flex-col justify-between gap-10 md:flex-row md:items-end">
          <div>
            <div className="flex items-center gap-3">
              <span className="h-2 w-2 rounded-full bg-red" />
              <span className="font-display text-2xl font-bold tracking-tight">
                FIRSTBREATH
              </span>
            </div>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-faint">
              A multi-agent simulation of the emergency response chain —
              built for the hour when everything is decided.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-x-16 gap-y-2 font-mono text-[11px] uppercase tracking-[0.18em] text-mute">
            <a href="/new" className="hover:text-bone">declare</a>
            <a href="/history" className="hover:text-bone">archive</a>
            <a href="https://github.com/DarshShah10/FirstBreath" target="_blank" rel="noreferrer" className="hover:text-bone">
              github
            </a>
            <span className="text-faint">v2.0 · langgraph</span>
          </div>
        </div>

        <div className="mt-12 flex flex-col justify-between gap-3 border-t border-line pt-6 font-mono text-[9px] uppercase tracking-[0.25em] text-faint md:flex-row">
          <span>28.6139°N · 77.2090°E — Sector 12, Noida, UP</span>
          <span>golden hour clock always running</span>
          <span>© {new Date().getFullYear()} firstbreath</span>
        </div>
      </div>
    </footer>
  );
}
