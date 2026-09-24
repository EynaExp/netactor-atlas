import { Engagement, Finding, AgentSession, AgentAction, AgentConfig, LLMSettings, ToolboxConfig, PhaseLog } from '../types';

const API_BASE = '/api';

export function getToken(): string | null {
  return localStorage.getItem('netactor_token');
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem('netactor_token', token);
  } else {
    localStorage.removeItem('netactor_token');
  }
}

export function onUnauthorized(cb: () => void) {
  unauthorizedCb = cb;
}
let unauthorizedCb: (() => void) | null = null;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (res.status === 401) {
    setToken(null);
    unauthorizedCb?.();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API Error ${res.status}: ${err}`);
  }
  return res.json();
}

// Auth
export const login = async (username: string, password: string) => {
  const data = await request<{ access_token: string; role: string; username: string }>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ username, password }) }
  );
  setToken(data.access_token);
  return data;
};

export const logout = () => setToken(null);

export const getMe = () => request<{ id: string; username: string; role: string }>('/auth/me');

export const listUsers = () => request<{ id: string; username: string; role: string; created_at: string }[]>('/auth/users');

export const createUser = (username: string, password: string, role: string) =>
  request<any>('/auth/users', { method: 'POST', body: JSON.stringify({ username, password, role }) });

export const updateUser = (id: string, data: { password?: string; role?: string }) =>
  request<any>(`/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });

export const deleteUser = (id: string) =>
  request<any>(`/auth/users/${id}`, { method: 'DELETE' });

// Scan control
export const stopEngagement = (id: string) =>
  request<any>(`/engagements/${id}/stop`, { method: 'POST' });

export const retryEngagement = (id: string) =>
  request<any>(`/engagements/${id}/retry`, { method: 'POST' });

export const changePassword = (oldPassword: string, newPassword: string) =>
  request<any>('/auth/password', { method: 'PUT', body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }) });

export const getAuditLogs = () =>
  request<{ id: string; username: string; action: string; details: any; created_at: string }[]>('/audit-logs');

// Tool states
export const getToolStates = () =>
  request<{ tool_name: string; enabled: boolean; description?: string; category?: string }[]>('/tools/states');

export const setToolState = (toolName: string, enabled: boolean) =>
  request<any>(`/tools/states/${toolName}`, { method: 'PUT', body: JSON.stringify({ enabled }) });

// Engagements
export const createEngagement = (data: any) =>
  request<Engagement>('/engagements', { method: 'POST', body: JSON.stringify(data) });

export const listEngagements = () =>
  request<Engagement[]>('/engagements');

export const getEngagement = (id: string) =>
  request<Engagement>(`/engagements/${id}`);

export const deleteEngagement = (id: string) =>
  request<any>(`/engagements/${id}`, { method: 'DELETE' });

export const runEngagement = (id: string, enableExploit = false, autoApprove = true) =>
  request<any>(`/engagements/${id}/run?enable_exploit=${enableExploit}&auto_approve=${autoApprove}`, { method: 'POST' });

export const approvePhase = (engagementId: string, phase: string) =>
  request<any>(`/engagements/${engagementId}/approve/${phase}`, { method: 'POST' });

// Sessions & Actions
export const getEngagementSessions = (id: string) =>
  request<AgentSession[]>(`/engagements/${id}/sessions`);

export const getEngagementActions = (id: string, full = false) =>
  request<AgentAction[]>(`/engagements/${id}/actions${full ? '?full=true' : ''}`);

export const getActionDetail = (engagementId: string, actionId: string) =>
  request<AgentAction>(`/engagements/${engagementId}/actions/${actionId}`);

export const getEngagementFindings = (id: string) =>
  request<Finding[]>(`/engagements/${id}/findings`);

export const getEngagementLogs = (id: string) =>
  request<PhaseLog[]>(`/engagements/${id}/logs`);

export const getEngagementReports = (id: string) =>
  request<{ id: string; engagement_id: string; level: string; content: string; summary?: string; docx_path?: string; pdf_path?: string; created_at?: string }[]>(`/engagements/${id}/reports`);

export const exportReport = (engagementId: string, reportId: string, format: string = 'markdown') =>
  `${API_BASE}/engagements/${engagementId}/reports/${reportId}/export?format=${format}`;

// Agent Configs
export const getAgentConfigs = () =>
  request<AgentConfig[]>('/agents/configs');

export const getAgentConfig = (type: string) =>
  request<AgentConfig>(`/agents/configs/${type}`);

export const updateAgentConfig = (type: string, data: Partial<AgentConfig>) =>
  request<AgentConfig>(`/agents/configs/${type}`, { method: 'PUT', body: JSON.stringify(data) });

// LLM Settings
export const getLLMSettings = () =>
  request<LLMSettings>('/settings/llm');

export const updateLLMSettings = (data: Partial<LLMSettings>) =>
  request<LLMSettings>('/settings/llm', { method: 'PUT', body: JSON.stringify(data) });

export const testLLMConnection = () =>
  request<{ success: boolean; model?: string; tokens_used?: number; error?: string }>('/settings/llm/test', { method: 'POST' });

// ATLAS external API (admin key management)
export const getAtlasKey = () =>
  request<{ configured: boolean; key?: string; prefix?: string; header: string }>('/atlas/key');

export const generateAtlasKey = () =>
  request<{ configured: boolean; key: string; prefix: string; header: string }>('/atlas/key', { method: 'POST' });

export const revokeAtlasKey = () =>
  request<{ status: string }>('/atlas/key', { method: 'DELETE' });

export const getNvdKey = () =>
  request<{ configured: boolean; key?: string }>('/atlas/nvd-key');

export const saveNvdKey = (api_key: string) =>
  request<{ status: string }>('/atlas/nvd-key', { method: 'POST', body: JSON.stringify({ api_key }) });

export const revokeNvdKey = () =>
  request<{ status: string }>('/atlas/nvd-key', { method: 'DELETE' });

// Toolbox
export const listToolboxes = () =>
  request<ToolboxConfig[]>('/toolboxes');

export const addToolbox = (data: any) =>
  request<ToolboxConfig>('/toolboxes', { method: 'POST', body: JSON.stringify(data) });

export const deleteToolbox = (name: string) =>
  request<any>(`/toolboxes/${name}`, { method: 'DELETE' });

export const testToolbox = (name: string, command: string) =>
  request<any>('/toolboxes/test', { method: 'POST', body: JSON.stringify({ name, command }) });

// Tools
export const listTools = () =>
  request<any[]>('/tools');

// CLI
export const executeCLI = (toolbox: string, command: string, timeout = 60) =>
  request<any>('/cli/execute', { method: 'POST', body: JSON.stringify({ toolbox, command, timeout }) });

// Asset Inventory
export const listAssets = (host?: string, assetType?: string) => {
  const params = new URLSearchParams();
  if (host) params.append('host', host);
  if (assetType) params.append('asset_type', assetType);
  const qs = params.toString();
  return request<any[]>(`/assets${qs ? '?' + qs : ''}`);
};

export const getAsset = (id: string) =>
  request<any>(`/assets/${id}`);

export const updateAsset = (id: string, data: { notes?: string; owner?: string }) =>
  request<any>(`/assets/${id}`, { method: 'PUT', body: JSON.stringify(data) });

export const getAssetChanges = (engagementId: string) =>
  request<any[]>(`/assets/changes/${engagementId}`);

// WebSocket
export function createWS(engagementId: string, onMessage: (msg: any) => void): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/${engagementId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onerror = (e) => console.error('WebSocket error:', e);
  return ws;
}
