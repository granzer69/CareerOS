import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { supportedEdit, unsupportedEdit } from "../test/fixtures";
import { EditProposal } from "./EditProposal";

describe("EditProposal", () => {
  it("exposes Accept only for supported rewrites", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    const { rerender } = render(
      <EditProposal edit={supportedEdit} busy={false} onAccept={onAccept} onReject={onReject} />,
    );
    expect(screen.getByRole("button", { name: "Accept rewrite" })).toBeInTheDocument();

    rerender(
      <EditProposal edit={unsupportedEdit} busy={false} onAccept={onAccept} onReject={onReject} />,
    );
    expect(screen.queryByRole("button", { name: "Accept rewrite" })).not.toBeInTheDocument();
    expect(screen.getByText("Not auto-applied.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });
});
