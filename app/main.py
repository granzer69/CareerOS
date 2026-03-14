from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

load_dotenv()  # Load .env before anything else

from app.api.routes.auth import router as auth_router
from app.api.routes.resume import router as resume_router
from app.api.routes.roadmap import router as roadmap_router
from app.api.routes.user_profile import router as user_profile_router
from app.core.config import settings
from app.core.startup import verify_database_connection

logger = logging.getLogger(__name__)


app = FastAPI(
    title="CareerOS",
    description="AI-powered career operating system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(resume_router, prefix="/api/v1")
app.include_router(roadmap_router, prefix="/api/v1")
app.include_router(user_profile_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check() -> JSONResponse:
    """Health check used by Render; verifies database connectivity."""
    try:
        await verify_database_connection()
        return JSONResponse({"status": "ok", "database": "connected"})
    except Exception as exc:
        logger.exception("Health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "disconnected"},
        )


# Serve the compiled frontend only in local unified mode.
if not settings.is_production:
    FRONTEND_DIR = Path("frontend/dist")
    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            potential_file = FRONTEND_DIR / full_path
            if full_path and potential_file.is_file():
                return FileResponse(potential_file)

            index_file = FRONTEND_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)

            return JSONResponse(
                status_code=404,
                content={
                    "message": "Frontend build not found. Run `npm run build` in frontend/."
                },
            )
