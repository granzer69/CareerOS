import type { RequirementMatch } from "../types";
import { StatusPill } from "./StatusPill";

export function RequirementTable({ matches }: { matches: RequirementMatch[] }) {
  if (matches.length === 0) {
    return <p className="muted">No extracted requirements for this job description.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th scope="col">Requirement</th>
          <th scope="col">Importance</th>
          <th scope="col">State</th>
          <th scope="col">Rationale</th>
        </tr>
      </thead>
      <tbody>
        {matches.map((match) => (
          <tr key={match.id}>
            <td>{match.text}</td>
            <td>{match.importance}</td>
            <td>
              <StatusPill value={match.evidence_state} />
            </td>
            <td>
              {match.rationale}
              {match.evidence_span ? (
                <div className="footnote">span: {match.evidence_span}</div>
              ) : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
