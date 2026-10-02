"""
main.py
FastAPI application entry point.

Startup sequence:
  1. Create all DB tables (idempotent — safe to call repeatedly)
  2. Register all routers
  3. Configure CORS

Run with:
  cd backend
  uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive Swagger UI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_all_tables
from app.routers import auth as auth_router

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=(
        "Context-Aware Hospital Information & Workflow Network — Prototype.\n\n"
        "⚠️ **All data is synthetic.** ML predictions are prototype outputs only "
        "and are NOT medical diagnoses."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────────────────────────────────────
# CORS — allow the Vite dev server (port 3000) to call this API
# ─────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Database table creation — runs once at startup
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    create_all_tables()


# ─────────────────────────────────────────────────────────────────────────────
# Routers — Phase 1: auth only. Phase 2+ adds the rest.
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)


# ─────────────────────────────────────────────────────────────────────────────
# Health check — always available, no auth required
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    """Returns 200 OK. Used to verify the server is running."""
    return {
        "status": "ok",
        "app": settings.APP_TITLE,
        "version": settings.APP_VERSION,
    }
