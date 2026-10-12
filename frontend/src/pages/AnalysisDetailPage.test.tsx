import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SCORE_COPY } from "../copy";
import { analysisFixture, supportedEdit, unsupportedEdit } from "../test/fixtures";
import { AnalysisDetailPage } from "./AnalysisDetailPage";

vi.mock("../api", () => ({
  request: vi.fn(),
}));

import { request } from "../api";

const mockedRequest = vi.mocked(request);

describe("AnalysisDetailPage", () => {
  beforeEach(() => {
    mockedRequest.mockReset();
    mockedRequest.mockImplementation(async (path: string) => {
      if (path.endsWith("/edits")) {
        return [supportedEdit, unsupportedEdit];
      }
      if (path.endsWith("/versions")) {
        return [];
      }
      return analysisFixture;
    });
  });

  it("renders rubric score captions and only accepts supported rewrites", async () => {
    render(
      <MemoryRouter initialEntries={[`/analyses/${analysisFixture.id}`]}>
        <Routes>
          <Route path="/analyses/:analysisId" element={<AnalysisDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "cv.pdf" })).toBeInTheDocument();
    expect(screen.getByText(SCORE_COPY.fit)).toBeInTheDocument();
    expect(screen.getByText(SCORE_COPY.alignment)).toBeInTheDocument();
    expect(screen.getByText(SCORE_COPY.readiness)).toBeInTheDocument();
    expect(screen.getByText(SCORE_COPY.terminology)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Accept rewrite" })).toHaveLength(1);
    expect(screen.getByText("Not auto-applied.")).toBeInTheDocument();
  });
});
