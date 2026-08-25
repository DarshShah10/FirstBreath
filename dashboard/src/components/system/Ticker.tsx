/** Infinite marquee strip — system truth in motion. */
export default function Ticker({
  items,
  tone = "text-faint",
  separator = "/",
}: {
  items: string[];
  tone?: string;
  separator?: string;
}) {
  const row = (
    <div className="flex shrink-0 items-center gap-8 pr-8">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-8 whitespace-nowrap">
          <span>{item}</span>
          <span className="text-red">{separator}</span>
        </span>
      ))}
    </div>
  );
  return (
    <div className={`flex overflow-hidden font-mono text-[10px] uppercase tracking-[0.22em] ${tone}`}>
      <div className="flex animate-marquee">
        {row}
        {row}
      </div>
    </div>
  );
}
