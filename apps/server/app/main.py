from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.core.config import settings
from app.core.logger import logger
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

    yield

    # Clean shutdown
    logger.info(f"🛑 Shutting down {settings.PROJECT_NAME}...")
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
)

# Mount API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root path to API documentation."""
    return RedirectResponse(url="/docs")
