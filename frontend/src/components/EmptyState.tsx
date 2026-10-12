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
      <h1>{title}</h1>
      <div>{children}</div>
      {action ? <p>{action}</p> : null}
    </div>
  );
}
