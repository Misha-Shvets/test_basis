"""Application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from api.payments import router as payments_router
from config import Settings
from ioc import MainProvider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Release application resources on shutdown."""
    yield
    container = app.state.dishka_container
    await (await container.get(AsyncEngine)).dispose()
    await container.close()


def create_basic_app(settings: Settings) -> FastAPI:
    """Create a FastAPI application without building a DI container."""
    app = FastAPI(
        title="Payment System",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(payments_router, prefix="/api/v1")
    return app


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a FastAPI application with Dishka integration."""
    settings = settings or Settings.from_env()
    app = create_basic_app(settings)
    container = make_async_container(
        MainProvider(),
        context={Settings: settings},
    )
    setup_dishka(container, app)
    return app


def run() -> None:
    """Run the development server."""
    uvicorn.run("main:create_app", factory=True, reload=True)


app = create_app()
