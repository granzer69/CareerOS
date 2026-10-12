from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCAN_PATHS = [
    ROOT / "app",
    ROOT / "requirements.txt",
    ROOT / "requirements-prod.txt",
    ROOT / "render.yaml",
    ROOT / ".env.example",
]

FORBIDDEN_SNIPPETS = (
    "anthropic",
    "openai",
    "gemini",
    "generativelanguage",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "api.anthropic.com",
    "api.openai.com",
    "claude-sonnet",
    "from_pretrained",
    "huggingface_hub",
    "hf_hub_download",
    "AsyncAnthropic",
)


def _iter_text_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for candidate in path.rglob("*"):
        if candidate.is_file() and candidate.suffix in {".py", ".txt", ".md", ".yml", ".yaml", ".example", ""}:
            files.append(candidate)
        elif candidate.is_file() and candidate.name in {"requirements.txt", "requirements-prod.txt", "render.yaml", ".env.example"}:
            files.append(candidate)
    return files


def test_runtime_has_no_hosted_llm_sdk_or_provider_keys() -> None:
    """Fail if hosted LLM SDKs, provider keys, or hub downloads remain in runtime config."""
    hits: list[str] = []
    for root in SCAN_PATHS:
        for file_path in _iter_text_files(root):
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            lowered = text.lower()
            for snippet in FORBIDDEN_SNIPPETS:
                if snippet.lower() in lowered:
                    relative = file_path.relative_to(ROOT)
                    hits.append(f"{relative}: {snippet}")

    assert hits == [], "Hosted inference markers remain:\n" + "\n".join(hits)
