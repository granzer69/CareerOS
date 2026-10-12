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
} as const;
