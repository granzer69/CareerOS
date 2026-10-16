import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "../api";
import { analysisFixture } from "../test/fixtures";
import { AnalyzePage } from "./AnalyzePage";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    request: vi.fn(),
    getToken: () => "test-token",
  };
});

const mockedRequest = vi.mocked(request);

function renderAnalyze() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<AnalyzePage />} />
        <Route path="/analyses/:id" element={<p>Analysis ready</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AnalyzePage", () => {
  beforeEach(() => {
    mockedRequest.mockReset();
  });

  it("scores a resume through the synchronous analyze endpoint", async () => {
    mockedRequest.mockImplementation(async (path: string) => {
      if (path === "/api/v1/user-profile/me") {
        throw new Error("no profile");
      }
      return analysisFixture;
    });
    const user = userEvent.setup();
    renderAnalyze();
    const file = new File(["%PDF-fake"], "cv.pdf", { type: "application/pdf" });
    const input = document.getElementById("resume-file") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await user.type(screen.getByLabelText(/target role/i), "Backend Engineer");
    await user.type(screen.getByLabelText(/job description/i), "Required: Python");
    await user.click(screen.getByRole("button", { name: /run analysis/i }));
    expect(await screen.findByText("Analysis ready")).toBeInTheDocument();
    expect(mockedRequest).toHaveBeenCalledWith(
      "/api/v1/resume/analyze",
      expect.objectContaining({ method: "POST" }),
    );
    expect(screen.queryByText(/local model/i)).not.toBeInTheDocument();
  });

  it("surfaces model_unavailable as an actionable GGUF error", async () => {
    mockedRequest.mockRejectedValue(
      Object.assign(
        new Error(
          "Local GGUF weights are not configured on the API host. Health can still be OK. Set LOCAL_MODEL_PATH to an on-disk file; CareerOS will not download a model or call a hosted LLM.",
        ),
        { code: "model_unavailable" },
      ),
    );
    const user = userEvent.setup();
    renderAnalyze();
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
