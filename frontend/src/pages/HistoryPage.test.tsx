import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { historyFixture } from "../test/fixtures";
import { HistoryPage } from "./HistoryPage";

vi.mock("../api", () => ({
  request: vi.fn(),
}));

import { request } from "../api";

const mockedRequest = vi.mocked(request);

describe("HistoryPage", () => {
  beforeEach(() => {
    mockedRequest.mockReset();
  });

  it("shows an empty state instead of fabricated rows", async () => {
    mockedRequest.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "History" })).toBeInTheDocument();
    expect(screen.getByText(/no analyses yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("row")).not.toBeInTheDocument();
  });

  it("renders owned history rows from the API", async () => {
    mockedRequest.mockResolvedValue(historyFixture);
    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("cv.pdf")).toBeInTheDocument();
    });
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText(/application-readiness/i)).toBeInTheDocument();
  });
});
