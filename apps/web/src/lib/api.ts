export interface HealthData {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  environment: string;
  timestamp: string;
  services: {
    database: string;
    redis: string;
  };
}

export interface ApiRootData {
  name: string;
  version: string;
  description: string;
  status: string;
  docs_url: string;
  health_url: string;
  api_v1_prefix: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function fetchHealth(): Promise<HealthData | null> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      return {
        status: 'unhealthy',
        version: '0.1.0',
        environment: 'offline',
        timestamp: new Date().toISOString(),
        services: { database: 'disconnected', redis: 'disconnected' },
      };
    }
    return await res.json();
  } catch (error) {
    return {
      status: 'unhealthy',
      version: '0.1.0',
      environment: 'offline',
      timestamp: new Date().toISOString(),
      services: { database: 'disconnected', redis: 'disconnected' },
    };
  }
}

export async function fetchApiRoot(): Promise<ApiRootData | null> {
  try {
    const res = await fetch(`${API_BASE}/`, {
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
