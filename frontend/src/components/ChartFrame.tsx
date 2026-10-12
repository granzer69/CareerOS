import type { ReactNode } from "react";

export function ChartFrame({
  title,
  definition,
  meta,
  children,
  table,
}: {
  title: string;
  definition: string;
  meta: string;
  children: ReactNode;
  table: ReactNode;
}) {
  return (
    <section className="card chart-frame">
      <header>
        <h2>{title}</h2>
        <p className="muted">{definition}</p>
        <p className="footnote">{meta}</p>
      </header>
      <div className="chart-visual">{children}</div>
      {table}
    </section>
  );
}
