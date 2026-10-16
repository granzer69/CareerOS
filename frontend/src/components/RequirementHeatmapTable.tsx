import { ANALYTICS_COPY } from "../copy";
import type { RequirementHeatCell } from "../types";
import { StatusPill } from "./StatusPill";

export function RequirementHeatmapTable({
  cells,
  rubricLabel,
}: {
  cells: RequirementHeatCell[];
  rubricLabel: string;
}) {
  return (
    <section className="card">
      <h2>Requirement coverage</h2>
      <p className="muted">{ANALYTICS_COPY.heatmap}</p>
      <p className="footnote">{rubricLabel} · top {cells.length} cells</p>
      {cells.length === 0 ? (
        <p className="muted">No requirement matches to summarize.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">Requirement</th>
              <th scope="col">Role</th>
              <th scope="col">Evidence</th>
              <th scope="col">Count</th>
            </tr>
          </thead>
          <tbody>
            {cells.map((cell) => (
              <tr key={`${cell.requirement_text}-${cell.target_role}-${cell.evidence_state}`}>
                <td>{cell.requirement_text}</td>
                <td>{cell.target_role}</td>
                <td>
                  <StatusPill value={cell.evidence_state} />
                </td>
                <td>{cell.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
