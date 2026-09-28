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
  workflow_definition?: WorkflowDefinition | null;
  status: string;
  error?: string | null;
  execution_metadata?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export type StepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED' | 'HUMAN_ACTION_REQUIRED';

export type StepType =
  | 'PARSE_REQUIREMENT'
  | 'DISCOVER_SOURCES'
  | 'COLLECT_DATA'
  | 'EXTRACT_DATA'
  | 'NORMALIZE_DATA'
  | 'VALIDATE_DATA'
  | 'DEDUPLICATE_DATA'
  | 'BUILD_DATASET'
  | 'EXPORT_DATA';

export interface WorkflowStep {
  id: string;
  name: string;
  type: StepType;
  description: string;
  order: number;
  depends_on: string[];
  config: Record<string, any>;
  status: StepStatus;
  input?: any;
  output?: any;
  error?: string | null;
  metadata: Record<string, any>;
}

export type WorkflowStatus =
  | 'DRAFT'
  | 'PARSED'
  | 'CONFIRMED'
  | 'PLANNED'
  | 'RUNNING'
  | 'PAUSED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export interface WorkflowDefinition {
  workflow_id: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  input_requirement: StructuredRequirement;
  steps: WorkflowStep[];
  metadata: Record<string, any>;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PlanWorkflowResponse {
  success: boolean;
  workflow?: WorkflowDefinition | null;
  error?: string | null;
}

export interface ExecuteWorkflowResponse {
  success: boolean;
  workflow?: WorkflowDefinition | null;
  error?: string | null;
}

export interface WorkflowStepsResponse {
  workflow_id: string;
  status: WorkflowStatus;
  steps: WorkflowStep[];
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

export async function planWorkflow(
  requirement: StructuredRequirement,
  prompt?: string,
  workflowId?: string
): Promise<PlanWorkflowResponse> {
  try {
    const res = await fetch(`${API_BASE}/workflows/plan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        requirement,
        prompt,
        workflow_id: workflowId,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      return {
        success: false,
        error: data.detail || 'Unable to plan workflow.',
      };
    }
    return data;
  } catch (err: any) {
    return {
      success: false,
      error: 'Failed to communicate with workflow planning service.',
    };
  }
}

export async function executeWorkflow(workflowId: string): Promise<ExecuteWorkflowResponse> {
  try {
    const res = await fetch(`${API_BASE}/workflows/${workflowId}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await res.json();
    if (!res.ok) {
      return {
        success: false,
        error: data.detail || 'Workflow execution failed.',
      };
    }
    return data;
  } catch (err: any) {
    return {
      success: false,
      error: 'Failed to trigger workflow execution.',
    };
  }
}

export async function fetchWorkflowDefinition(workflowId: string): Promise<WorkflowRecord | null> {
  try {
    const res = await fetch(`${API_BASE}/workflows/${workflowId}`, {
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchWorkflowSteps(workflowId: string): Promise<WorkflowStepsResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/workflows/${workflowId}/steps`, {
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
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

// ============================================================================
// Phase 4: Source Collection Engine Interfaces & APIs
// ============================================================================

export interface SourceDefinition {
  id: string;
  name: string;
  domain: string;
  type: string;
  access_method: string;
  status: string;
  tier: number;
  rate_limit_per_minute: number;
  requires_auth: boolean;
  supports_pagination: boolean;
  success_rate: number;
  metadata?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface CollectionJob {
  id: string;
  request_id: string;
  workflow_id?: string | null;
  status: string;
  collection_request?: Record<string, any>;
  discovered_sources?: any[];
  selected_sources?: any[];
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  errors?: any[];
  source?: Record<string, any> | null;
  current_step?: string | null;
  progress?: number;
  human_action_required?: boolean;
  human_action_reason?: string | null;
  checkpoint?: Record<string, any> | null;
  metadata?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}


export interface RawDocument {
  id: string;
  job_id: string;
  source_id: string;
  url: string;
  canonical_url: string;
  content_type: string;
  content?: string;
  content_hash: string;
  status_code: number;
  collected_at: string;
  metadata?: Record<string, any>;
}

export async function fetchSources(): Promise<SourceDefinition[]> {
  try {
    const res = await fetch(`${API_BASE}/sources`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchCollectionJobs(): Promise<CollectionJob[]> {
  try {
    const res = await fetch(`${API_BASE}/collection/jobs`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchDocuments(jobId?: string): Promise<RawDocument[]> {
  try {
    const url = jobId
      ? `${API_BASE}/collection/documents?job_id=${encodeURIComponent(jobId)}`
      : `${API_BASE}/collection/documents`;
    const res = await fetch(url, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function testDiscoverSources(params: {
  query: string;
  domain?: string;
  entity?: string;
}): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/collection/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function triggerDirectCollection(requestPayload: any): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/collection/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestPayload),
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function fetchCollectionJob(jobId: string): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/collection/jobs/${encodeURIComponent(jobId)}`, {
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function resumeCollectionJob(jobId: string): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/collection/jobs/${encodeURIComponent(jobId)}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch (err: any) {
    return { ok: false, error: err.message };
  }
}


