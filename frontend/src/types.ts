export type EvidenceState =
  | "confirmed"
  | "partial"
  | "not_found"
  | "contradicted"
  | "unknown";

export type RequirementImportance = "mandatory" | "preferred" | "contextual";
export type EditKind =
  | "supported_rewrite"
  | "missing_qualification"
  | "unsupported"
  | "needs_evidence";
export type EditStatus = "pending" | "accepted" | "rejected";

export type ExperienceLevel = "student" | "junior" | "mid";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
}

export interface UserProfileRead {
  id: string;
  user_id: string;
  skills: string[];
  target_role: string;
  experience_level: ExperienceLevel;
  created_at: string;
}

export interface UserProfileCreate {
  user_id: string;
  skills: string[];
  target_role: string;
  experience_level: ExperienceLevel;
}

export interface UserProfileUpdate {
  skills?: string[];
  target_role?: string;
  experience_level?: ExperienceLevel;
}

export interface HealthStatus {
  status: string;
  database: string;
  local_model: string;
}

export interface RequirementMatch {
  id: string;
  text: string;
  category: string;
  importance: RequirementImportance;
  is_eligibility: boolean;
  evidence_state: EvidenceState;
  evidence_span: string | null;
  rationale: string;
}

export interface EligibilityItem {
  text: string;
  status: string;
  rationale: string;
}

export interface ResumeSection {
  name: string;
  score: number;
  status: string;
  feedback: string;
  suggestions: string[];
}

export interface ResumeAnalysisSummary {
  id: string;
  file_name: string;
  target_role: string;
  overall_score: number;
  grade: string;
  created_at: string;
}

export interface ResumeAnalysisRead {
  id: string;
  session_id: string;
  file_name: string;
  target_role: string;
  overall_score: number;
  grade: string;
  ats_score: number;
  estimated_level: string;
  top_strengths: string[];
  critical_weaknesses: string[];
  keywords_missing: string[];
  sections: ResumeSection[];
  created_at: string;
  job_description: string | null;
  job_fit_score: number | null;
  resume_alignment_score: number | null;
  application_readiness_score: number | null;
  rubric_version: string | null;
  requirement_matches: RequirementMatch[];
  eligibility: EligibilityItem[];
  blocked_by_requirement: boolean;
  completeness_included: boolean;
}

export interface ResumeEditRead {
  id: string;
  analysis_id: string;
  batch_id: string | null;
  source_version_id: string | null;
  source_version_number: number;
  source_content_hash: string;
  kind: EditKind;
  status: EditStatus;
  original_span: string | null;
  proposed_text: string;
  evidence_span: string | null;
  requirement_id: string | null;
  rationale: string;
  span_start: number | null;
  span_end: number | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface ResumeVersionSummary {
  id: string;
  analysis_id: string;
  version_number: number;
  content_hash: string | null;
  overall_score: number | null;
  grade: string | null;
  created_at: string;
}

export interface ResumeVersionRead extends ResumeVersionSummary {
  resume_text: string;
  applied_edit_ids: string[];
  ats_score: number | null;
  estimated_level: string | null;
  job_fit_score: number | null;
  resume_alignment_score: number | null;
  application_readiness_score: number | null;
  rubric_version: string | null;
  requirement_matches: RequirementMatch[];
  eligibility: EligibilityItem[];
  blocked_by_requirement: boolean;
  completeness_included: boolean;
}

export interface EvidenceBucket {
  state: EvidenceState;
  count: number;
}

export interface ScorePoint {
  id: string;
  created_at: string;
  file_name: string;
  target_role: string;
  overall_score: number | null;
  job_fit_score: number | null;
  resume_alignment_score: number | null;
  application_readiness_score: number | null;
  ats_score?: number | null;
  rubric_version: string | null;
  blocked_by_requirement: boolean;
}

export interface RoleBreakdown {
  target_role: string;
  analysis_count: number;
  avg_readiness: number | null;
  confirmed: number;
  not_found: number;
  contradicted: number;
}

export interface TermCount {
  term: string;
  count: number;
}

export interface EditKindCount {
  kind: string;
  count: number;
}

export interface EditStats {
  total_edits: number;
  pending: number;
  accepted: number;
  rejected: number;
  supported_rewrite_generated: number;
  supported_rewrite_accepted: number;
  supported_rewrite_rejected: number;
  supported_rewrite_accept_rate: number | null;
}

export interface ImportanceEvidenceBucket {
  importance: string;
  state: EvidenceState;
  count: number;
}

export interface RoleCoverageRow {
  target_role: string;
  requirement_text: string;
  confirmed: number;
  partial: number;
  not_found: number;
  contradicted: number;
  unknown: number;
}

export interface VersionDelta {
  analysis_id: string;
  file_name: string;
  target_role: string;
  original_readiness: number | null;
  latest_version_readiness: number | null;
  delta: number | null;
  latest_version_number: number | null;
  rubric_version: string | null;
  original_job_fit: number | null;
  latest_job_fit: number | null;
  original_alignment: number | null;
  latest_alignment: number | null;
  original_terminology: number | null;
  latest_terminology: number | null;
}

export interface RequirementHeatCell {
  requirement_text: string;
  target_role: string;
  evidence_state: EvidenceState;
  count: number;
}

export interface AnalyticsRead {
  analysis_count: number;
  requirement_count: number;
  blocked_count: number;
  mandatory_gap_count: number;
  latest_created_at: string | null;
  rubric_versions: string[];
  evidence: EvidenceBucket[];
  scores: ScorePoint[];
  roles: RoleBreakdown[];
  missing_terminology: TermCount[];
  edits: EditStats;
  edit_kinds: EditKindCount[];
  version_deltas: VersionDelta[];
  requirement_heatmap: RequirementHeatCell[];
  importance_evidence: ImportanceEvidenceBucket[];
  role_coverage_matrix: RoleCoverageRow[];
}

export interface ApiError {
  message: string;
  code?: string;
}
