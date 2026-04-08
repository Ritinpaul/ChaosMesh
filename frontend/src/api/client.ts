import axios from 'axios'
import type {
  HealthResponse,
  EnvState,
  ResetResponse,
  StepRequest,
  StepResponse,
  InjectRequest,
  InjectResponse,
  DemoScenarioListResponse,
  DemoPrecomputedResponse
} from '../types/api'

const API_KEY = 'cm_demo_change_me'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
  },
  timeout: 30000
})

export const healthApi = {
  getHealth: () => api.get<HealthResponse>('/health').then(r => r.data)
}

export const envApi = {
  getState: () => api.get<EnvState>('/env/state').then(r => r.data),
  
  reset: (level: number = 1) => 
    api.post<ResetResponse>('/env/reset', { level }).then(r => r.data),
  
  step: (actions: StepRequest) => 
    api.post<StepResponse>('/env/step', actions).then(r => r.data)
}

export const demoApi = {
  injectIncident: (data: InjectRequest) => 
    api.post<InjectResponse>('/demo/inject', data).then(r => r.data),

  getScenarios: () =>
    api.get<DemoScenarioListResponse>('/demo/scenarios').then(r => r.data),

  getPrecomputed: () =>
    api.get<DemoPrecomputedResponse>('/demo/precomputed').then(r => r.data)
}

export default api
