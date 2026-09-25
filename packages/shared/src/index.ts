/**
 * DataPilot - Shared Constants and Types
 */

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  environment: string;
  timestamp: string;
  database: 'connected' | 'disconnected' | 'not_configured';
  redis: 'connected' | 'disconnected' | 'not_configured';
  uptime_seconds?: number;
}

export interface ApiRootInfo {
  project_name: string;
  version: string;
  status: string;
  docs_url: string;
  health_url: string;
  api_v1_prefix: string;
}

export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: string;
  description?: string;
}

export const APP_CONFIG = {
  appName: 'DataPilot',
  appDescription: 'AI-Powered Data Intelligence Platform',
  version: '0.1.0',
  defaultApiUrl: 'http://localhost:8000/api/v1',
} as const;
