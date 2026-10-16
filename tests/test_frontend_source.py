from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"

FORBIDDEN = (
    "placement probability",
    "chance of getting hired",
    "predicted company",
    "will get placed",
    "google, amazon, microsoft",
    "anthropic",
    "openai",
    "gemini",
)


def test_frontend_source_tree_exists() -> None:
    """Slice 6 restores source files instead of editing frontend/dist."""
    assert (SRC / "main.tsx").is_file()
    assert (SRC / "App.tsx").is_file()
    assert (SRC / "pages" / "AnalyzePage.tsx").is_file()
    assert (SRC / "pages" / "AnalysisDetailPage.tsx").is_file()
    assert (ROOT / "frontend" / "vite.config.ts").is_file()


def test_frontend_copy_is_honest() -> None:
    """The copilot UI must not claim hiring probability or company predictions."""
    hits: list[str] = []
    for path in SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".css", ".html"}:
            continue
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN:
            if phrase in text:
                hits.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert hits == []


def test_frontend_uses_bearer_auth_and_real_analysis_fields() -> None:
    """Signed-in copilot talks to JWT routes and renders rubric fields."""
    detail = (SRC / "pages" / "AnalysisDetailPage.tsx").read_text(encoding="utf-8")
    api = (SRC / "api.ts").read_text(encoding="utf-8")
    assert "Authorization" in api
    assert "Bearer" in api
    assert "job_fit_score" in detail
    assert "application-readiness" in detail.lower() or "application_readiness_score" in detail
    assert "model_unavailable" in api
    assert "schema_outdated" in api
    app_source = (SRC / "App.tsx").read_text(encoding="utf-8")
    types_source = (SRC / "types.ts").read_text(encoding="utf-8")
    assert "/analytics" in app_source
    assert "AnalyticsRead" in types_source
    assert "/api/v1/resume/analytics" in (SRC / "pages" / "AnalyticsPage.tsx").read_text(encoding="utf-8")
    assert "/profile" in app_source
    assert "/api/v1/user-profile/me" in (SRC / "pages" / "ProfilePage.tsx").read_text(encoding="utf-8")


def test_checked_in_dist_is_copilot_not_placement_app() -> None:
    """FastAPI serves frontend/dist; that bundle must come from the copilot source."""
    dist = ROOT / "frontend" / "dist"
    index = (dist / "index.html").read_text(encoding="utf-8").lower()
    assert "careeros" in index
    assert "student placement" not in index
    hits: list[str] = []
    assets = dist / "assets"
    assert assets.is_dir()
    for path in assets.iterdir():
        if path.suffix not in {".js", ".css"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN:
            if phrase in text:
                hits.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert hits == []
