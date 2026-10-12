import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { analyticsFixture, emptyAnalyticsFixture } from "../test/fixtures";
import { EvidenceMixChart } from "./EvidenceMixChart";

describe("EvidenceMixChart", () => {
  it("renders not_found counts from fixture JSON with a table fallback", () => {
    render(
      <EvidenceMixChart
        buckets={analyticsFixture.evidence}
        requirementCount={analyticsFixture.requirement_count}
        rubricLabel="rubric v1.0.0"
      />,
    );
    expect(screen.getByText("not_found")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Count" })).toBeInTheDocument();
    expect(screen.getByLabelText(/n=3/i)).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows an empty caption when requirement_matches would be empty", () => {
    render(
      <EvidenceMixChart
        buckets={emptyAnalyticsFixture.evidence}
        requirementCount={0}
        rubricLabel="rubric unknown"
      />,
    );
    expect(screen.getByText(/no requirement matches yet/i)).toBeInTheDocument();
  });
});
