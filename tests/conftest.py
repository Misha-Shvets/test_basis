"""Shared test configuration and Dishka fixtures."""

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from dishka import (
    AsyncContainer,
    Provider,
    Scope,
    make_async_container,
    provide,
)
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from config import Settings
from infra.db.models import metadata, outbox_table, payments_table
from infra.db.repositories import (
    SqlAlchemyOutboxRepository,
    SqlAlchemyPaymentRepository,
)
from infra.db.session import (
    create_engine_for,
    create_session_factory,
    session_scope,
)
from payment.ports import PaymentRepository
from payment.services import PaymentService

TEST_SETTINGS = Settings(
    database_url="postgresql+psycopg://payments:payments@postgres:5432/payments",
    rabbit_url="amqp://guest:guest@rabbitmq:5672/",
    api_key="test-api-key",
    debug=True,
)


class TestProvider(Provider):
    """Test-only provider for context-bound settings."""

    __test__ = False
    scope = Scope.RUNTIME

    @provide(scope=Scope.RUNTIME)
    def settings(self) -> Settings:
        """Provide settings for the test environment."""
        return TEST_SETTINGS

    @provide(scope=Scope.APP)
    def engine(self, settings: Settings) -> AsyncEngine:
        """Build the test database engine."""
        return create_engine_for(settings)

    @provide(scope=Scope.APP)
    def session_factory(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        """Build the test database session factory."""
        return create_session_factory(engine)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        """Provide one committed session per request."""
        async for database_session in session_scope(factory):
            yield database_session

    payment_repository = provide(
        SqlAlchemyPaymentRepository,
        scope=Scope.REQUEST,
        provides=PaymentRepository,
    )
    outbox_repository = provide(
        SqlAlchemyOutboxRepository,
        scope=Scope.REQUEST,
    )
    payment_service = provide(PaymentService, scope=Scope.REQUEST)


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Provide PostgreSQL settings for integration tests."""
    return TEST_SETTINGS


@pytest_asyncio.fixture(scope="session")
async def container(settings: Settings) -> AsyncIterator[AsyncContainer]:
    """Create one test DI container for the test session."""
    test_container = make_async_container(
        TestProvider(),
        start_scope=Scope.RUNTIME,
    )
    yield test_container
    await test_container.close()


@pytest_asyncio.fixture(scope="session")
async def database(container: AsyncContainer) -> AsyncIterator[None]:
    """Create and remove the real PostgreSQL schema for the test session."""
    async with container(scope=Scope.APP) as app_container:
        engine = await app_container.get(AsyncEngine)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(metadata.create_all)
        except (OSError, sa_exc.OperationalError) as error:
            await engine.dispose()
            pytest.skip(f"PostgreSQL is unavailable: {error}")
        yield
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)


@pytest_asyncio.fixture
async def request_container(
    container: AsyncContainer,
    database: None,
) -> AsyncIterator[AsyncContainer]:
    """Open one request-scoped Dishka container."""
    async with container(scope=Scope.REQUEST) as request_container:
        yield request_container


@pytest_asyncio.fixture
async def clean_database(request_container: AsyncContainer) -> None:
    """Isolate tests by clearing real database tables."""
    session = await request_container.get(AsyncSession)
    await session.execute(delete(outbox_table))
    await session.execute(delete(payments_table))
    await session.commit()


@pytest_asyncio.fixture
async def app(
    settings: Settings,
    container: AsyncContainer,
) -> AsyncIterator[FastAPI]:
    """Create an API application with the test DI container."""
    from main import create_basic_app

    application = create_basic_app(settings)
    setup_dishka(container, application)
    yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Create an async HTTP client for the ASGI application."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        yield test_client
