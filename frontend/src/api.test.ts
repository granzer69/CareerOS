import { afterEach, describe, expect, it, vi } from "vitest";
import { actionableMessage, clearToken, request, setToken } from "./api";

describe("actionableMessage", () => {
  it("explains missing GGUF without naming a hosted provider", () => {
    const message = actionableMessage({
      message: "Local model weights are not available",
      code: "model_unavailable",
    });
    expect(message).toMatch(/GGUF/i);
    expect(message.toLowerCase()).not.toContain("anthropic");
    expect(message.toLowerCase()).not.toContain("openai");
    expect(message.toLowerCase()).not.toContain("gemini");
  });
});

describe("request", () => {
  afterEach(() => {
    clearToken();
    vi.unstubAllGlobals();
  });

  it("clears the stored token on 401", async () => {
    setToken("stale-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        json: async () => ({ detail: { detail: "Not authenticated", code: "unauthorized" } }),
      }),
    );
    await expect(request("/api/v1/resume/analyses")).rejects.toThrow(/session expired/i);
    expect(window.localStorage.getItem("careeros_token")).toBeNull();
  });
});
