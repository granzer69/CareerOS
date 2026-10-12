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
from app.schemas.evidence import RequirementMatch
from app.schemas.resume_edit import ModelEditBatch

_PROMPT_PATH = Path(__file__).parent / "prompts" / "resume_edits.txt"
_MAX_RETRIES = 2


def _load_prompt_template() -> str:
    """Load the resume-edit prompt template from disk."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _escape_braces(value: str) -> str:
    """Keep user text from being interpreted as str.format placeholders."""
    return value.replace("{", "{{").replace("}", "}}")


def _format_matches(matches: list[RequirementMatch]) -> str:
    if not matches:
        return "(none)"
    lines = [
        f"- {match.id}: [{match.evidence_state}/{match.importance}] {match.text}"
        for match in matches[:40]
    ]
    return "\n".join(lines)


def _build_prompt(
    *,
    target_role: str,
    job_description: str,
    resume_text: str,
    matches: list[RequirementMatch],
) -> str:
    """Build the edit prompt from the saved template."""
    template = _load_prompt_template()
    return template.format(
        target_role=_escape_braces(target_role),
        job_description=_escape_braces(job_description),
        resume_text=_escape_braces(resume_text),
        requirement_matches=_escape_braces(_format_matches(matches)),
    )


def _strip_markdown_fences(raw_text: str) -> str:
    """Remove optional markdown code fences around model JSON."""
    stripped = raw_text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = [ln for ln in stripped.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


async def propose_edits_with_model(
    *,
    resume_text: str,
    target_role: str,
    job_description: str,
    matches: list[RequirementMatch],
    adapter: LocalInferenceAdapter | None = None,
) -> ModelEditBatch:
    """
    Ask the local model for grounded span rewrites. Scores are rejected by schema.

    Malformed JSON is retried once. Missing weights and inference failures are not
    retried and never fall back to a hosted provider.
    """
    inference = adapter if adapter is not None else build_local_adapter()
    prompt = _build_prompt(
        target_role=target_role,
        job_description=job_description,
        resume_text=resume_text,
        matches=matches,
    )
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
            return ModelEditBatch.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            continue

    raise ValueError(
        f"Model output was not valid edit JSON after {_MAX_RETRIES} attempts: {last_error}"
    )
