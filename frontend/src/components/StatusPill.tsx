export function StatusPill({ value }: { value: string }) {
  return <span className={`pill ${value}`}>{value.replaceAll("_", " ")}</span>;
}
