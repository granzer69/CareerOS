import { ANALYTICS_COPY } from "../copy";
import type { EvidenceBucket } from "../types";
import { ChartFrame } from "./ChartFrame";

const STATE_MARK: Record<string, string> = {
  confirmed: "●",
  partial: "◐",
  not_found: "○",
  contradicted: "×",
  unknown: "?",
};

export function EvidenceMixChart({
  buckets,
  requirementCount,
  rubricLabel,
}: {
  buckets: EvidenceBucket[];
  requirementCount: number;
  rubricLabel: string;
}) {
  const max = Math.max(1, ...buckets.map((bucket) => bucket.count));

  return (
    <ChartFrame
      title="Evidence mix"
      definition={ANALYTICS_COPY.evidence}
      meta={`${rubricLabel} · n=${requirementCount} requirements`}
      table={
        <table>
          <caption className="sr-only">Requirement matches by evidence state</caption>
          <thead>
            <tr>
              <th scope="col">Evidence state</th>
              <th scope="col">Count</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((bucket) => (
              <tr key={bucket.state}>
                <td>{bucket.state}</td>
                <td>{bucket.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {requirementCount === 0 ? (
        <p className="muted">No requirement matches yet.</p>
      ) : (
        <ul className="bar-chart" aria-label={`Evidence counts, ${rubricLabel}, n=${requirementCount}`}>
          {buckets.map((bucket) => (
            <li key={bucket.state}>
              <span className="bar-label">
                <span aria-hidden="true">{STATE_MARK[bucket.state] ?? "·"} </span>
                {bucket.state.replaceAll("_", " ")}
              </span>
              <span className="bar-track">
                <span
                  className={`bar-fill ${bucket.state}`}
                  style={{ width: `${(bucket.count / max) * 100}%` }}
                />
              </span>
              <span className="bar-count">{bucket.count}</span>
            </li>
          ))}
        </ul>
      )}
    </ChartFrame>
  );
}
