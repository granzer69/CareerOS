import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { getToken, request, setToken } from "../api";
import { Banner } from "../components/Banner";
import { HONESTY_COPY } from "../copy";
import type { TokenResponse } from "../types";

export function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (getToken()) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const path = mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const token = await request<TokenResponse>(path, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(token.access_token);
      navigate("/");
    } catch (err) {
      const fallback = err instanceof Error ? err.message : "Sign-in failed";
      setError(fallback);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <div className="brand">
          <strong>CareerOS</strong>
          <span>Sign in to analyze a resume against a job description</span>
        </div>
      </header>
      <main id="main-content">
        <div className="card auth-card">
          <h1>{mode === "login" ? "Sign in" : "Create an account"}</h1>
          <p className="muted">{HONESTY_COPY.notPredictor}</p>
          {error ? <Banner tone="error">{error}</Banner> : null}
          <form className="grid" onSubmit={onSubmit} aria-busy={pending}>
            <label htmlFor="email">
              Email
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
            <label htmlFor="password">
              Password
              <input
                id="password"
                type="password"
                minLength={mode === "register" ? 8 : 1}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            <button type="submit" disabled={pending}>
              {pending ? "Working…" : mode === "login" ? "Sign in" : "Register"}
            </button>
          </form>
          <p>
            <button
              className="secondary"
              type="button"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Need an account?" : "Already registered?"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}
