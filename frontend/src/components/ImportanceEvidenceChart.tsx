import { ANALYTICS_COPY } from "../copy";
import type { ImportanceEvidenceBucket } from "../types";
import { ChartFrame } from "./ChartFrame";
import { StatusPill } from "./StatusPill";

const IMPORTANCE_ORDER = ["mandatory", "preferred", "contextual"] as const;

export function ImportanceEvidenceChart({
  buckets,
  requirementCount,
  rubricLabel,
}: {
  buckets: ImportanceEvidenceBucket[];
  requirementCount: number;
  rubricLabel: string;
}) {
  const grouped = IMPORTANCE_ORDER.map((importance) => ({
    importance,
    rows: buckets.filter((bucket) => bucket.importance === importance),
  }));

  return (
    <ChartFrame
      title="Evidence by JD importance"
      definition="Counts of requirement matches split by mandatory, preferred, and contextual importance."
      meta={`${rubricLabel} · n=${requirementCount} requirements · ${ANALYTICS_COPY.gaps}`}
      table={
        <table>
          <caption className="sr-only">Evidence counts by importance and state</caption>
          <thead>
            <tr>
              <th scope="col">Importance</th>
              <th scope="col">Evidence</th>
              <th scope="col">Count</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((bucket) => (
              <tr key={`${bucket.importance}-${bucket.state}`}>
                <td>{bucket.importance}</td>
                <td>
                  <StatusPill value={bucket.state} />
                </td>
                <td>{bucket.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {buckets.length === 0 ? (
        <p className="muted">No requirement matches yet.</p>
      ) : (
        <div className="importance-groups">
          {grouped.map((group) =>
            group.rows.length === 0 ? null : (
              <section key={group.importance}>
                <h3>{group.importance}</h3>
                <ul className="bar-chart">
                  {group.rows.map((row) => (
                    <li key={row.state}>
                      <span className="bar-label">
                        <StatusPill value={row.state} />
                      </span>
                      <span className="bar-track">
                        <span
                          className={`bar-fill ${row.state}`}
                          style={{
                            width: `${(row.count / Math.max(...group.rows.map((r) => r.count))) * 100}%`,
                          }}
                        />
                      </span>
                      <span className="bar-count">{row.count}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ),
          )}
        </div>
      )}
    </ChartFrame>
  );
}
