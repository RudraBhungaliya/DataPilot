from fastapi import APIRouter
from app.api.v1.endpoints import health, root, workflows, collection, sources, datasets

api_router = APIRouter()

# Include endpoints
api_router.include_router(root.router, tags=["Root"])
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
api_router.include_router(collection.router, prefix="/collection", tags=["Collection"])
api_router.include_router(sources.router, prefix="/sources", tags=["Sources"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
