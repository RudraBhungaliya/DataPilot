from fastapi import APIRouter, status
from app.core.config import settings
from app.schemas.health import HealthResponse, ServiceStatus
from app.db.session import check_database_connection
from app.services.redis import RedisService
from datetime import datetime, timezone

router = APIRouter()

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health Check",
    description="Returns the operational status of the DataPilot API along with PostgreSQL and Redis connectivity.",
)
async def health_check() -> HealthResponse:
    # Check dependencies in parallel/async
    db_connected = await check_database_connection()
    redis_connected = await RedisService.check_connection()

    db_status = "connected" if db_connected else "disconnected"
    redis_status = "connected" if redis_connected else "disconnected"

    # Determine overall status
    if db_connected and redis_connected:
        overall_status = "healthy"
    elif db_connected or redis_connected:
        overall_status = "degraded"
    else:
        overall_status = "healthy" if settings.ENVIRONMENT == "development" else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        services=ServiceStatus(
            database=db_status,
            redis=redis_status,
        ),
    )
