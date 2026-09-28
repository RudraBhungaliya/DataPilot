from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.api.v1.endpoints import auth, collection, datasets, health, jobs, root, schedules, sources, workflows

api_router = APIRouter()

# Public (no auth): health and API metadata
api_router.include_router(root.router, tags=["Root"])
api_router.include_router(health.router, tags=["Health"])

# Protected: require an API key when AUTH_ENABLED is on
protected = [Depends(require_api_key)]
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"], dependencies=protected)
api_router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"], dependencies=protected)
api_router.include_router(collection.router, prefix="/collection", tags=["Collection"], dependencies=protected)
api_router.include_router(sources.router, prefix="/sources", tags=["Sources"], dependencies=protected)
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"], dependencies=protected)
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"], dependencies=protected)
api_router.include_router(schedules.router, prefix="/schedules", tags=["Schedules"], dependencies=protected)
