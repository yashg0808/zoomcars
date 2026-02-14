"""
Database Configuration and Connection Management
Using SQLAlchemy async with PostgreSQL
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)

# For Lambda, use NullPool to avoid connection issues
lambda_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models"""
    pass


async def init_db_pool():
    """Initialize database connection pool"""
    logger.info("Initializing database connection pool...")
    # Test connection
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)
    logger.info("Database connection pool initialized")


async def close_db_pool():
    """Close database connection pool"""
    logger.info("Closing database connection pool...")
    await engine.dispose()
    logger.info("Database connection pool closed")


async def get_db() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
