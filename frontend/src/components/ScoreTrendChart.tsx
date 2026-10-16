import { Link } from "react-router-dom";
import { ANALYTICS_COPY } from "../copy";
import type { ScorePoint } from "../types";
import { ChartFrame } from "./ChartFrame";

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function ScoreTrendChart({
  points,
  rubricLabel,
}: {
  points: ScorePoint[];
  rubricLabel: string;
}) {
  const plotted = points.filter((point) => point.application_readiness_score !== null);
  const width = 640;
  const height = 220;
  const pad = { top: 16, right: 16, bottom: 36, left: 36 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const xs = plotted.map((_, i) =>
    plotted.length === 1 ? pad.left + innerW / 2 : pad.left + (i * innerW) / (plotted.length - 1),
  );
  const ys = plotted.map((point) => {
    const score = point.application_readiness_score ?? 0;
    return pad.top + innerH - (score / 100) * innerH;
  });
  const polyline = xs.map((x, i) => `${x},${ys[i]}`).join(" ");
  const omitted = points.length - plotted.length;

  return (
    <ChartFrame
      title="Application-readiness over time"
      definition={ANALYTICS_COPY.trend}
      meta={`${rubricLabel} · n=${points.length} analyses${omitted ? ` · ${omitted} omitted (null score)` : ""}`}
      table={
        <table>
          <caption className="sr-only">Application-readiness by analysis</caption>
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">File</th>
              <th scope="col">Role</th>
              <th scope="col">Readiness</th>
              <th scope="col">Job-fit</th>
              <th scope="col">Alignment</th>
              <th scope="col">Blocked</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.id}>
                <td>{formatWhen(point.created_at)}</td>
                <td>
                  <Link to={`/analyses/${point.id}`}>{point.file_name}</Link>
                </td>
                <td>{point.target_role}</td>
                <td>{point.application_readiness_score ?? "—"}</td>
                <td>{point.job_fit_score ?? "—"}</td>
                <td>{point.resume_alignment_score ?? "—"}</td>
                <td>{point.blocked_by_requirement ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {plotted.length === 0 ? (
        <p className="muted">
          No rubric readiness scores to plot. Null scores are omitted, not drawn as zero.
        </p>
      ) : (
        <svg
          className="trend-svg"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Application-readiness trend for ${plotted.length} analyses, ${rubricLabel}`}
        >
          <line className="chart-axis" x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + innerH} />
          <line
            className="chart-axis"
            x1={pad.left}
            y1={pad.top + innerH}
            x2={pad.left + innerW}
            y2={pad.top + innerH}
          />
          <text className="chart-tick" x={4} y={pad.top + 4}>
            100
          </text>
          <text className="chart-tick" x={8} y={pad.top + innerH}>
            0
          </text>
          <polyline className="chart-line" fill="none" points={polyline} />
          {plotted.map((point, i) => (
            <g key={point.id}>
              <circle
                className={point.blocked_by_requirement ? "chart-point blocked" : "chart-point"}
                cx={xs[i]}
                cy={ys[i]}
                r={5}
              />
              {point.blocked_by_requirement ? (
                <text className="chart-tick" x={xs[i] - 4} y={ys[i] - 10}>
                  B
                </text>
              ) : null}
            </g>
          ))}
        </svg>
      )}
    </ChartFrame>
  );
}
