from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    logger.info(f"Attempting to connect to database: {settings.DATABASE_URL}")
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Set to True for debugging SQL queries
        connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {} # Specific to SQLite
    )
    logger.info("Database engine created successfully.")

    AsyncSessionFactory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession
    )
    logger.info("Async session factory configured.")

except Exception as e:
    logger.error(f"Error creating database engine or session factory: {e}", exc_info=True)
    # Depending on your deployment strategy, you might want to exit here
    # exit(1)

class Base(DeclarativeBase):
    pass

async def init_db():
    """Initialize the database and create tables."""
    async with engine.begin() as conn:
        logger.info("Dropping and creating all tables (for development)...")
        # In production, use Alembic for migrations instead of dropping tables
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")


async def get_db() -> AsyncSession:
    """FastAPI dependency to get a DB session."""
    async_session = AsyncSessionFactory()
    try:
        yield async_session
    finally:
        await async_session.close()