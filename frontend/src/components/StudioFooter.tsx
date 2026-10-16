import { HONESTY_COPY, STUDIO_COPY } from "../copy";

export function StudioFooter({ modelConfigured = false }: { modelConfigured?: boolean }) {
  const buildId =
    typeof __APP_BUILD_ID__ === "string" && __APP_BUILD_ID__.length > 0 ? __APP_BUILD_ID__ : null;
  return (
    <footer className="studio-footer">
      <p>{STUDIO_COPY.footer}</p>
      {buildId ? <p className="footnote">UI build {buildId}</p> : null}
      <p className="footnote">{HONESTY_COPY.notPredictor}</p>
      {modelConfigured ? <p className="footnote">{HONESTY_COPY.modelConfigured}</p> : null}
    </footer>
  );
}
