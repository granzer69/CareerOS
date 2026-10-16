import { Link } from "react-router-dom";
import { ANALYTICS_COPY } from "../copy";
import type { VersionDelta } from "../types";

export function VersionLiftTable({
  rows,
  rubricLabel,
}: {
  rows: VersionDelta[];
  rubricLabel: string;
}) {
  return (
    <section className="card">
      <h2>Version lift</h2>
      <p className="muted">{ANALYTICS_COPY.versionLift}</p>
      <p className="footnote">{rubricLabel} · n={rows.length} analyses with versions</p>
      {rows.length === 0 ? (
        <p className="muted">No accepted versions yet. Accept a supported rewrite to compare readiness.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">File</th>
              <th scope="col">Role</th>
              <th scope="col">Original</th>
              <th scope="col">Latest v</th>
              <th scope="col">Δ readiness</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.analysis_id}>
                <td>
                  <Link to={`/analyses/${row.analysis_id}`}>{row.file_name}</Link>
                </td>
                <td>{row.target_role}</td>
                <td>{row.original_readiness ?? "—"}</td>
                <td>
                  {row.latest_version_readiness ?? "—"}
                  {row.latest_version_number !== null ? ` (v${row.latest_version_number})` : ""}
                </td>
                <td>{row.delta ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
