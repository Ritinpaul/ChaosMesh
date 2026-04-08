import { BookOpen, Route, Layers, AlertTriangle, Cpu, Shield, Database } from 'lucide-react'

type GlossaryItem = {
  term: string
  meaning: string
}

const apiRoutes = [
  { method: 'GET', path: '/health', purpose: 'Public health status and backend availability checks.' },
  { method: 'POST', path: '/env/reset', purpose: 'Start a new episode at a selected level.' },
  { method: 'POST', path: '/env/step', purpose: 'Submit one agent action and advance simulation.' },
  { method: 'GET', path: '/env/state', purpose: 'Fetch full internal state (incidents, beliefs, rewards, progression).' },
  { method: 'GET', path: '/env/render', purpose: 'Get visualization-optimized cluster snapshot.' },
  { method: 'GET', path: '/demo/scenarios', purpose: 'List recommended and full demo scenario catalog.' },
  { method: 'POST', path: '/demo/inject', purpose: 'Inject scenario manually or by scenario_key.' },
  { method: 'GET', path: '/demo/precomputed', purpose: 'Check precomputed demo cache manifest availability.' },
  { method: 'GET', path: '/docs', purpose: 'Interactive Swagger UI documentation.' },
  { method: 'GET', path: '/redoc', purpose: 'Alternative API documentation view.' },
  { method: 'GET', path: '/openapi.json', purpose: 'OpenAPI schema JSON.' },
  { method: 'WS', path: '/ws/stream', purpose: 'Realtime streaming channel for dashboard updates.' },
]

const levelGuide = [
  {
    level: 'L1 - Pod Crash',
    summary: 'Single-point failures with clear signals.',
    examples: 'pod OOM crash, image pull failure, node disk pressure',
  },
  {
    level: 'L2 - Cascade',
    summary: 'Correlated failures affecting multiple services.',
    examples: 'cascading DB timeout, node failure cascade, rolling restart failure',
  },
  {
    level: 'L3 - Ambiguous',
    summary: 'Root cause is unclear and requires hypothesis validation.',
    examples: 'attack vs misconfiguration, performance degradation ambiguity',
  },
  {
    level: 'L4 - Dynamic',
    summary: 'Second-order failures where remediation can trigger new issues.',
    examples: 'autoscaling loop, remediation secondary failure',
  },
  {
    level: 'L5 - Compound',
    summary: 'Multiple simultaneous incident classes requiring coordinated triage.',
    examples: 'DB lag + gateway saturation, security breach + node failure',
  },
]

const glossary: GlossaryItem[] = [
  { term: 'Pod Crash', meaning: 'A Kubernetes pod enters crash states (often OOMKilled or CrashLoopBackOff).' },
  { term: 'Cascade', meaning: 'A failure chain where one outage propagates to dependent systems.' },
  { term: 'Ambiguous Incident', meaning: 'Symptoms fit multiple root causes; diagnostics must disambiguate evidence.' },
  { term: 'Dynamic Failure', meaning: 'System state changes over time and may react negatively to naive fixes.' },
  { term: 'Compound Chaos', meaning: 'More than one major incident class occurring at once.' },
  { term: 'Belief Tracking', meaning: 'Memory of agent hypotheses, confidence, and supporting evidence.' },
  { term: 'Episode', meaning: 'One training run from reset to terminated or truncated outcome.' },
  { term: 'Truncated', meaning: 'Episode ended due to time/step caps rather than successful resolution.' },
  { term: 'Cumulative Reward', meaning: 'Aggregate score from all steps reflecting quality and efficiency.' },
  { term: 'Scenario Key', meaning: 'Deterministic identifier for injecting a specific incident template.' },
  { term: 'Demo Mode', meaning: 'Fast-path runtime mode optimized for showcase speed and repeatability.' },
  { term: 'Dual LLM Routing', meaning: 'Primary local model (Ollama) with cloud fallback (OpenRouter).' },
  { term: 'ChromaDB', meaning: 'Vector memory backend used for belief and context retrieval.' },
]

const frontendRoutes = [
  { route: '/', meaning: 'Dashboard overview with metrics and incident feed.' },
  { route: '/episodes', meaning: 'Episode creation, level selection, and progression status.' },
  { route: '/metrics', meaning: 'Detailed system and reward analytics.' },
  { route: '/incidents', meaning: 'Incident tracking and active issue context.' },
  { route: '/agents', meaning: 'Agent activity and role-level observations.' },
  { route: '/cluster', meaning: 'Cluster topology and health visualization.' },
  { route: '/demo-mode', meaning: 'One-click full showcase across levels and scenarios.' },
  { route: '/docs-center', meaning: 'This documentation center.' },
  { route: '/settings', meaning: 'Runtime configuration and environment information.' },
]

export default function DocsPage() {
  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="card">
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <BookOpen className="w-8 h-8 text-primary" />
            ChaosMesh Arena Docs Center
          </h1>
          <p className="text-slate-300 mt-3">
            This route explains the full project surface: concepts, levels, architecture, API endpoints, and every core term used in the platform.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="card">
            <div className="flex items-center gap-2 text-primary font-semibold">
              <Cpu className="w-4 h-4" />
              Simulation Core
            </div>
            <p className="text-sm text-slate-300 mt-2">
              Gym-like environment with incidents, actions, rewards, truncation, and level progression.
            </p>
          </div>
          <div className="card">
            <div className="flex items-center gap-2 text-primary font-semibold">
              <Database className="w-4 h-4" />
              Memory Layer
            </div>
            <p className="text-sm text-slate-300 mt-2">
              ChromaDB-backed belief storage plus SQLite episode persistence and Redis cache/bus.
            </p>
          </div>
          <div className="card">
            <div className="flex items-center gap-2 text-primary font-semibold">
              <Shield className="w-4 h-4" />
              Control Plane
            </div>
            <p className="text-sm text-slate-300 mt-2">
              API-key protected routes, demo scenario tools, OpenAPI docs, and realtime streaming.
            </p>
          </div>
        </div>

        <div className="card overflow-x-auto">
          <h2 className="text-xl font-bold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-primary" />
            Difficulty Levels (L1-L5)
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="py-2 pr-3">Level</th>
                <th className="py-2 pr-3">What It Means</th>
                <th className="py-2 pr-3">Common Scenarios</th>
              </tr>
            </thead>
            <tbody>
              {levelGuide.map((row) => (
                <tr key={row.level} className="border-b border-slate-800">
                  <td className="py-2 pr-3 font-semibold">{row.level}</td>
                  <td className="py-2 pr-3">{row.summary}</td>
                  <td className="py-2 pr-3 text-slate-300">{row.examples}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card overflow-x-auto">
          <h2 className="text-xl font-bold mb-3 flex items-center gap-2">
            <Route className="w-5 h-5 text-primary" />
            Backend API Routes
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="py-2 pr-3">Method</th>
                <th className="py-2 pr-3">Path</th>
                <th className="py-2 pr-3">Purpose</th>
              </tr>
            </thead>
            <tbody>
              {apiRoutes.map((row) => (
                <tr key={`${row.method}-${row.path}`} className="border-b border-slate-800">
                  <td className="py-2 pr-3 font-semibold">{row.method}</td>
                  <td className="py-2 pr-3 font-mono text-xs">{row.path}</td>
                  <td className="py-2 pr-3">{row.purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card overflow-x-auto">
          <h2 className="text-xl font-bold mb-3 flex items-center gap-2">
            <Layers className="w-5 h-5 text-primary" />
            Frontend Routes
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="py-2 pr-3">Route</th>
                <th className="py-2 pr-3">Description</th>
              </tr>
            </thead>
            <tbody>
              {frontendRoutes.map((row) => (
                <tr key={row.route} className="border-b border-slate-800">
                  <td className="py-2 pr-3 font-mono text-xs">{row.route}</td>
                  <td className="py-2 pr-3">{row.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2 className="text-xl font-bold mb-3">Glossary</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {glossary.map((item) => (
              <div key={item.term} className="bg-slate-700/40 rounded-md p-3 border border-slate-700">
                <div className="font-semibold text-primary">{item.term}</div>
                <div className="text-sm text-slate-300 mt-1">{item.meaning}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
