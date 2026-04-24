export const API_BASE = '/api'; // Using proxy in vite.config.ts

export interface Goal {
  type: string;
  description: string;
}

export interface Run {
  run_id: string;
  status: string;
  updated_at: number;
  goal?: Goal;
}

export interface RunSummary {
  run_id: string;
  status: string;
  cycle_id: number;
  stop_reason: string | null;
  total_actions: number;
  artifact_count: number;
  goal: Goal | null;
  pending_approvals: Record<string, unknown>[];
}

export interface AgentState {
  cycle_id: number;
  active_goal?: Goal;
  active_plan?: Plan;
  active_focus?: unknown[];
  tensions?: unknown[];
  regulation?: Record<string, number>;
  [key: string]: unknown;
}

export interface PlanStep {
  status: string;
  tool_name: string;
  description: string;
}

export interface Plan {
  status: string;
  current_step: number;
  steps: PlanStep[];
}

export interface Artifact {
  title: string;
  type: string;
  created_at: number;
  content: unknown;
}

async function fetchJSON(url: string, options: RequestInit = {}) {
  const response = await fetch(`${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const client = {
  getRuns: () => fetchJSON(`${API_BASE}/runs`),
  getSummary: (id: string) => fetchJSON(`${API_BASE}/runs/${id}/summary`),
  getPlan: (id: string) => fetchJSON(`${API_BASE}/runs/${id}/plan`),
  getArtifacts: (id: string) => fetchJSON(`${API_BASE}/runs/${id}/artifacts`),
  getState: (id: string) => fetchJSON(`${API_BASE}/runs/${id}/state/compact`),
  getApprovals: () => fetchJSON(`${API_BASE}/approvals/pending`),
  getLLMStatus: () => fetchJSON(`${API_BASE}/llm/status`),
  
  createRun: (payload: Record<string, unknown>) => fetchJSON(`${API_BASE}/runs`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  
  pause: (id: string) => fetchJSON(`${API_BASE}/runs/${id}/pause`, { method: 'POST' }),
  resume: (id: string) => fetchJSON(`${API_BASE}/runs/${id}/resume`, { method: 'POST' }),
  stop: (id: string) => fetchJSON(`${API_BASE}/runs/${id}`, { method: 'DELETE' }),
  
  approve: (id: string, actionId: string) => fetchJSON(`${API_BASE}/runs/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ action_id: actionId })
  }),
  
  deny: (id: string, actionId: string) => fetchJSON(`${API_BASE}/runs/${id}/deny`, {
    method: 'POST',
    body: JSON.stringify({ action_id: actionId })
  })
};
