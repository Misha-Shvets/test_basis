"""Dishka providers and application dependency registration."""

from collections.abc import AsyncIterator

from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from config import Settings
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


class MainProvider(Provider):
    """Application-wide dependencies."""

    scope = Scope.APP
    settings = from_context(provides=Settings, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def engine(self, settings: Settings) -> AsyncEngine:
        """Build the database engine."""
        return create_engine_for(settings)

    @provide(scope=Scope.APP)
    def session_factory(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        """Build the database session factory."""
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
