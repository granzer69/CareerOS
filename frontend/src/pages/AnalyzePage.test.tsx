import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AnalyzePage } from "./AnalyzePage";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    request: vi.fn(),
    pollAnalysisJob: vi.fn(),
    getToken: () => "test-token",
  };
});

import { pollAnalysisJob, request } from "../api";

const mockedRequest = vi.mocked(request);
const mockedPoll = vi.mocked(pollAnalysisJob);

describe("AnalyzePage", () => {
  beforeEach(() => {
    mockedRequest.mockReset();
    mockedPoll.mockReset();
  });

  it("surfaces model_unavailable as an actionable GGUF error", async () => {
    mockedRequest.mockResolvedValue({
      id: "job-1",
      status: "pending",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      analysis: null,
      error_code: null,
      error_detail: null,
    });
    mockedPoll.mockRejectedValue(
      Object.assign(
        new Error(
          "Local GGUF weights are not configured on the API host. Health can still be OK. Set LOCAL_MODEL_PATH to an on-disk file; CareerOS will not download a model or call a hosted LLM.",
        ),
        { code: "model_unavailable" },
      ),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AnalyzePage />
      </MemoryRouter>,
    );
    const file = new File(["%PDF-fake"], "cv.pdf", { type: "application/pdf" });
    const input = document.getElementById("resume-file") as HTMLInputElement;
    expect(input).toBeTruthy();
    fireEvent.change(input, { target: { files: [file] } });
    await user.type(screen.getByLabelText(/target role/i), "Backend Engineer");
    await user.type(screen.getByLabelText(/job description/i), "Required: Python");
    await user.click(screen.getByRole("button", { name: /run analysis/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/GGUF/i);
    expect(screen.getByRole("alert").textContent?.toLowerCase()).not.toContain("openai");
  });
});
