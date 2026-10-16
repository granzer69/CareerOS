import { ANALYTICS_COPY } from "../copy";
import type { AnalyticsRead } from "../types";
import { KpiTile } from "./KpiTile";

export function EditFunnelCard({ data, rubricLabel }: { data: AnalyticsRead; rubricLabel: string }) {
  const rate =
    data.edits.supported_rewrite_accept_rate === null
      ? "—"
      : `${Math.round(data.edits.supported_rewrite_accept_rate * 100)}%`;

  return (
    <section className="card">
      <h2>Edit funnel</h2>
      <p className="muted">{ANALYTICS_COPY.editFunnel}</p>
      <p className="footnote">{rubricLabel} · n={data.edits.total_edits} suggestions</p>
      <div className="scores">
        <KpiTile
          label="Supported rewrites"
          value={data.edits.supported_rewrite_generated}
          note="Generated supported_rewrite suggestions across filtered analyses."
          nLabel={`pending ${data.edits.pending}`}
        />
        <KpiTile
          label="Accepted"
          value={data.edits.supported_rewrite_accepted}
          note="Applied supported rewrites that became a new version."
          nLabel={`rejected ${data.edits.supported_rewrite_rejected}`}
        />
        <KpiTile
          label="Accept rate"
          value={rate}
          note="Accepted ÷ (accepted + rejected) for supported_rewrite only."
          nLabel="Not a hiring probability"
        />
      </div>
      {data.edit_kinds.length === 0 ? (
        <p className="muted">No edit suggestions yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">Kind</th>
              <th scope="col">Count</th>
            </tr>
          </thead>
          <tbody>
            {data.edit_kinds.map((row) => (
              <tr key={row.kind}>
                <td>{row.kind}</td>
                <td>{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
