from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# .ext.asyncio is a subtoolbox inside sqlalchemy specifically for async db oprns
#AsyncSession is a class rep one convo with the db
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    # echo=false, dont print every sql query to terminal
    echo=settings.debug,
)

# Session factory
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Base - all db tables will inherit from this base to get 
# sqlalchemy superpowers
Base = declarative_base()

# Dependency
# func used by FastAPI to provide DB session to any endpt that needs it
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