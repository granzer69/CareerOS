from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.ai.local_inference import (
    LocalInferenceAdapter,
    LocalInferenceError,
    LocalModelNotFoundError,
    build_local_adapter,
)
from app.schemas.resume_analysis import ResumeAnalysisResult

_PROMPT_PATH = Path(__file__).parent / "prompts" / "resume_analysis.txt"
_MAX_RETRIES = 2


def _load_prompt_template() -> str:
    """Load the resume analysis prompt template from disk."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_prompt(*, target_role: str, resume_text: str) -> str:
    """Build the final prompt by interpolating role and resume text into the template."""
    template = _load_prompt_template()
    return template.format(target_role=target_role, resume_text=resume_text)


def _strip_markdown_fences(raw_text: str) -> str:
    """Remove optional markdown code fences around model JSON."""
    stripped = raw_text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = [ln for ln in stripped.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


async def analyze_resume_text(
    *,
    resume_text: str,
    target_role: str,
    adapter: LocalInferenceAdapter | None = None,
) -> ResumeAnalysisResult:
    """
    Analyze resume text with the local inference adapter and validate JSON output.

    Builds a prompt from the saved template, calls the local adapter, parses the
    returned JSON, and validates it against ResumeAnalysisResult. Malformed JSON
    is retried once (two attempts total). Missing weights and inference failures
    are not retried and never fall back to a hosted provider.

    Raises:
        LocalModelNotFoundError: Local weight file is missing.
        LocalInferenceError: Local generation failed.
        ValueError: Model output was not valid analysis JSON after retries.
    """
    inference = adapter if adapter is not None else build_local_adapter()
    prompt = _build_prompt(target_role=target_role, resume_text=resume_text)
    last_error: Exception | None = None

    for _attempt in range(_MAX_RETRIES):
        try:
            raw_text = await inference.complete(prompt)
        except (LocalModelNotFoundError, LocalInferenceError):
            raise
        except Exception as exc:
            raise LocalInferenceError("Local inference failed") from exc

        raw_text = _strip_markdown_fences(raw_text)

        try:
            parsed = json.loads(raw_text)
            return ResumeAnalysisResult.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            continue

    raise ValueError(
        f"Model output was not valid analysis JSON after {_MAX_RETRIES} attempts: {last_error}"
    )
