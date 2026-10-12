export function isSessionExpiredError(err: unknown): boolean {
  if (!err || typeof err !== "object") {
    return false;
  }
  const code = "code" in err ? String((err as { code?: string }).code) : "";
  const message = err instanceof Error ? err.message : "";
  return code === "unauthorized" || code === "invalid_token" || message.includes("session expired");
}
