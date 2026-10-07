import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from backend.app.api import (
    ask,
    bot_changes,
    bots,
    files,
    github,
    graph,
    project_brain,
    repos,
    runs,
    settings,
    wiki,
)
from backend.app.config import get_settings
from backend.app.frontend import mount_frontend
from backend.app.security import ProjectSecurityMiddleware
from backend.app.services.bot_changes.watcher import start_documentation_watcher


def create_app() -> FastAPI:
    app_settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        watcher = (
            start_documentation_watcher(app_settings)
            if app_settings.bot_documentation_watch_enabled else None
        )
        try:
            yield
        finally:
            if watcher is not None:
                watcher.cancel()
                with suppress(asyncio.CancelledError):
                    await watcher

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def private_validation_error(
        request: Request, exc: RequestValidationError,
    ) -> Response:
        if request.url.path == "/api/bots" or request.url.path.startswith("/api/bots/"):
            # Pydantic's input/context can contain request-only provider credentials.
            errors = [
                {"loc": error["loc"], "type": error["type"], "msg": "Invalid field value"}
                for error in exc.errors()
            ]
            return JSONResponse(status_code=422, content={"detail": errors})
        return await request_validation_exception_handler(request, exc)
    app.add_middleware(ProjectSecurityMiddleware, settings=app_settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(repos.router, prefix="/api/repos", tags=["repos"])
    app.include_router(files.router, prefix="/api/repos", tags=["files"])
    app.include_router(graph.router, prefix="/api/repos", tags=["graph"])
    app.include_router(wiki.router, prefix="/api/repos", tags=["wiki"])
    app.include_router(ask.router, prefix="/api/repos", tags=["ask"])
    app.include_router(runs.router, prefix="/api/repos", tags=["runs"])
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
    app.include_router(github.router, prefix="/api/github", tags=["github"])
    app.include_router(project_brain.router, prefix="/api/repos", tags=["project-brain"])
    app.include_router(bots.router, prefix="/api/bots", tags=["bots"])
    app.include_router(bot_changes.router, prefix="/api/bots", tags=["bot-changes"])

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_frontend(app)

    return app


app = create_app()
