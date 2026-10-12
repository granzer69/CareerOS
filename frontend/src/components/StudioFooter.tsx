import { HONESTY_COPY, STUDIO_COPY } from "../copy";

export function StudioFooter({ modelConfigured = false }: { modelConfigured?: boolean }) {
  return (
    <footer className="studio-footer">
      <p>{STUDIO_COPY.footer}</p>
      <p className="footnote">{HONESTY_COPY.notPredictor}</p>
      {modelConfigured ? <p className="footnote">{HONESTY_COPY.modelConfigured}</p> : null}
    </footer>
  );
}
