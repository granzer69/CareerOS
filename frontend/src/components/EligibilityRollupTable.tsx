import { ANALYTICS_COPY } from "../copy";
import type { EligibilityRollup } from "../types";
import { ChartFrame } from "./ChartFrame";

export function EligibilityRollupTable({
  rows,
  analysisCount,
  rubricLabel,
}: {
  rows: EligibilityRollup[];
  analysisCount: number;
  rubricLabel: string;
}) {
  return (
    <ChartFrame
      title="Eligibility constraints"
      definition="Stated eligibility items from your analyses, grouped by constraint text and rubric status."
      meta={`${rubricLabel} · n=${analysisCount} analyses · ${ANALYTICS_COPY.eligibility}`}
      table={
        <table>
          <caption className="sr-only">Eligibility status counts by constraint text</caption>
          <thead>
            <tr>
              <th scope="col">Constraint</th>
              <th scope="col">Met</th>
              <th scope="col">Not met</th>
              <th scope="col">Unknown</th>
              <th scope="col">N/A</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.text}>
                <td>{row.text}</td>
                <td>{row.confirmed_met}</td>
                <td>{row.confirmed_not_met}</td>
                <td>{row.unknown}</td>
                <td>{row.not_applicable}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {rows.length === 0 ? (
        <p className="muted">No eligibility rows on analyses in this view.</p>
      ) : (
        <p className="footnote">
          Rows count eligibility entries across analyses. A single posting can contribute one row per
          constraint.
        </p>
      )}
    </ChartFrame>
  );
}
