from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, PlainTextResponse
from app.core.config import settings
from app.core.logger import logger
from app.core.observability import ObservabilityMiddleware, metrics
from app.core.rate_limit import RateLimitMiddleware
from app.api.v1.api import api_router
from app.services.redis import RedisService
from app.db.session import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown event handling."""
    logger.info(f"🚀 Initializing {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    logger.info(f"🔌 Allowed CORS Origins: {settings.BACKEND_CORS_ORIGINS}")
    
    # Optional early database & redis initialization (non-blocking)
    await init_db()
    try:
        redis_client = await RedisService.get_client()
        logger.info("Redis service client initialized.")
    except Exception as e:
        logger.warning(f"Initial Redis setup warning: {e}")

    # Start the embedded background worker (disable when running a dedicated worker)
    worker_task = None
    if settings.RUN_EMBEDDED_WORKER:
        try:
            from app.jobs.worker import get_worker
            worker_task = asyncio.create_task(get_worker().run_forever())
            logger.info("Embedded background worker started.")
        except Exception as e:
            logger.warning(f"Could not start embedded worker: {e}")

    yield

    # Clean shutdown
    logger.info(f"🛑 Shutting down {settings.PROJECT_NAME}...")
    if worker_task is not None:
        try:
            from app.jobs.worker import get_worker
            get_worker().stop()
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        except Exception as e:
            logger.warning(f"Worker shutdown warning: {e}")
    # Close shared collection engine network clients (only if it was instantiated)
    try:
        from app.collection.dependencies import get_collection_service
        if get_collection_service.cache_info().currsize:
            await get_collection_service().aclose()
    except Exception as e:
        logger.warning(f"Collection engine shutdown warning: {e}")
    await RedisService.close()
    await engine.dispose()
    logger.info("Database and Redis connections gracefully disposed.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-Powered Data Intelligence Platform Backend API",
    version=settings.VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time-Ms"],
)

# Observability (timing + metrics)
app.add_middleware(ObservabilityMiddleware)

# Rate limiting (outermost: rejects before work is done)
app.add_middleware(RateLimitMiddleware)

# Mount API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/metrics", include_in_schema=False)
async def get_metrics():
    """Prometheus-format process metrics."""
    if not settings.METRICS_ENABLED:
        return PlainTextResponse("metrics disabled\n", status_code=404)
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root path to API documentation."""
    return RedirectResponse(url="/docs")
