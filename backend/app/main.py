"""
Zoomcar Clone API - Main Application
Production-Ready Car Rental Platform
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging
import uuid
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import settings
from app.core.database import init_db_pool, close_db_pool
from app.core.redis import init_redis_connection, close_redis_connection
from app.api.v1 import auth, cars, bookings, locations, webhooks, health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1,
        integrations=[FastApiIntegration()],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    # Startup
    logger.info("Starting Zoomcar Clone API...")
    await init_db_pool()
    await init_redis_connection()
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db_pool()
    await close_redis_connection()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Zoomcar Clone API",
    description="Production-ready car rental platform API",
    version="2.0.0",
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for tracking"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    logger.info(f"Response: {response.status_code}")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(locations.router, prefix="/api/v1/locations", tags=["Locations"])
app.include_router(cars.router, prefix="/api/v1/cars", tags=["Cars"])
app.include_router(bookings.router, prefix="/api/v1/bookings", tags=["Bookings"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Zoomcar Clone API",
        "version": "2.0.0",
        "status": "operational"
    }
