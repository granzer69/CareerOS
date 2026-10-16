import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { analyticsFixture, emptyAnalyticsFixture } from "../test/fixtures";
import { AnalyticsPage } from "./AnalyticsPage";

vi.mock("../api", () => ({
  request: vi.fn(),
}));

import { request } from "../api";

const mockedRequest = vi.mocked(request);

describe("AnalyticsPage", () => {
  beforeEach(() => {
    mockedRequest.mockReset();
  });

  it("shows an empty state instead of fabricated charts when n=0", async () => {
    mockedRequest.mockImplementation(async (path: string) => {
      if (path.includes("/user-profile/me")) {
        throw Object.assign(new Error("not found"), { code: "not_found" });
      }
      return emptyAnalyticsFixture;
    });
    render(
      <MemoryRouter>
        <AnalyticsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: /your evidence, over time/i })).toBeInTheDocument();
    expect(screen.getByText(/run an analysis first/i)).toBeInTheDocument();
    expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument();
    const text = document.body.textContent?.toLowerCase() ?? "";
    expect(text).not.toContain("placement probability");
    expect(text).not.toContain("chance of getting hired");
  });

  it("renders not_found counts and omits null readiness as a dash", async () => {
    mockedRequest.mockImplementation(async (path: string) => {
      if (path.includes("/user-profile/me")) {
        throw Object.assign(new Error("not found"), { code: "not_found" });
      }
      return analyticsFixture;
    });
    render(
      <MemoryRouter>
        <AnalyticsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Evidence mix" })).toBeInTheDocument();
    expect(screen.getByText("not_found")).toBeInTheDocument();
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Kubernetes").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Edit funnel" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence by JD importance" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /coverage matrix by role/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Eligibility constraints" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /profile skills vs jd mentions/i })).toBeInTheDocument();
    expect(screen.getAllByText("Data Engineer").length).toBeGreaterThan(0);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.getByRole("img", { name: /application-readiness trend/i })).toBeInTheDocument();
    const text = document.body.textContent?.toLowerCase() ?? "";
    expect(text).toContain("not a hiring probability");
    expect(text).not.toContain("chance of getting hired");
    expect(text).not.toContain("predicted company");
  });
});
