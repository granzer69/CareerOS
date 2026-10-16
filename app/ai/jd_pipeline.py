from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from app.ai.local_inference import (
    LocalInferenceAdapter,
    LocalInferenceError,
    LocalModelNotFoundError,
    build_local_adapter,
    resolve_local_model_path,
)
from app.ai.resume_analyzer import _coerce_json_object, _escape_braces
from app.schemas.evidence import ModelRequirement, RequirementMatch
from app.schemas.jd_insights import EvidenceBatchResult, JDUnderstanding
from app.services.evidence_matcher import match_requirement, match_requirements

_UNDERSTANDING_PROMPT = Path(__file__).parent / "prompts" / "jd_understanding.txt"
_EVIDENCE_PROMPT = Path(__file__).parent / "prompts" / "evidence_match.txt"
_MAX_RETRIES = 2
_BATCH_SIZE = 8
_MAX_RESUME_CHARS = 14_000
_MAX_JD_EXCERPT_CHARS = 6_000


def _format_objectives(understanding: JDUnderstanding | None) -> str:
    if understanding is None or not understanding.objectives:
        return "(none)"
    return "\n".join(f"- {item}" for item in understanding.objectives)


async def understand_jd_with_model(
    *,
    target_role: str,
    job_description: str,
    adapter: LocalInferenceAdapter | None = None,
) -> JDUnderstanding:
    """
    First pipeline stage: infer role objectives from the JD only.

    Raises LocalModelNotFoundError or LocalInferenceError when weights are missing
    or generation fails. Malformed JSON is retried once.
    """
    inference = adapter if adapter is not None else build_local_adapter(
        resolve_local_model_path("jd")
    )
    template = _UNDERSTANDING_PROMPT.read_text(encoding="utf-8")
    prompt = template.format(
        target_role=_escape_braces(target_role),
        job_description=_escape_braces(job_description),
    )
    last_error: Exception | None = None

    for _attempt in range(_MAX_RETRIES):
        try:
            raw_text = await inference.complete(prompt)
        except (LocalModelNotFoundError, LocalInferenceError):
            raise
        except Exception as exc:
            raise LocalInferenceError("Local inference failed") from exc

        try:
            parsed = json.loads(_coerce_json_object(raw_text))
            return JDUnderstanding.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            continue

    raise ValueError(
        f"Model output was not valid JD understanding JSON after {_MAX_RETRIES} attempts: {last_error}"
    )


def _requirements_batch_json(batch: list[ModelRequirement], start_index: int) -> str:
    payload = [
        {
            "index": start_index + offset,
            "text": item.text,
            "importance": item.importance,
            "category": item.category,
            "is_eligibility": item.is_eligibility,
        }
        for offset, item in enumerate(batch)
    ]
    return json.dumps(payload, ensure_ascii=False)


def _requirement_id(text: str) -> str:
    return "req-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def _match_from_model_item(
    requirement: ModelRequirement,
    *,
    evidence_state: str,
    evidence_span: str | None,
    rationale: str,
) -> RequirementMatch:
    return RequirementMatch(
        id=_requirement_id(requirement.text),
        text=requirement.text,
        category=requirement.category,
        importance=requirement.importance,
        is_eligibility=requirement.is_eligibility,
        evidence_state=evidence_state,  # type: ignore[arg-type]
        evidence_span=evidence_span,
        rationale=rationale,
    )


async def _match_batch_with_model(
    *,
    batch: list[ModelRequirement],
    start_index: int,
    resume_text: str,
    job_description: str,
    understanding: JDUnderstanding,
    adapter: LocalInferenceAdapter,
) -> list[RequirementMatch]:
    template = _EVIDENCE_PROMPT.read_text(encoding="utf-8")
    jd_excerpt = job_description[:_MAX_JD_EXCERPT_CHARS]
    resume_excerpt = resume_text[:_MAX_RESUME_CHARS]
    prompt = template.format(
        role_summary=_escape_braces(understanding.role_summary),
        objectives=_escape_braces(_format_objectives(understanding)),
        job_description_excerpt=_escape_braces(jd_excerpt),
        resume_text=_escape_braces(resume_excerpt),
        requirements_json=_requirements_batch_json(batch, start_index),
    )
    last_error: Exception | None = None

    for _attempt in range(_MAX_RETRIES):
        try:
            raw_text = await inference_complete(adapter, prompt)
        except (LocalModelNotFoundError, LocalInferenceError):
            raise
        except Exception as exc:
            raise LocalInferenceError("Local inference failed") from exc

        try:
            parsed = json.loads(_coerce_json_object(raw_text))
            batch_result = EvidenceBatchResult.model_validate(parsed)
            by_index = {item.requirement_index: item for item in batch_result.matches}
            results: list[RequirementMatch] = []
            for offset, requirement in enumerate(batch):
                index = start_index + offset
                item = by_index.get(index)
                if item is None:
                    results.append(match_requirement(requirement, resume_text))
                    continue
                results.append(
                    _match_from_model_item(
                        requirement,
                        evidence_state=item.evidence_state,
                        evidence_span=item.evidence_span,
                        rationale=item.rationale,
                    )
                )
            return results
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            continue

    raise ValueError(
        f"Model output was not valid evidence JSON after {_MAX_RETRIES} attempts: {last_error}"
    )


async def inference_complete(adapter: LocalInferenceAdapter, prompt: str) -> str:
    """Thin wrapper so tests can patch batch completion."""
    return await adapter.complete(prompt)


async def match_requirements_with_model(
    *,
    requirements: list[ModelRequirement],
    resume_text: str,
    job_description: str,
    understanding: JDUnderstanding,
    adapter: LocalInferenceAdapter | None = None,
) -> list[RequirementMatch]:
    """
    Semantic evidence pass: batched local-model judgments aligned to JD objectives.

    Falls back to lexical matching for a batch when JSON is invalid after retries.
    """
    if not requirements:
        return []

    inference = adapter if adapter is not None else build_local_adapter(
        resolve_local_model_path("evidence")
    )
    merged: list[RequirementMatch] = []
    for start in range(0, len(requirements), _BATCH_SIZE):
        batch = requirements[start : start + _BATCH_SIZE]
        try:
            merged.extend(
                await _match_batch_with_model(
                    batch=batch,
                    start_index=start,
                    resume_text=resume_text,
                    job_description=job_description,
                    understanding=understanding,
                    adapter=inference,
                )
            )
        except (LocalModelNotFoundError, LocalInferenceError, ValueError):
            merged.extend(match_requirements(batch, resume_text))
    return merged


async def match_requirements_hybrid(
    *,
    requirements: list[ModelRequirement],
    resume_text: str,
    job_description: str,
    understanding: JDUnderstanding | None,
) -> tuple[list[RequirementMatch], str]:
    """
    Prefer semantic multi-stage matching when a JD understanding exists and weights are configured.

    Returns matches and evidence_method label for persistence.
    """
    if understanding is None:
        return match_requirements(requirements, resume_text), "lexical_fallback"

    try:
        semantic = await match_requirements_with_model(
            requirements=requirements,
            resume_text=resume_text,
            job_description=job_description,
            understanding=understanding,
        )
        return semantic, "semantic_model"
    except LocalModelNotFoundError:
        return match_requirements(requirements, resume_text), "lexical_fallback"
    except LocalInferenceError:
        return match_requirements(requirements, resume_text), "lexical_fallback"
