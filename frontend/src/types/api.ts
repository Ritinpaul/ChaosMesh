export interface HealthResponse {
  status: string
  version: string
  ollama_available: boolean
  openrouter_available?: boolean
  redis_connected: boolean
  active_episode: string | null
  uptime_seconds: number
}

export interface Service {
  error_rate_percent: number
  p99_latency_ms: number
  healthy: boolean
}

export interface ClusterState {
  services: Record<string, Service>
  pods: Record<string, any>
  network_health: number
}

export interface Incident {
  incident_id: string
  title: string
  description: string
  level: number
  affected_pods: string[]
  affected_services: string[]
  root_cause: string
  detected_at: number
}

export interface AgentBelief {
  confidence: number
  findings?: string[]
  hypotheses?: string[]
  hypothesis?: string
  supporting_evidence?: string[]
}

export interface EnvState {
  episode_id: string
  step: number
  current_level: number
  cumulative_reward: number
  sim_time_minutes?: number
  episode_status?: string
  cluster_state: ClusterState
  active_incidents: Incident[]
  all_beliefs: Record<string, AgentBelief>
  all_messages: any[]
  reward_history: number[] | any[]
  difficulty_state: {
    consecutive_successes: number
    total_episodes: number
    success_threshold: number
  }
}

export interface ResetResponse {
  episode_id: string
  observation: {
    active_incidents: Incident[]
    cluster_state: ClusterState
  }
}

export interface AgentAction {
  agent: 'diagnostics' | 'remediation' | 'security' | 'database' | 'incident_commander'
  action_type:
    | 'query_metrics'
    | 'get_logs'
    | 'run_kubectl'
    | 'run_sql'
    | 'isolate_network'
    | 'restart_pod'
    | 'scale_deployment'
    | 'rollback_deployment'
    | 'declare_resolved'
    | 'send_message'
  target?: string
}

export interface StepRequest {
  episode_id: string
  action: AgentAction
}

export interface StepResponse {
  observation: EnvState
  reward: {
    total: number
  } | number
  terminated: boolean
  truncated: boolean
  info: Record<string, any>
}

export interface InjectRequest {
  scenario_key?: string
  description: string
  level: number
}

export interface InjectResponse {
  success?: boolean
  incident_id: string
  title: string
  level?: number
  affected_pods: string[]
  affected_services?: string[]
}

export interface DemoScenario {
  name: string
  description: string
  level: number
}

export interface DemoScenarioListResponse {
  scenarios: Record<string, DemoScenario>
  recommended: Record<
    string,
    {
      scenario_key: string
      name: string
      description: string
      level: number
    }
  >
  all_scenarios: Record<string, DemoScenario>
}

export interface DemoPrecomputedResponse {
  available: boolean
  message?: string
  manifest?: Record<string, any>
}
