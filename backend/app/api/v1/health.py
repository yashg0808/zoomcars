"""
Health Check Endpoints
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from app.core.database import get_db
from app.core.redis import get_redis
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> HealthResponse:
    """
    Health check endpoint.
    Checks database and Redis connectivity.
    """
    # Check database
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
    
    # Check Redis
    redis_status = "healthy"
    try:
        await redis_client.ping()
    except Exception:
        redis_status = "unhealthy"
    
    overall_status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version="2.0.0",
        database=db_status,
        redis=redis_status,
        timestamp=datetime.utcnow()
    )


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> dict:
    """
    Kubernetes readiness probe endpoint.
    """
    await db.execute(text("SELECT 1"))
    await redis_client.ping()
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict:
    """
    Kubernetes liveness probe endpoint.
    """
    return {"status": "alive"}
