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
  assumptions?: string[];
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

/**
 * API key handling. The key is stored in localStorage and sent as X-API-Key on
 * every request, so the UI works whether or not AUTH_ENABLED is turned on.
 */
export function getApiKey(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('datapilot_api_key');
}

export function setApiKey(key: string | null): void {
  if (typeof window === 'undefined') return;
  if (key) window.localStorage.setItem('datapilot_api_key', key);
  else window.localStorage.removeItem('datapilot_api_key');
}

function authHeaders(): Record<string, string> {
  const key = getApiKey();
  return key ? { 'X-API-Key': key } : {};
}

export async function fetchHealth(): Promise<HealthData | null> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
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
      headers: authHeaders(),
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
        ...authHeaders(),
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
        ...authHeaders(),
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
        ...authHeaders(),
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
      headers: authHeaders(),
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
      headers: authHeaders(),
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
        ...authHeaders(),
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
      headers: authHeaders(),
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

export interface SourceRateLimit {
  requests?: number;
  period_seconds?: number;
  min_interval?: number;
  max_concurrency?: number;
}

export interface SourceDefinition {
  id: string;
  source_id: string;
  name: string;
  type: string;
  base_url: string;
  domain: string;
  capabilities: string[];
  access_method: string;
  status: string;
  rate_limit?: SourceRateLimit;
  metadata?: Record<string, any>;
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
  document_id: string;
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
      headers: authHeaders(),
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
      headers: authHeaders(),
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchDocuments(jobId: string): Promise<RawDocument[]> {
  try {
    const res = await fetch(
      `${API_BASE}/collection/jobs/${encodeURIComponent(jobId)}/documents?limit=50`,
      { cache: 'no-store', headers: authHeaders() }
    );
    if (!res.ok) return [];
    const data = await res.json();
    return data.documents ?? [];
  } catch {
    return [];
  }
}

export async function fetchRecentDocuments(): Promise<RawDocument[]> {
  try {
    const res = await fetch(`${API_BASE}/collection/documents?limit=50`, { cache: 'no-store', headers: authHeaders() });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function createCollectionJob(
  collectionRequest: Record<string, any>
): Promise<{ ok: boolean; status: number; data: any }> {
  try {
    const res = await fetch(`${API_BASE}/collection/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ collection_request: collectionRequest }),
    });
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch (err: any) {
    return { ok: false, status: 0, data: { error: err.message } };
  }
}

export async function discoverJobSources(
  jobId: string
): Promise<{ ok: boolean; status: number; data: any }> {
  try {
    const res = await fetch(`${API_BASE}/collection/jobs/${encodeURIComponent(jobId)}/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
    });
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch (err: any) {
    return { ok: false, status: 0, data: { error: err.message } };
  }
}

export async function executeCollectionJob(
  jobId: string
): Promise<{ ok: boolean; status: number; data: any }> {
  try {
    const res = await fetch(`${API_BASE}/collection/jobs/${encodeURIComponent(jobId)}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
    });
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch (err: any) {
    return { ok: false, status: 0, data: { error: err.message } };
  }
}

export async function fetchCollectionJob(jobId: string): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/collection/jobs/${encodeURIComponent(jobId)}`, {
      cache: 'no-store',
      headers: authHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function resumeCollectionJob(jobId: string, skipSource: boolean = false): Promise<any> {
  try {
    const res = await fetch(
      `${API_BASE}/collection/jobs/${encodeURIComponent(jobId)}/resume?skip_source=${skipSource}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
      }
    );
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch (err: any) {
    return { ok: false, error: err.message };
  }
}

export async function resumeWorkflow(workflowId: string, skipSource: boolean = false): Promise<ExecuteWorkflowResponse> {
  try {
    const res = await fetch(`${API_BASE}/workflows/${workflowId}/resume?skip_source=${skipSource}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
    });
    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Workflow resume failed.' };
    }
    return data;
  } catch (err: any) {
    return { success: false, error: 'Failed to resume workflow.' };
  }
}

// ============================================================================
// Phase 5: Data Intelligence Pipeline - Datasets
// ============================================================================

export interface DatasetSummary {
  id: string;
  workflow_id?: string | null;
  name: string;
  entity: string;
  description?: string | null;
  schema_fields: string[];
  output_format: string;
  status: string;
  version: number;
  is_latest: boolean;
  record_count: number;
  valid_count: number;
  duplicate_count: number;
  metadata?: Record<string, any>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DatasetRecord {
  record_id: string;
  entity: string;
  data: Record<string, any>;
  source_document_id?: string | null;
  source_id?: string | null;
  source_url?: string | null;
  extraction_method: string;
  confidence: number;
  is_valid: boolean;
  validation_errors: string[];
  missing_fields: string[];
  completeness: number;
  dedupe_key?: string | null;
  is_duplicate: boolean;
}

export async function fetchDatasets(): Promise<DatasetSummary[]> {
  try {
    const res = await fetch(`${API_BASE}/datasets`, { cache: 'no-store', headers: authHeaders() });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchDataset(datasetId: string): Promise<DatasetSummary | null> {
  try {
    const res = await fetch(`${API_BASE}/datasets/${encodeURIComponent(datasetId)}`, { cache: 'no-store', headers: authHeaders() });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDatasetRecords(
  datasetId: string,
  opts: {
    q?: string;
    field?: string;
    value?: string;
    sort?: string;
    order?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  } = {}
): Promise<{ total: number; count: number; records: DatasetRecord[] }> {
  try {
    const params = new URLSearchParams();
    if (opts.q) params.set('q', opts.q);
    if (opts.field) params.set('field', opts.field);
    if (opts.value !== undefined) params.set('value', opts.value);
    if (opts.sort) params.set('sort', opts.sort);
    params.set('order', opts.order ?? 'asc');
    params.set('limit', String(opts.limit ?? 50));
    params.set('offset', String(opts.offset ?? 0));

    const res = await fetch(
      `${API_BASE}/datasets/${encodeURIComponent(datasetId)}/records?${params.toString()}`,
      { cache: 'no-store', headers: authHeaders() }
    );
    if (!res.ok) return { total: 0, count: 0, records: [] };
    const data = await res.json();
    return { total: data.total ?? 0, count: data.count ?? 0, records: data.records ?? [] };
  } catch {
    return { total: 0, count: 0, records: [] };
  }
}

export interface EvidenceItem {
  source: string;
  source_type: string;
  reference: string;
  excerpt?: string | null;
  verification_status: string;
}

export interface RecordEvidence {
  record_id: string;
  entity: string;
  data: Record<string, any>;
  extraction_method: string;
  confidence: number;
  completeness: number;
  missing_fields: string[];
  evidence: EvidenceItem[];
  document?: Record<string, any> | null;
  source?: Record<string, any> | null;
}

export async function fetchRecordEvidence(
  datasetId: string,
  recordId: string
): Promise<RecordEvidence | null> {
  try {
    const res = await fetch(
      `${API_BASE}/datasets/${encodeURIComponent(datasetId)}/records/${encodeURIComponent(recordId)}/evidence`,
      { cache: 'no-store', headers: authHeaders() }
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export function datasetExportUrl(datasetId: string, format: 'csv' | 'json' | 'jsonl'): string {
  return `${API_BASE}/datasets/${encodeURIComponent(datasetId)}/export/${format}`;
}

// ============================================================================
// Phase 7: Background jobs + API keys
// ============================================================================

export interface BackgroundJob {
  id: string;
  kind: string;
  status: string;
  payload?: Record<string, any>;
  result?: Record<string, any> | null;
  error?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export async function fetchJobs(limit: number = 50): Promise<BackgroundJob[]> {
  try {
    const res = await fetch(`${API_BASE}/jobs?limit=${limit}`, {
      cache: 'no-store',
      headers: authHeaders(),
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchQueueStats(): Promise<{ depth: number }> {
  try {
    const res = await fetch(`${API_BASE}/jobs/stats`, {
      cache: 'no-store',
      headers: authHeaders(),
    });
    if (!res.ok) return { depth: 0 };
    return await res.json();
  } catch {
    return { depth: 0 };
  }
}

export async function executeWorkflowAsync(
  workflowId: string
): Promise<{ id: string; kind: string; status: string } | null> {
  try {
    const res = await fetch(`${API_BASE}/workflows/${workflowId}/execute-async`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export interface ApiKeyRecord {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at?: string | null;
  last_used_at?: string | null;
}

export async function fetchApiKeys(): Promise<ApiKeyRecord[]> {
  try {
    const res = await fetch(`${API_BASE}/auth/keys`, {
      cache: 'no-store',
      headers: authHeaders(),
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function createApiKey(
  name: string
): Promise<({ api_key: string } & ApiKeyRecord) | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function revokeApiKey(keyId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/keys/${encodeURIComponent(keyId)}`, {
      method: 'DELETE',
      headers: { ...authHeaders() },
    });
    return res.ok;
  } catch {
    return false;
  }
}




