import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getToken, request } from "../api";
import { isSessionExpiredError } from "../authRedirect";
import { Banner } from "../components/Banner";
import { StepList } from "../components/StepList";
import { HONESTY_COPY, STUDIO_COPY } from "../copy";
import type { ResumeAnalysisRead } from "../types";

export function AnalyzePage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [targetRole, setTargetRole] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF or DOCX resume.");
      return;
    }
    setPending(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    body.append("target_role", targetRole);
    body.append("job_description", jobDescription);
    try {
      const analysis = await request<ResumeAnalysisRead>("/api/v1/resume/analyze", {
        method: "POST",
        body,
      });
      navigate(`/analyses/${analysis.id}`);
    } catch (err) {
      if (isSessionExpiredError(err)) {
        navigate("/login", { replace: true });
        return;
      }
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="analyze-layout">
      <section className="card analyze-guide" aria-labelledby="analyze-guide-title">
        <p className="eyebrow">{STUDIO_COPY.brandLine}</p>
        <h2 id="analyze-guide-title">Four steps, one posting</h2>
        <p className="muted">{STUDIO_COPY.whoFor}</p>
        <StepList />
        <p className="footnote">{HONESTY_COPY.analyzeDisclaimer}</p>
      </section>
      <div className="card analyze-form">
        <h1>Analyze a resume against a JD</h1>
        <p className="lead">
          Use the posting you would actually submit to. CareerOS will not invent a company list or a
          hiring forecast.
        </p>
        {error ? <Banner tone="error">{error}</Banner> : null}
        <form className="grid" onSubmit={onSubmit} aria-busy={pending}>
          <label htmlFor="resume-file">
            Resume (PDF or DOCX, max 5 MB)
            <input
              id="resume-file"
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            {file ? <span className="footnote">Selected: {file.name}</span> : null}
          </label>
          <label htmlFor="target-role">
            Target role
            <input
              id="target-role"
              value={targetRole}
              onChange={(event) => setTargetRole(event.target.value)}
              maxLength={200}
              required
              placeholder="e.g. Software engineering intern"
            />
          </label>
          <label htmlFor="job-description">
            Job description
            <textarea
              id="job-description"
              value={jobDescription}
              onChange={(event) => setJobDescription(event.target.value)}
              maxLength={20000}
              required
              placeholder="Paste the full job description. Required skills should be explicit."
            />
          </label>
          <button type="submit" disabled={pending || !getToken()} aria-busy={pending}>
            {pending ? "Analyzing…" : "Run analysis"}
          </button>
        </form>
      </div>
    </div>
  );
}
