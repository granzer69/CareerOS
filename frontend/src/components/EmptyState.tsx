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
      <p className="eyebrow">Owner-scoped</p>
      <h1>{title}</h1>
      <div className="empty-state-body">{children}</div>
      {action ? <p className="empty-state-action">{action}</p> : null}
    </div>
  );
}
