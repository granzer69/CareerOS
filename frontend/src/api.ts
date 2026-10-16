import type { AnalysisJobRead, ApiError, ResumeAnalysisRead } from "./types";

const TOKEN_KEY = "careeros_token";
const USER_ID_KEY = "careeros_user_id";

export function apiBase(): string {
  const configured = import.meta.env.VITE_BACKEND_URL || "";
  return configured.replace(/\/$/, "");
}

export function apiUrl(path: string): string {
  return `${apiBase()}${path}`;
}

export function getToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function getUserId(): string | null {
  return window.localStorage.getItem(USER_ID_KEY);
}

export function setUserId(userId: string): void {
  window.localStorage.setItem(USER_ID_KEY, userId);
}

export function setSession(token: string, userId: string): void {
  setToken(token);
  setUserId(userId);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_ID_KEY);
}

export function parseApiError(payload: unknown, fallback: string): ApiError {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) {
    return { message: fallback };
  }
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") {
    return { message: detail };
  }
  if (Array.isArray(detail)) {
    return { message: "The request could not be validated. Check the form and try again." };
  }
  if (detail && typeof detail === "object") {
    const inner = detail as { detail?: unknown; code?: string };
    const message = typeof inner.detail === "string" ? inner.detail : fallback;
    return { message, code: inner.code };
  }
  return { message: fallback };
}

export function actionableMessage(error: ApiError): string {
  switch (error.code) {
    case "unauthorized":
    case "invalid_token":
      return "Your session expired. Sign in again.";
    case "model_unavailable":
      return "Local GGUF weights are not configured on the API host. Health can still be OK. Set LOCAL_MODEL_PATH to an on-disk file; CareerOS will not download a model or call a hosted LLM.";
    case "inference_failed":
      return "Local inference failed on the API host. Check server logs, LOCAL_MODEL_PATH, and that llama-cpp-python matches your OS (glibc vs musl).";
    case "file_too_large":
      return "Resume files must be 5 MB or smaller.";
    case "unsupported_media_type":
      return "Upload a PDF or DOCX resume.";
    case "empty_resume":
      return "No text could be read from that file.";
    case "job_description_required":
      return "Paste the job description. CareerOS scores against a real JD, not a title alone.";
    case "edit_source_stale":
      return "The resume snapshot changed. Reload edits and try again.";
    case "version_conflict":
      return "Another version was saved at the same time. Reload and retry.";
    case "edit_not_acceptable":
      return "Only supported rewrites can be applied. Flagged claims stay on the resume until you supply evidence.";
    case "email_exists":
      return "That email is already registered. Sign in instead.";
    case "invalid_credentials":
      return "Invalid email or password.";
    case "schema_outdated":
      return "The local database schema is behind Alembic. Stop the API, delete leftover sqlite, run `alembic upgrade head`, then restart.";
    case "not_found":
      return "That resource was not found for your account.";
    default:
      return error.message;
  }
}

async function readError(response: Response, fallback: string): Promise<ApiError> {
  try {
    const payload: unknown = await response.json();
    return parseApiError(payload, fallback);
  } catch {
    return { message: fallback };
  }
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(apiUrl(path), { ...init, headers, cache: "no-store" });
  if (response.status === 401) {
    clearToken();
  }
  if (!response.ok) {
    const error = await readError(response, `Request failed (${response.status})`);
    throw Object.assign(new Error(actionableMessage(error)), { code: error.code });
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

const ANALYSIS_POLL_MS = 2000;
const ANALYSIS_POLL_MAX_MS = 10 * 60 * 1000;

/** Poll a background analysis job until it completes or fails. */
export async function pollAnalysisJob(jobId: string): Promise<ResumeAnalysisRead> {
  const deadline = Date.now() + ANALYSIS_POLL_MAX_MS;
  while (Date.now() < deadline) {
    const job = await request<AnalysisJobRead>(`/api/v1/resume/analyze-jobs/${jobId}`);
    if (job.status === "completed" && job.analysis) {
      return job.analysis;
    }
    if (job.status === "failed") {
      const error: ApiError = {
        message: job.error_detail ?? "Resume analysis failed",
        code: job.error_code ?? undefined,
      };
      throw Object.assign(new Error(actionableMessage(error)), { code: error.code });
    }
    await new Promise((resolve) => setTimeout(resolve, ANALYSIS_POLL_MS));
  }
  throw new Error(
    "Analysis is still running on the server. Wait a moment and check History, or try again.",
  );
}
