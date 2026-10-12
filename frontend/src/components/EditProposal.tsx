import type { ResumeEditRead } from "../types";
import { StatusPill } from "./StatusPill";

export function EditProposal({
  edit,
  busy,
  onAccept,
  onReject,
}: {
  edit: ResumeEditRead;
  busy: boolean;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
}) {
  const canApply = edit.kind === "supported_rewrite";
  return (
    <article className="edit">
      <div>
        <StatusPill value={edit.kind} /> <StatusPill value={edit.status} />
      </div>
      <p>{edit.rationale}</p>
      <div className="diff">
        <div>
          <div className="muted">Original</div>
          <pre>{edit.original_span || "—"}</pre>
        </div>
        <div>
          <div className="muted">Proposed</div>
          <pre>{edit.proposed_text}</pre>
        </div>
      </div>
      <div className="row">
        {canApply ? (
          <button type="button" disabled={busy} onClick={() => onAccept(edit.id)}>
            Accept rewrite
          </button>
        ) : (
          <span className="muted">Not auto-applied.</span>
        )}
        <button className="secondary" type="button" disabled={busy} onClick={() => onReject(edit.id)}>
          Reject
        </button>
      </div>
    </article>
  );
}
