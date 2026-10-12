import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SCORE_COPY } from "../copy";
import { ScoreCard } from "./ScoreCard";

describe("ScoreCard", () => {
  it("shows the definition caption and an em dash when the value is missing", () => {
    render(
      <ScoreCard label="Job-fit" value={null} note={SCORE_COPY.fit} rubricVersion="v1.0.0" />,
    );
    expect(screen.getByText("Job-fit")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText(SCORE_COPY.fit)).toBeInTheDocument();
    expect(screen.getByText("Rubric v1.0.0")).toBeInTheDocument();
  });
});
