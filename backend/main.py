
"""
BloodConnect API — FastAPI backend.

Run locally:
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Serves the REST API only; the frontend/ folder is static HTML/CSS/JS.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import auth, donors, requests as blood_requests, telegram
from utils.telegram_bot import telegram_polling_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the Telegram bot with the FastAPI application."""
    telegram_task = None

    if os.getenv("TELEGRAM_BOT_TOKEN"):
        logger.info("Starting BloodConnect Telegram bot...")
        telegram_task = asyncio.create_task(telegram_polling_loop())
    else:
        logger.warning(
            "Telegram bot not started: TELEGRAM_BOT_TOKEN is not configured."
        )

    try:
        yield
    finally:
        if telegram_task:
            telegram_task.cancel()
            try:
                await telegram_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="BloodConnect API",
    description=(
        "Smart Blood Donation & Emergency Request Platform "
        "— Mini Project, CIT-4, 2026-27."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# CORS setup: frontend is served separately during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register existing routers.
app.include_router(auth.router)
app.include_router(donors.router)
app.include_router(blood_requests.router)
app.include_router(telegram.router)


# Centralized exception handlers.

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "status_code": exc.status_code,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Validation failed",
                "status_code": 422,
                "fields": [
                    {
                        "field": ".".join(str(part) for part in error["loc"][1:]),
                        "issue": error["msg"],
                    }
                    for error in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception("Unhandled application exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Something went wrong. Please try again.",
                "status_code": 500,
            }
        },
    )


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "service": "bloodconnect-api"}
