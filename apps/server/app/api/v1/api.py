from fastapi import APIRouter
from app.api.v1.endpoints import health, root, workflows

api_router = APIRouter()

# Include endpoints
api_router.include_router(root.router, tags=["Root"])
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
