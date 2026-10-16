import { ANALYTICS_COPY } from "../copy";
import type { ProfileSkillCoverage } from "../types";
import { ChartFrame } from "./ChartFrame";
import { StatusPill } from "./StatusPill";

export function ProfileSkillCoverageTable({
  rows,
  rubricLabel,
}: {
  rows: ProfileSkillCoverage[];
  rubricLabel: string;
}) {
  const mentionTotal = rows.reduce((sum, row) => sum + row.requirement_mentions, 0);

  return (
    <ChartFrame
      title="Profile skills vs JD mentions"
      definition="For each skill on your profile, counts JD requirement lines whose text mentions that skill string."
      meta={`${rubricLabel} · n=${mentionTotal} requirement mentions · ${ANALYTICS_COPY.profileSkills}`}
      table={
        <table>
          <caption className="sr-only">Profile skill evidence from JD requirement text</caption>
          <thead>
            <tr>
              <th scope="col">Profile skill</th>
              <th scope="col">JD mentions</th>
              <th scope="col">Confirmed</th>
              <th scope="col">Partial</th>
              <th scope="col">Not found</th>
              <th scope="col">Contradicted</th>
              <th scope="col">Unknown</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.skill}>
                <td>{row.skill}</td>
                <td>{row.requirement_mentions}</td>
                <td>
                  <StatusPill value="confirmed" /> {row.confirmed}
                </td>
                <td>
                  <StatusPill value="partial" /> {row.partial}
                </td>
                <td>
                  <StatusPill value="not_found" /> {row.not_found}
                </td>
                <td>
                  <StatusPill value="contradicted" /> {row.contradicted}
                </td>
                <td>
                  <StatusPill value="unknown" /> {row.unknown}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {rows.length === 0 ? (
        <p className="muted">
          Add skills on your <a href="/profile">profile</a> to see how often posting requirements mention
          them in this window.
        </p>
      ) : rows.every((row) => row.requirement_mentions === 0) ? (
        <p className="muted">
          None of your profile skills appeared in JD requirement text on these analyses. That does not
          mean you lack them — only that postings here did not name them explicitly.
        </p>
      ) : null}
    </ChartFrame>
  );
}
