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

export interface LocationConstraint {
  country?: string | null;
  state?: string | null;
  city?: string | null;
  region?: string | null;
  raw?: string | null;
}

export interface TimeConstraint {
  type?: string | null;
  value?: number | string | null;
  unit?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  raw_text?: string | null;
}

export interface FilterRule {
  field: string;
  operator: string;
  value: any;
}

export interface StructuredRequirement {
  objective: string;
  entity: string;
  location?: LocationConstraint | null;
  time_constraint?: TimeConstraint | null;
  required_fields: string[];
  filters: FilterRule[];
  source_preferences: string[];
  output_format: 'table' | 'json' | 'csv';
  confidence_score?: number;
  is_ambiguous?: boolean;
  clarification_needed?: string | null;
}

export interface RequirementParseResponse {
  success: boolean;
  requirement?: StructuredRequirement | null;
  workflow_id?: string | null;
  clarification_needed?: string | null;
  error?: string | null;
}

export interface WorkflowRecord {
  id: string;
  prompt: string;
  parsed_requirement?: StructuredRequirement | null;
  status: string;
  created_at: string;
  updated_at: string;
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

export async function parseRequirement(prompt: string): Promise<RequirementParseResponse> {
  try {
    const res = await fetch(`${API_BASE}/workflows/parse`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ prompt }),
    });

    const data = await res.json();

    if (!res.ok) {
      return {
        success: false,
        error: data.detail || 'Unable to understand this requirement. Please try again.',
      };
    }

    return data;
  } catch (err: any) {
    return {
      success: false,
      error: 'Unable to connect to AI requirement engine. Please check your network and backend server.',
    };
  }
}

export async function createWorkflow(
  prompt: string,
  requirement: StructuredRequirement
): Promise<WorkflowRecord | null> {
  try {
    const res = await fetch(`${API_BASE}/workflows`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt,
        requirement,
        status: 'CONFIRMED',
      }),
    });

    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchWorkflows(): Promise<WorkflowRecord[]> {
  try {
    const res = await fetch(`${API_BASE}/workflows`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}
