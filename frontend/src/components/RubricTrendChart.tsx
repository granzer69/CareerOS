import { Link } from "react-router-dom";
import { ANALYTICS_COPY } from "../copy";
import type { ScorePoint } from "../types";
import { ChartFrame } from "./ChartFrame";

type SeriesKey = "readiness" | "fit" | "alignment";

const SERIES: { key: SeriesKey; label: string; dash: string; className: string }[] = [
  { key: "readiness", label: "Readiness", dash: "", className: "chart-line readiness" },
  { key: "fit", label: "Job-fit", dash: "6 4", className: "chart-line fit" },
  { key: "alignment", label: "Alignment", dash: "2 4", className: "chart-line alignment" },
];

function scoreFor(point: ScorePoint, key: SeriesKey): number | null {
  if (key === "readiness") {
    return point.application_readiness_score;
  }
  if (key === "fit") {
    return point.job_fit_score;
  }
  return point.resume_alignment_score;
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function RubricTrendChart({
  points,
  rubricLabel,
}: {
  points: ScorePoint[];
  rubricLabel: string;
}) {
  const width = 640;
  const height = 240;
  const pad = { top: 16, right: 16, bottom: 36, left: 36 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const hasAny = SERIES.some((series) =>
    points.some((point) => scoreFor(point, series.key) !== null),
  );

  function xAt(index: number, count: number): number {
    if (count <= 1) {
      return pad.left + innerW / 2;
    }
    return pad.left + (index * innerW) / (count - 1);
  }

  function yAt(score: number): number {
    return pad.top + innerH - (score / 100) * innerH;
  }

  return (
    <ChartFrame
      title="Rubric scores over time"
      definition={ANALYTICS_COPY.fitAlignment}
      meta={`${rubricLabel} · n=${points.length} analyses`}
      table={
        <table>
          <caption className="sr-only">Rubric scores by analysis</caption>
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">File</th>
              <th scope="col">Readiness</th>
              <th scope="col">Job-fit</th>
              <th scope="col">Alignment</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.id}>
                <td>{formatWhen(point.created_at)}</td>
                <td>
                  <Link to={`/analyses/${point.id}`}>{point.file_name}</Link>
                </td>
                <td>{point.application_readiness_score ?? "—"}</td>
                <td>{point.job_fit_score ?? "—"}</td>
                <td>{point.resume_alignment_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {!hasAny ? (
        <p className="muted">No rubric scores to plot yet.</p>
      ) : (
        <>
          <ul className="chart-legend" aria-label="Rubric series legend">
            {SERIES.map((series) => (
              <li key={series.key}>
                <span className={`legend-swatch ${series.key}`} aria-hidden="true" />
                {series.label}
              </li>
            ))}
          </ul>
          <svg
            className="trend-svg"
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label={`Rubric trends for ${points.length} analyses`}
          >
            <line className="chart-axis" x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + innerH} />
            <line
              className="chart-axis"
              x1={pad.left}
              y1={pad.top + innerH}
              x2={pad.left + innerW}
              y2={pad.top + innerH}
            />
            {SERIES.map((series) => {
              const plotted = points
                .map((point, index) => ({ point, index, score: scoreFor(point, series.key) }))
                .filter((item) => item.score !== null);
              const polyline = plotted
                .map((item) => `${xAt(item.index, points.length)},${yAt(item.score as number)}`)
                .join(" ");
              return (
                <polyline
                  key={series.key}
                  className={series.className}
                  fill="none"
                  strokeDasharray={series.dash}
                  points={polyline}
                />
              );
            })}
          </svg>
        </>
      )}
    </ChartFrame>
  );
}
