import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { getToken, request, setSession } from "../api";
import { Banner } from "../components/Banner";
import { StepList } from "../components/StepList";
import { StudioFooter } from "../components/StudioFooter";
import { HONESTY_COPY, STUDIO_COPY } from "../copy";
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
      setSession(token.access_token, token.user_id);
      navigate("/");
    } catch (err) {
      const fallback = err instanceof Error ? err.message : "Sign-in failed";
      setError(fallback);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="shell auth-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <div className="brand">
          <strong>{STUDIO_COPY.brandMark}</strong>
          <span>{STUDIO_COPY.brandLine}</span>
        </div>
      </header>
      <main id="main-content" className="auth-layout">
        <section className="auth-hero" aria-labelledby="auth-hero-title">
          <p className="eyebrow">{STUDIO_COPY.brandSub}</p>
          <h1 id="auth-hero-title">{STUDIO_COPY.heroTitle}</h1>
          <p className="lead">{STUDIO_COPY.heroLead}</p>
          <p className="muted">{STUDIO_COPY.whoFor}</p>
          <StepList />
          <p className="footnote">{HONESTY_COPY.notPredictor}</p>
        </section>
        <div className="card auth-card">
          <h2>{mode === "login" ? "Sign in" : "Create an account"}</h2>
          <p className="muted">
            Same account for internships, co-ops, and full-time postings. History stays on this account.
          </p>
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
      <StudioFooter />
    </div>
  );
}
