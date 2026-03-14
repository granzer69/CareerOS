"""Direct test of the resume analyzer — bypasses the HTTP server to see the real error."""
import asyncio
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Set the API key in env for the analyzer
os.environ["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.resume_analyzer import analyze_resume_with_claude

SAMPLE_RESUME = """
Ribhu Sharma
Senior Software Engineer | Python | FastAPI | AI/ML

SUMMARY
Experienced software engineer with 5+ years building scalable backend systems.

WORK EXPERIENCE
Senior Backend Engineer — TechCorp (2022-Present)
- Designed microservices handling 50K+ RPM using FastAPI
- Implemented async data pipelines with SQLAlchemy 2.0

SKILLS
Python, FastAPI, SQLAlchemy, PostgreSQL, Redis, Docker, Claude API

EDUCATION
B.Tech Computer Science — IIT Delhi (2015-2019)
"""

async def main():
    try:
        print("Calling Claude API...")
        result = await analyze_resume_with_claude(
            resume_text=SAMPLE_RESUME,
            target_role="Senior AI/ML Engineer",
        )
        print(f"SUCCESS! Score: {result.overall_score}, Grade: {result.grade}")
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"\nERROR TYPE: {type(e).__name__}")
        print(f"ERROR: {e}")
        traceback.print_exc()

asyncio.run(main())
