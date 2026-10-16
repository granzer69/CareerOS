import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfilePage } from "./ProfilePage";

vi.mock("../api", () => ({
  request: vi.fn(),
  getUserId: () => "00000000-0000-0000-0000-000000000001",
}));

import { request } from "../api";

const mockedRequest = vi.mocked(request);

describe("ProfilePage", () => {
  beforeEach(() => {
    mockedRequest.mockReset();
  });

  it("shows create copy when the profile is missing", async () => {
    mockedRequest.mockRejectedValue(Object.assign(new Error("not found"), { code: "not_found" }));
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: /your profile/i })).toBeInTheDocument();
    expect(screen.getByText(/no profile yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create profile/i })).toBeInTheDocument();
  });

  it("loads an existing profile for editing", async () => {
    mockedRequest.mockResolvedValue({
      id: "00000000-0000-0000-0000-000000000123",
      user_id: "00000000-0000-0000-0000-000000000001",
      skills: ["Python"],
      target_role: "Backend Engineer intern",
      experience_level: "student",
      created_at: "2026-10-12T12:00:00.000Z",
    });
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByDisplayValue("Backend Engineer intern")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /update profile/i })).toBeInTheDocument();
  });
});
