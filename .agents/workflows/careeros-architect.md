---
description: Core architectural rules and tech stack constraints for CareerOS. Invoke to understand the core structural rules of the application.
---
# CareerOS Architect rules

This is CareerOS — an AI-powered career operating system.

## Tech Stack
- Python 3.11, FastAPI, SQLAlchemy 2.0 async, PostgreSQL
- Redis, Anthropic Claude API, Pydantic v2, Alembic, Next.js 14.

## Key Architectural Rules (Always Apply)
- Never make synchronous database calls
- Never hardcode API keys — use environment variables via `core/config.py`
- All Claude API calls live in `app/ai/` only
- Progress tracking uses event sourcing — append only, never UPDATE
- Roadmaps are versioned — new AI analysis creates a new version row
- Every Claude API call must save a `context_snapshot` to the database

## Current Development Phase
- Phase: MVP (Phase 1)
- Active focus: FastAPI skeleton + Claude integration + PostgreSQL models
