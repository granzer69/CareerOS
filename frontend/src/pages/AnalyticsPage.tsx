import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { request } from "../api";
import { isSessionExpiredError } from "../authRedirect";
import { Banner } from "../components/Banner";
import { EditFunnelCard } from "../components/EditFunnelCard";
import { EmptyState } from "../components/EmptyState";
import { EvidenceMixChart } from "../components/EvidenceMixChart";
import { KpiTile } from "../components/KpiTile";
import { LoadingState } from "../components/LoadingState";
import { ImportanceEvidenceChart } from "../components/ImportanceEvidenceChart";
import { RequirementHeatmapTable } from "../components/RequirementHeatmapTable";
import { RoleCoverageMatrix } from "../components/RoleCoverageMatrix";
import { RubricTrendChart } from "../components/RubricTrendChart";
import { EligibilityRollupTable } from "../components/EligibilityRollupTable";
import { ProfileSkillCoverageTable } from "../components/ProfileSkillCoverageTable";
import { TerminologyTrendChart } from "../components/TerminologyTrendChart";
import { ScoreTrendChart } from "../components/ScoreTrendChart";
import { VersionLiftTable } from "../components/VersionLiftTable";
import { ANALYTICS_COPY, HONESTY_COPY, STUDIO_COPY } from "../copy";
import type { AnalyticsRead, UserProfileRead } from "../types";

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsRead | null>(null);
  const [profileRole, setProfileRole] = useState<string | null>(null);
  const [useProfileFilter, setUseProfileFilter] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  const loadAnalytics = useCallback(async () => {
    const query =
      useProfileFilter && profileRole
        ? `?target_role=${encodeURIComponent(profileRole)}`
        : "";
    const payload = await request<AnalyticsRead>(`/api/v1/resume/analytics${query}`);
    setData(payload);
  }, [profileRole, useProfileFilter]);

  useEffect(() => {
    void request<UserProfileRead>("/api/v1/user-profile/me")
      .then((profile) => setProfileRole(profile.target_role))
      .catch(() => {
        setProfileRole(null);
      });
  }, []);

  useEffect(() => {
    void loadAnalytics().catch((err: unknown) => {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Could not load analytics");
    });
  }, [loadAnalytics]);

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
        {useProfileFilter && profileRole ? (
          <p className="footnote">
            No analyses match profile role “{profileRole}”.{" "}
            <button className="secondary" type="button" onClick={() => setUseProfileFilter(false)}>
              Show all roles
            </button>
          </p>
        ) : null}
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
        {profileRole ? (
          <p className="row filter-row">
            <button
              className="secondary"
              type="button"
              aria-pressed={useProfileFilter}
              onClick={() => setUseProfileFilter((value) => !value)}
            >
              {useProfileFilter ? "Showing" : "Filter to"} profile role: {profileRole}
            </button>
            <span className="footnote">{ANALYTICS_COPY.profileFilter}</span>
          </p>
        ) : (
          <p className="footnote">
            <Link to="/profile">Add a profile</Link> to prefill Analyze and filter this view.
          </p>
        )}
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
          nLabel={rubricLabel}
        />
        <KpiTile
          label="Blocked analyses"
          value={data.blocked_count}
          note={ANALYTICS_COPY.blocked}
          nLabel={`n=${data.analysis_count}`}
        />
      </div>

      <RubricTrendChart points={data.scores} rubricLabel={rubricLabel} />
      <ScoreTrendChart points={data.scores} rubricLabel={rubricLabel} />
      <TerminologyTrendChart points={data.scores} rubricLabel={rubricLabel} />
      <ImportanceEvidenceChart
        buckets={data.importance_evidence}
        requirementCount={data.requirement_count}
        rubricLabel={rubricLabel}
      />
      <RoleCoverageMatrix rows={data.role_coverage_matrix} rubricLabel={rubricLabel} />
      <EvidenceMixChart
        buckets={data.evidence}
        requirementCount={data.requirement_count}
        rubricLabel={rubricLabel}
      />
      <EligibilityRollupTable
        rows={data.eligibility_rollups}
        analysisCount={data.analysis_count}
        rubricLabel={rubricLabel}
      />
      <ProfileSkillCoverageTable rows={data.profile_skill_coverage} rubricLabel={rubricLabel} />
      <EditFunnelCard data={data} rubricLabel={rubricLabel} />
      <VersionLiftTable rows={data.version_deltas} rubricLabel={rubricLabel} />
      <RequirementHeatmapTable cells={data.requirement_heatmap} rubricLabel={rubricLabel} />

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
