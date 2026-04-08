import { Brain, Activity } from 'lucide-react'
import { useState } from 'react'
import { useEnvState } from '../hooks/useApi'

interface Agent {
  id: string
  name: string
  role: 'commander' | 'diagnostics' | 'remediation' | 'security' | 'agent'
  status: 'active' | 'idle' | 'error'
  confidence: number
  findings: number
  hypotheses: number
  messageCount: number
}

const CORE_AGENTS = [
  'incident_commander',
  'diagnostics',
  'remediation',
  'security',
  'database',
]

export default function AgentsPage() {
  const { data: state, isLoading } = useEnvState()
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)

  const beliefs = state?.all_beliefs || {}
  const allMessages = Array.isArray(state?.all_messages) ? state.all_messages : []

  const messageCountByAgent = allMessages.reduce<Record<string, number>>((acc, msg) => {
    const senderRaw = (msg && typeof msg === 'object' && 'sender' in msg) ? (msg as { sender?: unknown }).sender : undefined
    const sender = senderRaw && typeof senderRaw === 'object' && senderRaw !== null && 'value' in senderRaw
      ? String((senderRaw as { value?: unknown }).value)
      : String(senderRaw || '')

    if (!sender) return acc
    acc[sender] = (acc[sender] || 0) + 1
    return acc
  }, {})

  const normalizeRole = (name: string): Agent['role'] => {
    const n = name.toLowerCase()
    if (n.includes('commander')) return 'commander'
    if (n.includes('diagnostic')) return 'diagnostics'
    if (n.includes('remediation')) return 'remediation'
    if (n.includes('security')) return 'security'
    return 'agent'
  }

  const labelFromRole = (role: Agent['role']) => {
    switch (role) {
      case 'commander':
        return 'Orchestration'
      case 'diagnostics':
        return 'Analysis'
      case 'remediation':
        return 'Fixing'
      case 'security':
        return 'Compliance'
      default:
        return 'General'
    }
  }

  const agentIds = Array.from(new Set([...CORE_AGENTS, ...Object.keys(beliefs), ...Object.keys(messageCountByAgent)]))

  const formatName = (id: string) =>
    id
      .split('_')
      .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
      .join(' ')

  const agents: Agent[] = agentIds.map((id) => {
    const belief = beliefs[id]
    const confidence = typeof belief?.confidence === 'number' ? belief.confidence : 0
    const findings = Array.isArray(belief?.supporting_evidence) ? belief.supporting_evidence.length : 0
    const hypotheses = belief?.hypothesis ? 1 : 0
    const messageCount = messageCountByAgent[id] || 0
    const role = normalizeRole(id)

    return {
      id,
      name: formatName(id),
      role,
      status: (messageCount > 0 || confidence > 0) ? 'active' : 'idle',
      confidence,
      findings,
      hypotheses,
      messageCount,
    }
  })

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-500'
      case 'idle':
        return 'bg-yellow-500'
      case 'error':
        return 'bg-red-500'
      default:
        return 'bg-slate-500'
    }
  }

  if (isLoading) {
    return <div className="p-6 text-slate-400">Loading agents...</div>
  }

  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <Brain className="w-8 h-8 text-primary" />
            <h1 className="text-3xl font-bold">AI Agents</h1>
          </div>
          <p className="text-slate-400">Monitor and control autonomous agents</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Agent List */}
          <div className="lg:col-span-2">
            <div className="space-y-4">
              <div className="card text-slate-400 text-sm">
                Live telemetry appears after agent actions. At step 0, agents are listed as idle until messages/beliefs are produced.
              </div>
              {agents.map(agent => (
                <div
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent.id)}
                  className={`card cursor-pointer transition-all border-2 ${
                    selectedAgent === agent.id
                      ? 'border-primary bg-slate-700 shadow-lg shadow-primary/50'
                      : 'border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <div className={`w-3 h-3 rounded-full ${getStatusColor(agent.status)}`} />
                      <div>
                        <h3 className="font-bold text-lg">{agent.name}</h3>
                        <p className="text-sm text-slate-400">{labelFromRole(agent.role)}</p>
                      </div>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      agent.status === 'active'
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-slate-700 text-slate-300'
                    }`}>
                      {agent.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <div className="text-xs text-slate-400 mb-1">Confidence</div>
                      <div className="text-2xl font-bold">{(agent.confidence * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400 mb-1">Findings</div>
                      <div className="text-2xl font-bold text-green-400">{agent.findings}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400 mb-1">Messages</div>
                      <div className="text-2xl font-bold text-blue-400">{agent.messageCount}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Agent Details & Controls */}
          <div className="space-y-4">
            {/* Agent Stats Card */}
            <div className="card">
              <div className="flex items-center space-x-2 mb-4">
                <Activity className="w-5 h-5 text-primary" />
                <h3 className="font-bold">System Status</h3>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-slate-400">Active Agents</span>
                  <span className="font-bold text-green-400">{agents.filter(a => a.status === 'active').length}/{agents.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Avg Confidence</span>
                  <span className="font-bold text-blue-400">
                    {agents.length ? `${((agents.reduce((a, b) => a + b.confidence, 0) / agents.length) * 100).toFixed(1)}%` : '0.0%'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Messages</span>
                  <span className="font-bold">{agents.reduce((a, b) => a + b.messageCount, 0)}</span>
                </div>
              </div>
            </div>

            {/* Performance Chart */}
            <div className="card">
              <h3 className="font-bold mb-4">Confidence Distribution</h3>
              <div className="space-y-2">
                {agents.map(agent => (
                  <div key={agent.id}>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs text-slate-400">{agent.name}</span>
                      <span className="text-xs font-semibold">{(agent.confidence * 100).toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2">
                      <div
                        className="bg-primary rounded-full h-2 transition-all"
                        style={{ width: `${Math.max(0, Math.min(100, agent.confidence * 100))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
