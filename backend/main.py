
"""
BloodConnect API — FastAPI backend.

Run locally:
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Serves the REST API only; the frontend/ folder is static HTML/CSS/JS.
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import auth, donors, requests as blood_requests, telegram

load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start the BloodConnect API.

    Telegram background polling is disabled on this web service
    to prevent duplicate getUpdates polling conflicts (HTTP 409).
    Telegram REST API routes remain registered.
    """
    logger.info(
        "BloodConnect API starting. "
        "Automatic Telegram polling is disabled on this service."
    )

    yield

    logger.info("BloodConnect API shutting down.")


app = FastAPI(
    title="BloodConnect API",
    description=(
        "Smart Blood Donation & Emergency Request Platform "
        "— Mini Project, CIT-4, 2026-27."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# CORS configuration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register existing API routers.
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
                        "field": ".".join(
                            str(part) for part in error["loc"][1:]
                        ),
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
    logger.exception(
        "Unhandled application exception",
        exc_info=exc,
    )
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
    return {
        "status": "ok",
        "service": "bloodconnect-api",
    }
