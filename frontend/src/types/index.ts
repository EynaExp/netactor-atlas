export interface Engagement {
  id: string;
  name: string;
  target_scope: Target[];
  status: 'created' | 'running' | 'completed' | 'failed' | 'paused' | 'stopping';
  scan_mode: string;
  enable_exploit: boolean;
  report_level: 'minimal' | 'medium' | 'detailed';
  current_phase: string;
  phase_status: string;
  created_at: string;
  completed_at: string | null;
}

export interface Target {
  type: 'ip' | 'cidr' | 'domain' | 'url';
  value: string;
}

export interface Finding {
  id: string;
  engagement_id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  cvss_score: number | null;
  cwe_id: string | null;
  status: string;
  description: string | null;
  proof: any;
  tool_source: string | null;
  endpoint: string | null;
  remediation: string | null;
  created_at: string;
}

export interface AgentSession {
  id: string;
  engagement_id: string;
  agent_type: string;
  model_url: string | null;
  model_name: string | null;
  status: string;
  tokens_used: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentAction {
  id: string;
  session_id: string;
  action_type: string;
  tool_name: string | null;
  input_data: any;
  output_data: any;
  duration_ms: number | null;
  success: boolean;
  created_at: string;
}

export interface AgentConfig {
  id: string;
  agent_type: string;
  system_prompt: string;
  max_tokens: number;
  temperature: number;
  enabled: boolean;
  allowed_tools?: string[] | null;
}

export interface LLMSettings {
  base_url: string;
  api_key: string;
  model: string;
}

export interface ToolboxConfig {
  name: string;
  executor_type: string;
  container_name: string | null;
  image: string | null;
  ssh_host: string | null;
  ssh_port: number;
  ssh_user: string | null;
  mcp_url: string | null;
  working_dir: string;
  tool_count: number;
}

export interface PhaseLog {
  id: string;
  engagement_id: string;
  phase: string;
  status: string;
  message: string | null;
  details: any;
  created_at: string;
}

export interface WSMessage {
  type: string;
  data: any;
}

export type PhaseType = 'recon' | 'scanner' | 'vuln_analyzer' | 'exploit' | 'report';

export const PHASE_CONFIG: Record<PhaseType, { label: string; icon: string; color: string }> = {
  recon: { label: 'Reconnaissance', icon: 'Search', color: 'blue' },
  scanner: { label: 'Vulnerability Scan', icon: 'Scan', color: 'purple' },
  vuln_analyzer: { label: 'Analysis', icon: 'Shield', color: 'yellow' },
  exploit: { label: 'Exploitation', icon: 'Zap', color: 'red' },
  report: { label: 'Report', icon: 'FileText', color: 'green' },
};
