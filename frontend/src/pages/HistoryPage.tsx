import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { request } from "../api";
import type { ResumeAnalysisSummary } from "../types";

export function HistoryPage() {
  const [rows, setRows] = useState<ResumeAnalysisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void request<ResumeAnalysisSummary[]>("/api/v1/resume/analyses")
      .then(setRows)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load history");
      });
  }, []);

  if (error) {
    return <div className="banner error">{error}</div>;
  }
  if (!rows) {
    return <p className="muted">Loading history…</p>;
  }
  if (rows.length === 0) {
    return (
      <div className="card">
        <h1>History</h1>
        <p>No analyses yet. Run an analysis with a resume and a job description.</p>
        <Link to="/">Go to analyze</Link>
      </div>
    );
  }

  return (
    <div className="card">
      <h1>Your analyses</h1>
      <p className="muted">Overall score is application-readiness, not a hiring probability.</p>
      <table>
        <thead>
          <tr>
            <th>File</th>
            <th>Role</th>
            <th>Readiness</th>
            <th>Grade</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <Link to={`/analyses/${row.id}`}>{row.file_name}</Link>
              </td>
              <td>{row.target_role}</td>
              <td>{row.overall_score}</td>
              <td>{row.grade}</td>
              <td>{new Date(row.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
