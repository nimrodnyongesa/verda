from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth as auth_routes
from .api import (
    cases,
    exports,
    folders,
    generation,
    health,
    mcp,
    outputs,
    profile,
)
from .config import CORS_ORIGINS
from .db import initialize_db


def create_app() -> FastAPI:
    initialize_db()
    app = FastAPI(
        title="Verda",
        description="Codex-built litigation toolkits for human rights defenders.",
        version="0.2.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(generation.router, prefix="/api")
    app.include_router(outputs.router, prefix="/api")
    app.include_router(exports.router, prefix="/api")
    app.include_router(mcp.router, prefix="/api")
    app.include_router(folders.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    from .config import HOST, PORT

    uvicorn.run("wakili.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
