import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { apiUrl, clearToken, getToken } from "./api";
import { Banner } from "./components/Banner";
import { StudioFooter } from "./components/StudioFooter";
import { HONESTY_COPY, STUDIO_COPY } from "./copy";
import { AnalysisDetailPage } from "./pages/AnalysisDetailPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AnalyzePage } from "./pages/AnalyzePage";
import { AuthPage } from "./pages/AuthPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ProfilePage } from "./pages/ProfilePage";
import type { HealthStatus } from "./types";

function RequireAuth() {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell />;
}

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    void fetch(apiUrl("/health"))
      .then(async (response) => {
        const body = (await response.json()) as HealthStatus;
        setHealth(body);
        if (!response.ok) {
          setHealthError("The API is up enough to answer, but the database is not healthy.");
        }
      })
      .catch(() => {
        setHealthError("Cannot reach the API. Check BACKEND_URL / CORS and that the backend is running.");
      });
  }, []);

  function logout(event: FormEvent) {
    event.preventDefault();
    clearToken();
    navigate("/login");
  }

  const modelMissing = health?.local_model === "missing";
  const modelConfigured = health?.local_model === "configured";
  const onAnalytics = location.pathname === "/analytics";
  const onProfile = location.pathname === "/profile";
  const wideShell = onAnalytics || onProfile;

  return (
    <div className={wideShell ? "shell shell-wide" : "shell"}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <Link className="brand" to="/">
          <strong>{STUDIO_COPY.brandMark}</strong>
          <span>{STUDIO_COPY.brandLine}</span>
        </Link>
        <nav aria-label="Primary">
          <Link to="/" aria-current={location.pathname === "/" ? "page" : undefined}>
            Analyze
          </Link>
          <Link
            to="/history"
            aria-current={location.pathname === "/history" ? "page" : undefined}
          >
            History
          </Link>
          <Link
            to="/analytics"
            aria-current={onAnalytics ? "page" : undefined}
          >
            Analytics
          </Link>
          <Link to="/profile" aria-current={onProfile ? "page" : undefined}>
            Profile
          </Link>
          <button className="secondary" type="button" onClick={logout}>
            Sign out
          </button>
        </nav>
      </header>
      {healthError ? <Banner tone="error">{healthError}</Banner> : null}
      {modelMissing ? <Banner tone="warn">{HONESTY_COPY.modelMissing}</Banner> : null}
      <main id="main-content">
        <Outlet />
      </main>
      <StudioFooter modelConfigured={modelConfigured} />
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<AnalyzePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/analyses/:analysisId" element={<AnalysisDetailPage />} />
      </Route>
    </Routes>
  );
}
