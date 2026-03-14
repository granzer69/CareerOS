from __future__ import annotations

import json
from pathlib import Path

import anthropic
from pydantic import ValidationError

from app.core.config import settings
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


async def analyze_resume_with_claude(
    *,
    resume_text: str,
    target_role: str,
) -> ResumeAnalysisResult:
    """
    Send extracted resume text to Claude for analysis and return validated results.

    Builds a prompt from the saved template, calls the Claude API, parses the
    returned JSON, and validates it against ResumeAnalysisResult.  If Claude
    returns malformed JSON the call is retried once (total of 2 attempts).

    Raises:
        ValueError: If Claude returns invalid JSON after all retry attempts.
        anthropic.APIError: If the Claude API itself returns an error.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set in environment / .env")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    prompt = _build_prompt(target_role=target_role, resume_text=resume_text)

    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = message.content[0].text.strip()

        # Strip markdown fences if Claude wraps the JSON
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            # Remove first and last fence lines
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            raw_text = "\n".join(lines).strip()

        try:
            parsed = json.loads(raw_text)
            return ResumeAnalysisResult.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            continue

    raise ValueError(
        f"Claude returned malformed JSON after {_MAX_RETRIES} attempts: {last_error}"
    )
