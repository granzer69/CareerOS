import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthPage } from "./AuthPage";

vi.mock("../api", () => ({
  request: vi.fn(),
  getToken: () => null,
  setToken: vi.fn(),
}));

describe("AuthPage", () => {
  it("states that CareerOS is not a placement predictor", () => {
    render(
      <MemoryRouter>
        <AuthPage />
      </MemoryRouter>,
    );
    const text = document.body.textContent?.toLowerCase() ?? "";
    expect(text).toContain("not a placement predictor");
    expect(text).not.toContain("placement probability");
    expect(text).not.toContain("chance of getting hired");
    expect(text).not.toContain("predicted company");
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });
});
