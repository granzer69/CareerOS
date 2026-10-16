import { Link } from "react-router-dom";
import { SCORE_COPY } from "../copy";
import type { ScorePoint } from "../types";
import { ChartFrame } from "./ChartFrame";

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function TerminologyTrendChart({
  points,
  rubricLabel,
}: {
  points: ScorePoint[];
  rubricLabel: string;
}) {
  const plotted = points.filter((point) => point.ats_score !== null && point.ats_score !== undefined);
  const width = 640;
  const height = 200;
  const pad = { top: 16, right: 16, bottom: 36, left: 36 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const polyline = plotted
    .map((point, index) => {
      const x =
        plotted.length === 1
          ? pad.left + innerW / 2
          : pad.left + (index * innerW) / (plotted.length - 1);
      const y = pad.top + innerH - ((point.ats_score ?? 0) / 100) * innerH;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <ChartFrame
      title="Terminology coverage over time"
      definition={SCORE_COPY.terminology}
      meta={`${rubricLabel} · n=${plotted.length} plotted · ${points.length - plotted.length} omitted (null)`}
      table={
        <table>
          <caption className="sr-only">Terminology coverage by analysis</caption>
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">File</th>
              <th scope="col">Coverage</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.id}>
                <td>{formatWhen(point.created_at)}</td>
                <td>
                  <Link to={`/analyses/${point.id}`}>{point.file_name}</Link>
                </td>
                <td>{point.ats_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {plotted.length === 0 ? (
        <p className="muted">No terminology coverage scores to plot.</p>
      ) : (
        <svg
          className="trend-svg"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Terminology coverage trend, ${plotted.length} analyses`}
        >
          <line className="chart-axis" x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + innerH} />
          <line
            className="chart-axis"
            x1={pad.left}
            y1={pad.top + innerH}
            x2={pad.left + innerW}
            y2={pad.top + innerH}
          />
          <polyline className="chart-line alignment" fill="none" points={polyline} />
        </svg>
      )}
    </ChartFrame>
  );
}
