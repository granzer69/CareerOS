export function KpiTile({
  label,
  value,
  note,
  nLabel,
}: {
  label: string;
  value: number | string;
  note: string;
  nLabel: string;
}) {
  return (
    <article className="card kpi-tile">
      <div className="muted">{label}</div>
      <strong className="score-value">{value}</strong>
      <p className="footnote">{note}</p>
      <p className="footnote">{nLabel}</p>
    </article>
  );
}
