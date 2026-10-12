import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { apiUrl, clearToken, getToken } from "./api";
import { AnalysisDetailPage } from "./pages/AnalysisDetailPage";
import { AnalyzePage } from "./pages/AnalyzePage";
import { AuthPage } from "./pages/AuthPage";
import { HistoryPage } from "./pages/HistoryPage";
import type { HealthStatus } from "./types";

function RequireAuth() {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell />;
}

function AppShell() {
  const navigate = useNavigate();
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

  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" to="/">
          <strong>CareerOS</strong>
          <span>JD-driven resume copilot</span>
        </Link>
        <nav>
          <Link to="/">Analyze</Link>
          <Link to="/history">History</Link>
          <button className="secondary" type="button" onClick={logout}>
            Sign out
          </button>
        </nav>
      </header>
      {healthError ? <div className="banner error">{healthError}</div> : null}
      {modelMissing ? (
        <div className="banner warn">
          Local model: not configured. Analysis and edit generation need a GGUF file on the API host
          (`LOCAL_MODEL_PATH`). Missing weights return 503 `model_unavailable` — CareerOS does not
          call a hosted LLM and will not download weights for you.
        </div>
      ) : null}
      {health?.local_model === "configured" ? (
        <div className="banner ok">Local model file is present. Scores still come from rubric v1.0.0, not the model.</div>
      ) : null}
      <Outlet />
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
        <Route path="/analyses/:analysisId" element={<AnalysisDetailPage />} />
      </Route>
    </Routes>
  );
}
