from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()
Base = declarative_base()


def get_engine():
    """
    Creates a fresh async engine.
    Called inside each Celery worker process to avoid
    event loop conflicts from prefork process model.
    """
    return create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        echo=settings.debug,
    )


def get_session_factory(engine):
    return sessionmaker(
        engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


# Module-level engine for FastAPI (single process, no fork issue)
engine = get_engine()
AsyncSessionLocal = get_session_factory(engine)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()