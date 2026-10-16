import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { request } from "../api";
import { isSessionExpiredError } from "../authRedirect";
import { Banner } from "../components/Banner";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { HONESTY_COPY, STUDIO_COPY } from "../copy";
import type { ResumeAnalysisSummary } from "../types";

export function HistoryPage() {
  const [rows, setRows] = useState<ResumeAnalysisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    void request<ResumeAnalysisSummary[]>("/api/v1/resume/analyses")
      .then(setRows)
      .catch((err: unknown) => {
        if (isSessionExpiredError(err)) {
          setExpired(true);
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load history");
      });
  }, []);

  if (expired) {
    return <Navigate to="/login" replace />;
  }
  if (error) {
    return <Banner tone="error">{error}</Banner>;
  }
  if (!rows) {
    return <LoadingState label="Loading history…" />;
  }
  if (rows.length === 0) {
    return (
      <EmptyState title="History" action={<Link to="/">Go to analyze</Link>}>
        <p>{STUDIO_COPY.emptyHistory}</p>
      </EmptyState>
    );
  }

  return (
    <div className="card history-page">
      <header className="page-intro">
        <p className="eyebrow">Owner-scoped history</p>
        <h1>Your analyses</h1>
        <p className="muted">{HONESTY_COPY.historyReadiness}</p>
      </header>
      <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">File</th>
            <th scope="col">Role</th>
            <th scope="col">Readiness</th>
            <th scope="col">Grade</th>
            <th scope="col">When</th>
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
    </div>
  );
}
