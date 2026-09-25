from fastapi import APIRouter, status
from app.core.config import settings
from app.schemas.health import ApiRootResponse

router = APIRouter()

@router.get(
    "/",
    response_model=ApiRootResponse,
    status_code=status.HTTP_200_OK,
    summary="DataPilot API v1 Overview",
    description="Returns metadata, versioning, documentation links, and route discovery for DataPilot API v1.",
)
async def api_v1_root() -> ApiRootResponse:
    return ApiRootResponse(
        name=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="DataPilot - AI-Powered Data Intelligence Platform API",
        status="operational",
        docs_url="/docs",
        health_url=f"{settings.API_V1_STR}/health",
        api_v1_prefix=settings.API_V1_STR,
        endpoints={
            "health": f"{settings.API_V1_STR}/health",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        },
    )
