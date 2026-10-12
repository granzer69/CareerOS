import type { ResumeAnalysisRead, ResumeAnalysisSummary, ResumeEditRead } from "../types";

export const analysisFixture: ResumeAnalysisRead = {
  id: "00000000-0000-0000-0000-0000000000aa",
  session_id: "00000000-0000-0000-0000-0000000000bb",
  file_name: "cv.pdf",
  target_role: "Backend Engineer",
  overall_score: 72,
  grade: "B",
  ats_score: 65,
  estimated_level: "mid",
  top_strengths: ["Python"],
  critical_weaknesses: ["No metrics"],
  keywords_missing: ["Kubernetes"],
  sections: [
    {
      name: "Work Experience",
      score: 70,
      status: "needs_improvement",
      feedback: "Add measurable outcomes.",
      suggestions: ["Quantify impact"],
    },
  ],
  created_at: "2026-10-12T12:00:00.000Z",
  job_description: "Required: Python",
  job_fit_score: 70,
  resume_alignment_score: 68,
  application_readiness_score: 72,
  rubric_version: "v1.0.0",
  requirement_matches: [
    {
      id: "req-1",
      text: "Python",
      category: "skill",
      importance: "mandatory",
      is_eligibility: false,
      evidence_state: "confirmed",
      evidence_span: "Python engineer",
      rationale: "Explicit skill mention.",
    },
    {
      id: "req-2",
      text: "Kubernetes",
      category: "skill",
      importance: "preferred",
      is_eligibility: false,
      evidence_state: "not_found",
      evidence_span: null,
      rationale: "No matching evidence.",
    },
  ],
  eligibility: [],
  blocked_by_requirement: false,
  completeness_included: true,
};

export const historyFixture: ResumeAnalysisSummary[] = [
  {
    id: analysisFixture.id,
    file_name: analysisFixture.file_name,
    target_role: analysisFixture.target_role,
    overall_score: analysisFixture.overall_score,
    grade: analysisFixture.grade,
    created_at: analysisFixture.created_at,
  },
];

export const supportedEdit: ResumeEditRead = {
  id: "edit-supported",
  analysis_id: analysisFixture.id,
  batch_id: "batch-1",
  source_version_id: null,
  source_version_number: 0,
  source_content_hash: "abc",
  kind: "supported_rewrite",
  status: "pending",
  original_span: "Built APIs",
  proposed_text: "Built FastAPI services at Acme",
  evidence_span: "FastAPI at Acme",
  requirement_id: "req-1",
  rationale: "Unique span, attested employer.",
  span_start: 0,
  span_end: 10,
  created_at: analysisFixture.created_at,
  reviewed_at: null,
};

export const unsupportedEdit: ResumeEditRead = {
  ...supportedEdit,
  id: "edit-unsupported",
  kind: "unsupported",
  proposed_text: "Led a team of 40",
  rationale: "Headcount is not attested.",
};
