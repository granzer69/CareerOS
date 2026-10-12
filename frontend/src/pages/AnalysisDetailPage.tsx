import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { request } from "../api";
import type {
  ResumeAnalysisRead,
  ResumeEditRead,
  ResumeVersionRead,
  ResumeVersionSummary,
} from "../types";

const SCORE_COPY = {
  fit: "Job-fit: how much of the JD is supported by resume evidence. Missing evidence is not proof the person lacks the skill.",
  alignment:
    "Resume-alignment: how clearly the current resume communicates those verified qualifications.",
  readiness:
    "Application-readiness: 0.60×fit + 0.35×alignment + 0.05×completeness (renormalized if completeness is unknown). Not P(hire) or P(interview).",
  terminology:
    "Terminology coverage (legacy field ats_score): keyword overlap with the JD. Not a vendor ATS score.",
};

function ScoreCard({
  label,
  value,
  note,
}: {
  label: string;
  value: number | null | undefined;
  note: string;
}) {
  return (
    <div className="card">
      <div className="muted">{label}</div>
      <strong style={{ fontSize: "1.8rem" }}>{value ?? "—"}</strong>
      <p className="footnote">{note}</p>
    </div>
  );
}

export function AnalysisDetailPage() {
  const { analysisId } = useParams();
  const [analysis, setAnalysis] = useState<ResumeAnalysisRead | null>(null);
  const [edits, setEdits] = useState<ResumeEditRead[]>([]);
  const [versions, setVersions] = useState<ResumeVersionSummary[]>([]);
  const [version, setVersion] = useState<ResumeVersionRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
      setError(err instanceof Error ? err.message : "Could not load version");
    } finally {
      setBusy(false);
    }
  }

  if (error && !analysis) {
    return <div className="banner error">{error}</div>;
  }
  if (!analysis) {
    return <p className="muted">Loading analysis…</p>;
  }

  const pending = edits.filter((item) => item.status === "pending");

  return (
    <div className="grid">
      <p>
        <Link to="/history">← History</Link>
      </p>
      {error ? <div className="banner error">{error}</div> : null}
      {notice ? <div className="banner ok">{notice}</div> : null}
      {analysis.blocked_by_requirement ? (
        <div className="banner block">
          Blocked by a stated eligibility requirement. The composite score does not hide this.
        </div>
      ) : null}

      <section className="card">
        <h1>{analysis.file_name}</h1>
        <p>
          {analysis.target_role} · grade {analysis.grade} · estimated level {analysis.estimated_level}{" "}
          · rubric {analysis.rubric_version ?? "unknown"}
        </p>
        <div className="scores">
          <ScoreCard
            label="Job-fit"
            value={analysis.job_fit_score}
            note={SCORE_COPY.fit}
          />
          <ScoreCard
            label="Resume-alignment"
            value={analysis.resume_alignment_score}
            note={SCORE_COPY.alignment}
          />
          <ScoreCard
            label="Application-readiness"
            value={analysis.application_readiness_score ?? analysis.overall_score}
            note={SCORE_COPY.readiness}
          />
          <ScoreCard
            label="Terminology coverage"
            value={analysis.ats_score}
            note={SCORE_COPY.terminology}
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
                <span className={`pill ${item.status}`}>{item.status}</span> {item.text} — {item.rationale}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Requirement evidence</h2>
        <table>
          <thead>
            <tr>
              <th>Requirement</th>
              <th>Importance</th>
              <th>State</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {analysis.requirement_matches.map((match) => (
              <tr key={match.id}>
                <td>{match.text}</td>
                <td>{match.importance}</td>
                <td>
                  <span className={`pill ${match.evidence_state}`}>{match.evidence_state}</span>
                </td>
                <td>
                  {match.rationale}
                  {match.evidence_span ? <div className="footnote">span: {match.evidence_span}</div> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Presentation notes</h2>
        <p>
          <strong>Strengths:</strong> {analysis.top_strengths.join(" · ")}
        </p>
        <p>
          <strong>Gaps in the supplied evidence:</strong> {analysis.critical_weaknesses.join(" · ")}
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
        <button type="button" onClick={() => void generateEdits()} disabled={busy}>
          {busy ? "Working…" : "Generate suggestions"}
        </button>
        {pending.length === 0 ? <p className="muted">No pending suggestions.</p> : null}
        {pending.map((edit) => (
          <article className="edit" key={edit.id}>
            <div>
              <span className={`pill ${edit.kind}`}>{edit.kind}</span>{" "}
              <span className="pill">{edit.status}</span>
            </div>
            <p>{edit.rationale}</p>
            <div className="diff">
              <div>
                <div className="muted">Original</div>
                <pre>{edit.original_span || "—"}</pre>
              </div>
              <div>
                <div className="muted">Proposed</div>
                <pre>{edit.proposed_text}</pre>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {edit.kind === "supported_rewrite" ? (
                <button type="button" disabled={busy} onClick={() => void acceptEdit(edit.id)}>
                  Accept rewrite
                </button>
              ) : (
                <span className="muted">Not auto-applied.</span>
              )}
              <button
                className="secondary"
                type="button"
                disabled={busy}
                onClick={() => void rejectEdit(edit.id)}
              >
                Reject
              </button>
            </div>
          </article>
        ))}
      </section>

      <section className="card">
        <h2>Versions</h2>
        <p className="muted">The original analysis text stays immutable. Restore creates a new version.</p>
        <button className="secondary" type="button" disabled={busy} onClick={() => void restoreOriginal()}>
          Restore original as a new version
        </button>
        {version ? (
          <button
            className="secondary"
            type="button"
            disabled={busy}
            onClick={() => {
              if (!analysisId) {
                return;
              }
              setBusy(true);
              void request<ResumeVersionRead>(
                `/api/v1/resume/analyses/${analysisId}/versions/${version.id}/restore`,
                { method: "POST" },
              )
                .then(async (next) => {
                  setVersion(next);
                  await load();
                  setNotice(`Copied version ${version.version_number} forward as version ${next.version_number}.`);
                })
                .catch((err: unknown) => {
                  setError(err instanceof Error ? err.message : "Restore failed");
                })
                .finally(() => setBusy(false));
            }}
          >
            Copy this snapshot forward
          </button>
        ) : null}
        {versions.length === 0 ? <p>No accepted versions yet.</p> : (
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
