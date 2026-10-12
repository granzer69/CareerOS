import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { request } from "../api";
import { isSessionExpiredError } from "../authRedirect";
import { Banner } from "../components/Banner";
import { EditProposal } from "../components/EditProposal";
import { LoadingState } from "../components/LoadingState";
import { RequirementTable } from "../components/RequirementTable";
import { ScoreCard } from "../components/ScoreCard";
import { StatusPill } from "../components/StatusPill";
import { SCORE_COPY } from "../copy";
import type {
  ResumeAnalysisRead,
  ResumeEditRead,
  ResumeVersionRead,
  ResumeVersionSummary,
} from "../types";

export function AnalysisDetailPage() {
  const { analysisId } = useParams();
  const [analysis, setAnalysis] = useState<ResumeAnalysisRead | null>(null);
  const [edits, setEdits] = useState<ResumeEditRead[]>([]);
  const [versions, setVersions] = useState<ResumeVersionSummary[]>([]);
  const [version, setVersion] = useState<ResumeVersionRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);

  const load = useCallback(async () => {
    if (!analysisId) {
      return;
    }
    const [nextAnalysis, nextEdits, nextVersions] = await Promise.all([
      request<ResumeAnalysisRead>(`/api/v1/resume/analyses/${analysisId}`),
      request<ResumeEditRead[]>(`/api/v1/resume/analyses/${analysisId}/edits`),
      request<ResumeVersionSummary[]>(`/api/v1/resume/analyses/${analysisId}/versions`),
    ]);
    setAnalysis(nextAnalysis);
    setEdits(nextEdits);
    setVersions(nextVersions);
  }, [analysisId]);

  useEffect(() => {
    void load().catch((err: unknown) => {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Could not load analysis");
    });
  }, [load]);

  async function generateEdits() {
    if (!analysisId) {
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const next = await request<ResumeEditRead[]>(`/api/v1/resume/analyses/${analysisId}/edits`, {
        method: "POST",
      });
      setEdits(next);
      setNotice(
        next.length
          ? "Suggestions generated. Only supported rewrites can be applied."
          : "No suggestions were returned.",
      );
    } catch (err) {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Could not generate edits");
    } finally {
      setBusy(false);
    }
  }

  async function rejectEdit(editId: string) {
    if (!analysisId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await request(`/api/v1/resume/analyses/${analysisId}/edits/${editId}/reject`, {
        method: "POST",
      });
      await load();
    } catch (err) {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  }

  async function acceptEdit(editId: string) {
    if (!analysisId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await request<ResumeVersionRead>(
        `/api/v1/resume/analyses/${analysisId}/edits/${editId}/accept`,
        { method: "POST" },
      );
      setVersion(next);
      await load();
      setNotice(
        `Applied a supported rewrite as version ${next.version_number}. Original upload is unchanged.`,
      );
    } catch (err) {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Accept failed");
    } finally {
      setBusy(false);
    }
  }

  async function restoreOriginal() {
    if (!analysisId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await request<ResumeVersionRead>(
        `/api/v1/resume/analyses/${analysisId}/restore-original`,
        { method: "POST" },
      );
      setVersion(next);
      await load();
      setNotice(`Restored the original resume as version ${next.version_number}.`);
    } catch (err) {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Restore failed");
    } finally {
      setBusy(false);
    }
  }

  async function openVersion(versionId: string) {
    if (!analysisId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await request<ResumeVersionRead>(
        `/api/v1/resume/analyses/${analysisId}/versions/${versionId}`,
      );
      setVersion(next);
    } catch (err) {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Could not load version");
    } finally {
      setBusy(false);
    }
  }

  async function copySnapshotForward() {
    if (!analysisId || !version) {
      return;
    }
    setBusy(true);
    setError(null);
    const sourceNumber = version.version_number;
    try {
      const next = await request<ResumeVersionRead>(
        `/api/v1/resume/analyses/${analysisId}/versions/${version.id}/restore`,
        { method: "POST" },
      );
      setVersion(next);
      await load();
      setNotice(`Copied version ${sourceNumber} forward as version ${next.version_number}.`);
    } catch (err) {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Restore failed");
    } finally {
      setBusy(false);
    }
  }

  if (expired) {
    return <Navigate to="/login" replace />;
  }
  if (error && !analysis) {
    return <Banner tone="error">{error}</Banner>;
  }
  if (!analysis) {
    return <LoadingState label="Loading analysis…" />;
  }

  const pending = edits.filter((item) => item.status === "pending");
  const rubric = analysis.rubric_version ?? "unknown";

  return (
    <div className="grid report">
      <p>
        <Link to="/history">← History</Link>
      </p>
      {error ? <Banner tone="error">{error}</Banner> : null}
      {notice ? <Banner tone="ok">{notice}</Banner> : null}
      {analysis.blocked_by_requirement ? (
        <Banner tone="block">
          Blocked by a stated eligibility requirement. The composite score does not hide this.
        </Banner>
      ) : null}

      <section className="card">
        <header className="report-header">
          <p className="eyebrow">Evidence report · rubric {rubric}</p>
          <h1>{analysis.file_name}</h1>
          <p className="muted">
            {analysis.target_role} · grade {analysis.grade} · estimated level {analysis.estimated_level}
          </p>
        </header>
        <div className="scores">
          <ScoreCard
            label="Job-fit"
            value={analysis.job_fit_score}
            note={SCORE_COPY.fit}
            rubricVersion={rubric}
          />
          <ScoreCard
            label="Resume-alignment"
            value={analysis.resume_alignment_score}
            note={SCORE_COPY.alignment}
            rubricVersion={rubric}
          />
          <ScoreCard
            label="Application-readiness"
            value={analysis.application_readiness_score ?? analysis.overall_score}
            note={SCORE_COPY.readiness}
            rubricVersion={rubric}
          />
          <ScoreCard
            label="Terminology coverage"
            value={analysis.ats_score}
            note={SCORE_COPY.terminology}
            rubricVersion={rubric}
          />
        </div>
      </section>

      <section className="card">
        <h2>Eligibility</h2>
        {analysis.eligibility.length === 0 ? (
          <p className="muted">No eligibility items.</p>
        ) : (
          <ul>
            {analysis.eligibility.map((item) => (
              <li key={item.text}>
                <StatusPill value={item.status} /> {item.text} — {item.rationale}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Requirement evidence</h2>
        <RequirementTable matches={analysis.requirement_matches} />
      </section>

      <section className="card">
        <h2>Presentation notes</h2>
        <p>
          <strong>Strengths:</strong> {analysis.top_strengths.join(" · ") || "—"}
        </p>
        <p>
          <strong>Gaps in the supplied evidence:</strong>{" "}
          {analysis.critical_weaknesses.join(" · ") || "—"}
        </p>
        {analysis.keywords_missing.length ? (
          <p>
            <strong>Missing terminology:</strong> {analysis.keywords_missing.join(", ")}
          </p>
        ) : null}
        <ul>
          {analysis.sections.map((section) => (
            <li key={section.name}>
              {section.name}: {section.status} ({section.score}) — {section.feedback}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Evidence-grounded edits</h2>
        <p className="muted">
          The model never assigns scores or kind. Unsupported, needs-evidence, and missing-qualification
          items cannot be applied as facts.
        </p>
        <button type="button" onClick={() => void generateEdits()} disabled={busy} aria-busy={busy}>
          {busy ? "Working…" : "Generate suggestions"}
        </button>
        {pending.length === 0 ? <p className="muted">No pending suggestions.</p> : null}
        {pending.map((edit) => (
          <EditProposal
            key={edit.id}
            edit={edit}
            busy={busy}
            onAccept={(id) => void acceptEdit(id)}
            onReject={(id) => void rejectEdit(id)}
          />
        ))}
      </section>

      <section className="card">
        <h2>Versions</h2>
        <p className="muted">The original analysis text stays immutable. Restore creates a new version.</p>
        <div className="row">
          <button className="secondary" type="button" disabled={busy} onClick={() => void restoreOriginal()}>
            Restore original as a new version
          </button>
          {version ? (
            <button
              className="secondary"
              type="button"
              disabled={busy}
              onClick={() => void copySnapshotForward()}
            >
              Copy this snapshot forward
            </button>
          ) : null}
        </div>
        {versions.length === 0 ? (
          <p>No accepted versions yet.</p>
        ) : (
          <ul>
            {versions.map((item) => (
              <li key={item.id}>
                v{item.version_number} · readiness {item.overall_score ?? "—"} · {item.grade ?? "—"}{" "}
                <button className="secondary" type="button" onClick={() => void openVersion(item.id)}>
                  View working copy
                </button>
              </li>
            ))}
          </ul>
        )}
        {version ? (
          <div>
            <h3>Version {version.version_number}</h3>
            <p>
              Readiness {version.application_readiness_score ?? version.overall_score} · job-fit{" "}
              {version.job_fit_score} · alignment {version.resume_alignment_score}
            </p>
            <pre>{version.resume_text}</pre>
          </div>
        ) : null}
      </section>
    </div>
  );
}
