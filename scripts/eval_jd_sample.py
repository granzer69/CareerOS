#!/usr/bin/env python3
# Run: PYTHONPATH=/workspace python3 scripts/eval_jd_sample.py
"""Run JD understanding on a sample posting and print a quick quality review."""

from __future__ import annotations

import asyncio
import sys

from app.ai.jd_pipeline import understand_jd_with_model
from app.services.jd_understanding_deterministic import deterministic_jd_understanding

SAMPLE_JD = """
Senior Product Engineer — Campus Hiring Platform
About the role: You will own features that help students match resumes to real job postings.

Responsibilities:
- Design and ship full-stack features with Python/FastAPI and React
- Partner with design to improve onboarding for first-time applicants
- Instrument funnels and fix drop-off on the analyze flow
- Mentor 1-2 interns each term

Requirements:
- 2+ years building web products (internships count)
- Strong Python and SQL; comfortable with REST APIs
- Experience collaborating in GitHub PRs with tests

Nice to have:
- PostgreSQL performance tuning
- Local LLM or GGUF inference experience

Must be authorized to work in the US without sponsorship.
"""

EXPECT_THEMES = (
    "python",
    "react",
    "fastapi",
    "mentor",
    "onboarding",
    "authorized",
)


def _score_output(text: str) -> tuple[int, list[str]]:
    lowered = text.lower()
    missing = [theme for theme in EXPECT_THEMES if theme not in lowered]
    hit = len(EXPECT_THEMES) - len(missing)
    return hit, missing


async def main() -> int:
    role = "Senior Product Engineer"
    print("=== Deterministic baseline ===")
    baseline = deterministic_jd_understanding(target_role=role, job_description=SAMPLE_JD)
    print("objectives:", *baseline.objectives, sep="\n  - ")
    print()

    print("=== Model + merge ===")
    import os

    if os.environ.get("EVAL_SKIP_MODEL") == "1":
        understanding = baseline
        print("(EVAL_SKIP_MODEL=1 — skipped local GGUF call)")
    else:
        try:
            understanding = await understand_jd_with_model(
                target_role=role,
                job_description=SAMPLE_JD,
            )
        except Exception as exc:
            print(f"Model path failed ({exc}); using deterministic baseline.")
            understanding = baseline

    blob = " ".join(
        [understanding.role_summary, *understanding.objectives, *understanding.success_criteria]
    )
    score, missing = _score_output(blob)
    print("role_summary:", understanding.role_summary)
    print("objectives:")
    for item in understanding.objectives:
        print(f"  - {item}")
    print("success_criteria:", understanding.success_criteria)
    print("estimated_level:", understanding.estimated_level)
    print()
    print(f"Theme coverage: {score}/{len(EXPECT_THEMES)}")
    if missing:
        print("Missing themes:", ", ".join(missing))
    return 0 if score >= 4 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
