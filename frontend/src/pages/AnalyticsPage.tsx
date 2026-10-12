import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { request } from "../api";
import { isSessionExpiredError } from "../authRedirect";
import { Banner } from "../components/Banner";
import { EmptyState } from "../components/EmptyState";
import { EvidenceMixChart } from "../components/EvidenceMixChart";
import { KpiTile } from "../components/KpiTile";
import { LoadingState } from "../components/LoadingState";
import { ScoreTrendChart } from "../components/ScoreTrendChart";
import { ANALYTICS_COPY, HONESTY_COPY, STUDIO_COPY } from "../copy";
import type { AnalyticsRead } from "../types";

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    void request<AnalyticsRead>("/api/v1/resume/analytics")
      .then(setData)
      .catch((err: unknown) => {
        if (isSessionExpiredError(err)) {
          setExpired(true);
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load analytics");
      });
  }, []);

  if (expired) {
    return <Navigate to="/login" replace />;
  }
  if (error) {
    return <Banner tone="error">{error}</Banner>;
  }
  if (!data) {
    return <LoadingState label="Loading analytics…" />;
  }
  if (data.analysis_count === 0) {
    return (
      <EmptyState title="Your evidence, over time" action={<Link to="/">Go to analyze</Link>}>
        <p>{STUDIO_COPY.emptyAnalytics}</p>
      </EmptyState>
    );
  }

  const rubricLabel =
    data.rubric_versions.length > 0
      ? `rubric ${data.rubric_versions.join(", ")}`
      : "rubric unknown";
  const latest = data.latest_created_at
    ? new Date(data.latest_created_at).toLocaleString()
    : "—";

  return (
    <div className="grid analytics-page">
      <header className="page-intro">
        <p className="eyebrow">Owner-scoped · last 100 analyses</p>
        <h1>Your evidence, over time</h1>
        <p className="muted">{HONESTY_COPY.analyticsScope}</p>
        <p className="footnote">Latest analysis {latest} · {rubricLabel}</p>
      </header>

      <div className="scores">
        <KpiTile
          label="Analyses"
          value={data.analysis_count}
          note={ANALYTICS_COPY.analyses}
          nLabel={`n=${data.analysis_count}`}
        />
        <KpiTile
          label="Requirements reviewed"
          value={data.requirement_count}
          note={ANALYTICS_COPY.requirements}
          nLabel={`n=${data.requirement_count}`}
        />
        <KpiTile
          label="Mandatory gaps"
          value={data.mandatory_gap_count}
          note={ANALYTICS_COPY.gaps}
          nLabel={`${rubricLabel}`}
        />
        <KpiTile
          label="Blocked analyses"
          value={data.blocked_count}
          note={ANALYTICS_COPY.blocked}
          nLabel={`n=${data.analysis_count}`}
        />
      </div>

      <ScoreTrendChart points={data.scores} rubricLabel={rubricLabel} />
      <EvidenceMixChart
        buckets={data.evidence}
        requirementCount={data.requirement_count}
        rubricLabel={rubricLabel}
      />

      <section className="card">
        <h2>Roles you analyzed</h2>
        <p className="muted">{ANALYTICS_COPY.roles}</p>
        <p className="footnote">{rubricLabel} · n={data.analysis_count}</p>
        <table>
          <thead>
            <tr>
              <th scope="col">Target role</th>
              <th scope="col">Analyses</th>
              <th scope="col">Avg readiness</th>
              <th scope="col">Confirmed</th>
              <th scope="col">Not found</th>
              <th scope="col">Contradicted</th>
            </tr>
          </thead>
          <tbody>
            {data.roles.map((role) => (
              <tr key={role.target_role}>
                <td>{role.target_role}</td>
                <td>{role.analysis_count}</td>
                <td>{role.avg_readiness ?? "—"}</td>
                <td>{role.confirmed}</td>
                <td>{role.not_found}</td>
                <td>{role.contradicted}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Missing terminology</h2>
        <p className="muted">{ANALYTICS_COPY.terms}</p>
        <p className="footnote">{rubricLabel} · n={data.analysis_count}</p>
        {data.missing_terminology.length === 0 ? (
          <p className="muted">No missing-terminology strings on these analyses.</p>
        ) : (
          <ul className="term-list">
            {data.missing_terminology.map((item) => (
              <li key={item.term}>
                <span>{item.term}</span>
                <span className="pill">{item.count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
