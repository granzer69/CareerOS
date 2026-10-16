export const SCORE_COPY = {
  fit: "Job-fit: how much of the JD is supported by resume evidence. Missing evidence is not proof the person lacks the skill.",
  alignment:
    "Resume-alignment: how clearly the current resume communicates those verified qualifications.",
  readiness:
    "Application-readiness: 0.60×fit + 0.35×alignment + 0.05×completeness (renormalized if completeness is unknown). Not P(hire) or P(interview).",
  terminology:
    "Terminology coverage (legacy field ats_score): keyword overlap with the JD. Not a vendor ATS score.",
} as const;

export const HONESTY_COPY = {
  notPredictor:
    "Analyses are stored only for the signed-in owner. This is not a placement predictor and does not recommend companies.",
  analyzeDisclaimer:
    "Scores are rubric v1.0.0: job-fit, resume-alignment, and application-readiness. They are not a probability of being hired or interviewed, and ats_score is terminology coverage — not a vendor ATS result.",
  historyReadiness: "Overall score is application-readiness, not a hiring probability.",
  modelMissing:
    "Local model: not configured. Analysis and edit generation need a GGUF file on the API host (LOCAL_MODEL_PATH). Missing weights return 503 model_unavailable — CareerOS does not call a hosted LLM and will not download weights for you.",
  modelConfigured:
    "Local model file is present. Scores still come from rubric v1.0.0, not the model.",
  analyticsScope:
    "These charts are your last 100 analyses. They describe evidence coverage under the named rubric — not a hiring probability, interview chance, or comparison with other students.",
} as const;

export const STUDIO_COPY = {
  brandMark: "CareerOS",
  brandLine: "Campus resume studio",
  brandSub: "JD-driven resume copilot",
  heroTitle: "See what a real posting already supports on your resume",
  heroLead:
    "Paste the job description you are actually applying to. CareerOS maps each requirement to evidence on your PDF or DOCX — then scores job-fit, resume-alignment, and application-readiness with rubric v1.0.0.",
  whoFor:
    "Built for students and early-career applicants who want a clear JD match, not a placement office dashboard.",
  stepUpload: "Upload a PDF or DOCX resume (5 MB max).",
  stepRole: "Name the role on the posting — intern, co-op, new grad, or otherwise.",
  stepJd: "Paste the full job description so required skills stay explicit.",
  stepRead: "Read evidence states, then apply only supported rewrites.",
  emptyHistory:
    "No analyses yet. Run one with a resume and a real job description — empty history is honest, not a reason to invent rows.",
  emptyAnalytics:
    "Analytics stay empty until you run an analysis. CareerOS will not fill charts with sample scores or other students' data.",
  footer:
    "Owner-scoped analyses. Local GGUF when configured. Rubric scores, not a hosted LLM and not a hiring forecast.",
} as const;

export const ANALYTICS_COPY = {
  analyses: "How many of your analyses are in this view (capped at 100, newest first on the server).",
  requirements: "JD requirement rows across those analyses, counted from stored evidence matches.",
  gaps: "Mandatory requirements whose evidence is not_found or contradicted. Missing evidence is not proof you lack the skill.",
  blocked: "Analyses flagged blocked_by_requirement. The composite score does not hide an eligibility miss.",
  trend:
    "Application-readiness over time for analyses that have a rubric score. Points with a null score are omitted, not drawn as zero.",
  evidence:
    "Count of requirement matches by evidence state: confirmed, partial, not_found, contradicted, unknown.",
  roles: "Evidence mix grouped by the target_role you typed. Average readiness skips analyses with a null rubric score.",
  terms: "Strings that appeared in keywords_missing. Terminology coverage is not a vendor ATS pass or fail.",
  fitAlignment:
    "Job-fit and resume-alignment over time. Null rubric scores are omitted from the chart, not drawn as zero.",
  editFunnel:
    "Supported-rewrite accept rate = accepted ÷ (accepted + rejected). Pending suggestions are excluded from the rate.",
  versionLift:
    "Original application-readiness vs the latest accepted resume version for the same analysis. Not a hiring forecast.",
  heatmap:
    "Top requirement texts from your JD matches, grouped by target_role and evidence state.",
  profileFilter:
    "Filter analytics to analyses whose target_role exactly matches your profile role.",
} as const;

export const PROFILE_COPY = {
  title: "Your profile",
  lead:
    "Save a default target role and experience level. Analyze can prefill the role field; analytics can filter to that role.",
  skillsHint: "Comma-separated skills for your own reference. They do not change rubric scores.",
  experience: "Experience level is descriptive only — scores still come from the JD and resume evidence.",
  missing: "No profile yet. Save one to prefill Analyze and filter Analytics.",
} as const;
