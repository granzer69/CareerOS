import type { ReactNode } from "react";

export type BannerTone = "error" | "warn" | "ok" | "block";

const ALERT_TONES: BannerTone[] = ["error", "block"];

export function Banner({
  tone,
  children,
}: {
  tone: BannerTone;
  children: ReactNode;
}) {
  const alert = ALERT_TONES.includes(tone);
  return (
    <div className={`banner ${tone}`} role={alert ? "alert" : "status"}>
      {children}
    </div>
  );
}
