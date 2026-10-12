export function ScoreCard({
  label,
  value,
  note,
  rubricVersion,
}: {
  label: string;
  value: number | null | undefined;
  note: string;
  rubricVersion?: string | null;
}) {
  const display = value ?? "—";
  return (
    <article className="card score-card">
      <div className="muted">{label}</div>
      <strong className="score-value">{display}</strong>
      <p className="footnote">{note}</p>
      {rubricVersion ? <p className="footnote">Rubric {rubricVersion}</p> : null}
    </article>
  );
}
