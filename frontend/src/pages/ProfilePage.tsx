import { FormEvent, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getUserId, request } from "../api";
import { isSessionExpiredError } from "../authRedirect";
import { Banner } from "../components/Banner";
import { LoadingState } from "../components/LoadingState";
import { PROFILE_COPY } from "../copy";
import type { ExperienceLevel, UserProfileCreate, UserProfileRead, UserProfileUpdate } from "../types";

const LEVELS: ExperienceLevel[] = ["student", "junior", "mid"];

export function ProfilePage() {
  const userId = getUserId();
  const [loading, setLoading] = useState(true);
  const [exists, setExists] = useState(false);
  const [skillsText, setSkillsText] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel>("student");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }
    void request<UserProfileRead>("/api/v1/user-profile/me")
      .then((profile) => {
        setExists(true);
        setSkillsText(profile.skills.join(", "));
        setTargetRole(profile.target_role);
        setExperienceLevel(profile.experience_level);
      })
      .catch((err: unknown) => {
        if (isSessionExpiredError(err)) {
          setExpired(true);
          return;
        }
        const code = (err as { code?: string }).code;
        if (code === "not_found") {
          setExists(false);
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load profile");
      })
      .finally(() => setLoading(false));
  }, [userId]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!userId) {
      setError("Sign in again — your user id is missing from this browser.");
      return;
    }
    const skills = skillsText
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!targetRole.trim()) {
      setError("Target role is required.");
      return;
    }
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      if (exists) {
        const payload: UserProfileUpdate = {
          skills,
          target_role: targetRole.trim(),
          experience_level: experienceLevel,
        };
        await request<UserProfileRead>(`/api/v1/user-profile/${userId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        const payload: UserProfileCreate = {
          user_id: userId,
          skills,
          target_role: targetRole.trim(),
          experience_level: experienceLevel,
        };
        await request<UserProfileRead>(`/api/v1/user-profile/${userId}`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setExists(true);
      }
      setNotice("Profile saved.");
    } catch (err) {
      if (isSessionExpiredError(err)) {
        setExpired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Could not save profile");
    } finally {
      setPending(false);
    }
  }

  if (expired) {
    return <Navigate to="/login" replace />;
  }
  if (!userId) {
    return <Navigate to="/login" replace />;
  }
  if (loading) {
    return <LoadingState label="Loading profile…" />;
  }

  return (
    <div className="card profile-page">
      <p className="eyebrow">Owner-scoped</p>
      <h1>{PROFILE_COPY.title}</h1>
      <p className="muted">{PROFILE_COPY.lead}</p>
      {!exists ? <p className="footnote">{PROFILE_COPY.missing}</p> : null}
      {error ? <Banner tone="error">{error}</Banner> : null}
      {notice ? <Banner tone="ok">{notice}</Banner> : null}
      <form className="grid" onSubmit={onSubmit} aria-busy={pending}>
        <label htmlFor="profile-skills">
          Skills
          <input
            id="profile-skills"
            value={skillsText}
            onChange={(event) => setSkillsText(event.target.value)}
            placeholder="e.g. Python, React, SQL"
          />
          <span className="footnote">{PROFILE_COPY.skillsHint}</span>
        </label>
        <label htmlFor="profile-role">
          Default target role
          <input
            id="profile-role"
            value={targetRole}
            onChange={(event) => setTargetRole(event.target.value)}
            maxLength={200}
            required
          />
        </label>
        <label htmlFor="profile-level">
          Experience level
          <select
            id="profile-level"
            value={experienceLevel}
            onChange={(event) => setExperienceLevel(event.target.value as ExperienceLevel)}
          >
            {LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
          <span className="footnote">{PROFILE_COPY.experience}</span>
        </label>
        <button type="submit" disabled={pending}>
          {pending ? "Saving…" : exists ? "Update profile" : "Create profile"}
        </button>
      </form>
    </div>
  );
}
