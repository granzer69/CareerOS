export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-card" role="status" aria-live="polite" aria-busy="true">
      <p className="loading-label">{label}</p>
      <div className="loading-skeleton" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
