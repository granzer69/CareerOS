import { ANALYTICS_COPY } from "../copy";
import type { RoleCoverageRow } from "../types";

export function RoleCoverageMatrix({
  rows,
  rubricLabel,
}: {
  rows: RoleCoverageRow[];
  rubricLabel: string;
}) {
  const roles = [...new Set(rows.map((row) => row.target_role))];

  return (
    <section className="card">
      <h2>Coverage matrix by role</h2>
      <p className="muted">{ANALYTICS_COPY.heatmap}</p>
      <p className="footnote">{rubricLabel} · top requirements per role</p>
      {rows.length === 0 ? (
        <p className="muted">No requirement rows to matrix yet.</p>
      ) : (
        roles.map((role) => {
          const roleRows = rows.filter((row) => row.target_role === role);
          return (
            <div key={role} className="matrix-role-block">
              <h3>{role}</h3>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Requirement</th>
                    <th scope="col">Confirmed</th>
                    <th scope="col">Partial</th>
                    <th scope="col">Not found</th>
                    <th scope="col">Contradicted</th>
                    <th scope="col">Unknown</th>
                  </tr>
                </thead>
                <tbody>
                  {roleRows.map((row) => (
                    <tr key={`${row.target_role}-${row.requirement_text}`}>
                      <td>{row.requirement_text}</td>
                      <td>{row.confirmed}</td>
                      <td>{row.partial}</td>
                      <td>{row.not_found}</td>
                      <td>{row.contradicted}</td>
                      <td>{row.unknown}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })
      )}
    </section>
  );
}
