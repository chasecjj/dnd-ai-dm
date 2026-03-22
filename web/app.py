"""FastAPI application factory for Quest Mirror.

Creates the ASGI app that runs alongside the Discord bot, serving the
React SPA and providing REST + WebSocket endpoints for the solo-mode
web companion.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web.auth import check_passphrase, clear_all_tokens

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEB_PORT = int(os.getenv("QUEST_MIRROR_PORT", "8642"))

# ---------------------------------------------------------------------------
# Pydantic models for auth endpoint
# ---------------------------------------------------------------------------


class AuthRequest(BaseModel):
    passphrase: str


class AuthResponse(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Quest Mirror starting on port %d", WEB_PORT)
    yield
    clear_all_tokens()
    logger.info("Quest Mirror shut down — all tokens cleared")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""

    app = FastAPI(
        title="Quest Mirror",
        version="0.1.0",
        lifespan=lifespan,
    )

    # -- CORS ---------------------------------------------------------------
    origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
    ]
    extra = os.getenv("QUEST_MIRROR_CORS_ORIGINS", "")
    if extra:
        origins.extend(o.strip() for o in extra.split(",") if o.strip())

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Auth endpoint ------------------------------------------------------

    @app.post("/api/auth", response_model=AuthResponse)
    async def auth(body: AuthRequest) -> AuthResponse:
        token = check_passphrase(body.passphrase)
        if token is None:
            raise HTTPException(status_code=401, detail="Invalid passphrase")
        return AuthResponse(token=token)

    # -- REST routes (Task 6) -----------------------------------------------
    try:
        from web.routes import router  # noqa: WPS433

        app.include_router(router, prefix="/api")
    except ImportError:
        logger.warning("web.routes not available yet — REST routes skipped")

    # -- WebSocket handler (Task 7) -----------------------------------------
    try:
        from web.ws_handler import register_ws  # noqa: WPS433

        register_ws(app)
    except ImportError:
        logger.warning("web.ws_handler not available yet — WebSocket skipped")

    # -- SPA static files ---------------------------------------------------
    # NOTE: Mount at /app instead of / to avoid intercepting WebSocket routes.
    # Starlette 0.52+ StaticFiles with html=True at / can block WebSocket upgrades.
    spa_dir = os.path.join(os.path.dirname(__file__), "..", "quest-mirror", "dist")
    if os.path.isdir(spa_dir):
        app.mount("/app", StaticFiles(directory=spa_dir, html=True), name="spa")
        logger.info("Serving SPA from %s (at /app)", spa_dir)
    else:
        logger.info("SPA directory not found (%s) — static serving disabled", spa_dir)

    return app
