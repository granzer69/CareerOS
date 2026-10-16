import type { ReactNode } from "react";

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="card empty-state">
      <div className="empty-state-icon" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="8" y="6" width="24" height="28" rx="3" stroke="currentColor" strokeWidth="2" />
          <path d="M13 14h14M13 20h14M13 26h9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </div>
      <p className="eyebrow">Owner-scoped</p>
      <h1>{title}</h1>
      <div className="empty-state-body">{children}</div>
      {action ? <p className="empty-state-action">{action}</p> : null}
    </div>
  );
}
