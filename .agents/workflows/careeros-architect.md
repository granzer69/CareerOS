---
description: Core architectural rules and tech stack constraints for CareerOS. Invoke to understand the core structural rules of the application.
---
# CareerOS Architect rules

This is CareerOS — an AI-powered career operating system.

## Tech Stack
- Python 3.11, FastAPI, SQLAlchemy 2.0 async, PostgreSQL
- Pydantic v2, Alembic, local GGUF inference (`llama-cpp-python` optional extra)

## Key Architectural Rules (Always Apply)
- Never make synchronous database calls
- Never hardcode API keys — use environment variables via `core/config.py`
- All model inference lives in `app/ai/` behind the local adapter
- Do not call hosted LLM or embedding APIs from the CareerOS runtime
- Missing local weights fail closed; never fall back to a hosted provider

## Current Development Phase
- Phase: MVP (Phase 1)
- Active focus: local inference adapter + FastAPI + PostgreSQL models
