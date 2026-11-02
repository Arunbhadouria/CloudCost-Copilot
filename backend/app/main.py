"""Main FastAPI application for CloudCost Copilot."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import init_db
from app.routers import datasets, costs, detect, recommendations, eval, anomalies, chat, audit, gcp_sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="CloudCost Copilot API",
    description="GCP-first cloud cost optimizer backend.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for development and frontend web UI (supports cross-domain deployments)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"^https?:\/\/.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Exception handler for consistent error formats
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(exc)}}
    )

# Include Routers
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(costs.router, prefix="/api/v1")
app.include_router(detect.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(eval.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(gcp_sync.router, prefix="/api/v1")
