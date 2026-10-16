import { STUDIO_COPY } from "../copy";

const STEPS = [
  { n: "1", title: "Upload", body: STUDIO_COPY.stepUpload },
  { n: "2", title: "Role", body: STUDIO_COPY.stepRole },
  { n: "3", title: "Job description", body: STUDIO_COPY.stepJd },
  { n: "4", title: "Review evidence", body: STUDIO_COPY.stepRead },
] as const;

export function StepList() {
  return (
    <ol className="step-list">
      {STEPS.map((step) => (
        <li key={step.n}>
          <span className="step-index" aria-hidden="true">
            {step.n}
          </span>
          <div>
            <strong>{step.title}</strong>
            <p>{step.body}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
