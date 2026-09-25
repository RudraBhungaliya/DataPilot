from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ServiceStatus(BaseModel):
    database: str = Field(..., description="PostgreSQL status: 'connected', 'disconnected', 'not_configured'")
    redis: str = Field(..., description="Redis status: 'connected', 'disconnected', 'not_configured'")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system health status: 'healthy', 'degraded', 'unhealthy'")
    version: str = Field(..., description="DataPilot API version")
    environment: str = Field(..., description="Environment mode e.g. development, production")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of the health check")
    services: ServiceStatus = Field(..., description="Status breakdown of underlying dependencies")


class ApiRootResponse(BaseModel):
    name: str
    version: str
    description: str
    status: str
    docs_url: str
    health_url: str
    api_v1_prefix: str
    endpoints: Dict[str, str] = Field(default_factory=dict)
