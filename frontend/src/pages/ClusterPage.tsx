import { Activity, Server, HardDrive, AlertCircle, CheckCircle, Info } from 'lucide-react'
import { useEnvState } from '../hooks/useApi'

type PodData = {
  phase?: string
  ready?: boolean
  restart_count?: number
  node_name?: string
  resources?: {
    cpu_millicores?: number
    memory_mib?: number
  }
}

type ServiceData = {
  error_rate_percent?: number
  p99_latency_ms?: number
  healthy_endpoints?: number
  total_endpoints?: number
}

const STATUS_COLOR: Record<string, string> = {
  Running: 'bg-green-500/20 text-green-400',
  Healthy: 'bg-green-500/20 text-green-400',
  Degraded: 'bg-yellow-500/20 text-yellow-400',
  Pending: 'bg-yellow-500/20 text-yellow-400',
  Failed: 'bg-red-500/20 text-red-400',
  CrashLoopBackOff: 'bg-red-500/20 text-red-400',
  Unhealthy: 'bg-red-500/20 text-red-400',
  Unknown: 'bg-slate-700 text-slate-300',
}

function getPodStatus(pod: PodData): string {
  const phase = pod.phase || 'Unknown'
  if (phase === 'Running' && pod.ready === false && (pod.restart_count || 0) > 2) {
    return 'CrashLoopBackOff'
  }
  return phase
}

function getServiceStatus(svc: ServiceData): string {
  const err = svc.error_rate_percent || 0
  const healthyEp = svc.healthy_endpoints ?? 0
  const totalEp = svc.total_endpoints ?? 1
  if (err > 20 || healthyEp === 0) return 'Unhealthy'
  if (err > 5 || healthyEp < totalEp) return 'Degraded'
  return 'Healthy'
}

function colorClass(status: string): string {
  return STATUS_COLOR[status] || STATUS_COLOR.Unknown
}

function TopologyMiniGraph({
  nodes,
  pods,
  services,
}: {
  nodes: string[]
  pods: Array<{ name: string; data: PodData }>
  services: Array<{ name: string; data: ServiceData }>
}) {
  const width = 960
  const height = 300
  const layerY = {
    nodes: 240,
    pods: 150,
    services: 60,
  }

  const xPos = (idx: number, total: number) => ((idx + 1) * width) / (total + 1)

  const nodePos: Record<string, { x: number; y: number }> = {}
  nodes.forEach((n, i) => {
    nodePos[n] = { x: xPos(i, Math.max(nodes.length, 1)), y: layerY.nodes }
  })

  pods.forEach((p, i) => {
    nodePos[p.name] = { x: xPos(i, Math.max(pods.length, 1)), y: layerY.pods }
  })

  services.forEach((s, i) => {
    nodePos[s.name] = { x: xPos(i, Math.max(services.length, 1)), y: layerY.services }
  })

  return (
    <div className="card overflow-x-auto">
      <h2 className="text-xl font-bold mb-4">Topology Graph</h2>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[700px] h-[280px] bg-slate-900 rounded-lg">
        {pods.map((pod) => {
          const podNode = pod.data.node_name
          if (!podNode || !nodePos[pod.name] || !nodePos[podNode]) return null
          return (
            <line
              key={`${pod.name}-${podNode}`}
              x1={nodePos[pod.name].x}
              y1={nodePos[pod.name].y}
              x2={nodePos[podNode].x}
              y2={nodePos[podNode].y}
              stroke="#475569"
              strokeWidth="1.5"
            />
          )
        })}

        {nodes.map((n) => (
          <g key={n}>
            <rect x={nodePos[n].x - 14} y={nodePos[n].y - 14} width="28" height="28" rx="4" fill="#3b82f6" />
            <text x={nodePos[n].x} y={nodePos[n].y + 28} textAnchor="middle" className="fill-slate-300 text-[10px]">
              {n.slice(0, 14)}
            </text>
          </g>
        ))}

        {pods.map((p) => {
          const status = getPodStatus(p.data)
          const fill = status === 'Running' ? '#22c55e' : status === 'Pending' ? '#f59e0b' : '#ef4444'
          return (
            <g key={p.name}>
              <circle cx={nodePos[p.name].x} cy={nodePos[p.name].y} r="11" fill={fill} />
              <text x={nodePos[p.name].x} y={nodePos[p.name].y + 25} textAnchor="middle" className="fill-slate-300 text-[10px]">
                {p.name.slice(0, 16)}
              </text>
            </g>
          )
        })}

        {services.map((s) => {
          const status = getServiceStatus(s.data)
          const fill = status === 'Healthy' ? '#22c55e' : status === 'Degraded' ? '#f59e0b' : '#ef4444'
          return (
            <g key={s.name}>
              <polygon
                points={`${nodePos[s.name].x},${nodePos[s.name].y - 12} ${nodePos[s.name].x + 12},${nodePos[s.name].y} ${nodePos[s.name].x},${nodePos[s.name].y + 12} ${nodePos[s.name].x - 12},${nodePos[s.name].y}`}
                fill={fill}
              />
              <text x={nodePos[s.name].x} y={nodePos[s.name].y + 25} textAnchor="middle" className="fill-slate-300 text-[10px]">
                {s.name.slice(0, 16)}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="mt-3 text-xs text-slate-400">
        Squares: Nodes | Circles: Pods | Diamonds: Services
      </div>
    </div>
  )
}

export default function ClusterPage() {
  const { data: state, isLoading } = useEnvState()

  const cluster = (state?.cluster_state || {}) as {
    pods?: Record<string, PodData>
    services?: Record<string, ServiceData>
    nodes?: Record<string, Record<string, unknown>>
  }

  const podEntries = Object.entries(cluster.pods || {}).map(([name, data]) => ({ name, data }))
  const serviceEntries = Object.entries(cluster.services || {}).map(([name, data]) => ({ name, data }))
  const nodeNames = Object.keys(cluster.nodes || {})

  const derivedNodeNames = nodeNames.length
    ? nodeNames
    : Array.from(new Set(podEntries.map((p) => p.data.node_name).filter((v): v is string => Boolean(v))))

  const activeIncidents = state?.active_incidents || []

  const runningPods = podEntries.filter((p) => getPodStatus(p.data) === 'Running').length
  const failedPods = podEntries.filter((p) => {
    const s = getPodStatus(p.data)
    return s === 'Failed' || s === 'CrashLoopBackOff'
  }).length

  const totalCpu = podEntries.reduce((acc, p) => acc + (p.data.resources?.cpu_millicores || 0), 0)
  const totalMem = podEntries.reduce((acc, p) => acc + (p.data.resources?.memory_mib || 0), 0)

  if (isLoading) {
    return <div className="p-6 text-slate-400">Loading cluster topology...</div>
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'Running':
      case 'Healthy':
        return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'Degraded':
        return <AlertCircle className="w-5 h-5 text-yellow-400" />
      case 'Failed':
      case 'Unhealthy':
      case 'CrashLoopBackOff':
        return <AlertCircle className="w-5 h-5 text-red-400" />
      default:
        return <Info className="w-5 h-5 text-blue-400" />
    }
  }

  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <Activity className="w-8 h-8 text-primary" />
            <h1 className="text-3xl font-bold">Cluster Topology</h1>
          </div>
          <p className="text-slate-400">Real-time Kubernetes cluster state</p>
        </div>

        {/* Cluster Overview Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Total Pods</div>
                <div className="text-3xl font-bold mt-1">{podEntries.length}</div>
              </div>
              <Server className="w-8 h-8 text-primary opacity-30" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Running</div>
                <div className="text-3xl font-bold text-green-400 mt-1">
                  {runningPods}
                </div>
              </div>
              <CheckCircle className="w-8 h-8 text-green-400 opacity-30" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Failed</div>
                <div className="text-3xl font-bold text-red-400 mt-1">
                  {failedPods}
                </div>
              </div>
              <AlertCircle className="w-8 h-8 text-red-400 opacity-30" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Nodes</div>
                <div className="text-3xl font-bold mt-1">{derivedNodeNames.length}</div>
              </div>
              <HardDrive className="w-8 h-8 text-info opacity-30" />
            </div>
          </div>
        </div>

        <div className="mb-8">
          <TopologyMiniGraph
            nodes={derivedNodeNames}
            pods={podEntries}
            services={serviceEntries}
          />
        </div>

        {activeIncidents.length > 0 && (
          <div className="card mb-8">
            <h2 className="text-xl font-bold mb-3">Active Incidents</h2>
            <div className="flex flex-wrap gap-2">
              {activeIncidents.map((inc) => (
                <span
                  key={inc.incident_id}
                  className="px-3 py-1 rounded-full text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/30"
                >
                  L{inc.level} {inc.title}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Services Section */}
          <div>
            <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
              <Activity className="w-5 h-5 text-primary" />
              <span>Services</span>
            </h2>
            <div className="space-y-3">
              {serviceEntries.map((service) => {
                const status = getServiceStatus(service.data)
                const healthyEp = service.data.healthy_endpoints ?? 0
                const totalEp = service.data.total_endpoints ?? 0

                return (
                <div key={service.name} className="card">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(status)}
                      <span className="font-medium">{service.name}</span>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${colorClass(status)}`}>
                      {status}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 text-sm text-slate-400">
                    <div>Error: <span className="text-white font-medium">{(service.data.error_rate_percent || 0).toFixed(1)}%</span></div>
                    <div>P99: <span className="text-white font-medium">{(service.data.p99_latency_ms || 0).toFixed(0)}ms</span></div>
                    <div>Endpoints: <span className="text-white font-medium text-xs">{healthyEp}/{totalEp}</span></div>
                  </div>
                </div>
              )})}
              {serviceEntries.length === 0 && (
                <div className="card text-slate-400">No services available yet. Start an episode first.</div>
              )}
            </div>
          </div>

          {/* Resources Usage */}
          <div>
            <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
              <HardDrive className="w-5 h-5 text-primary" />
              <span>Resource Usage</span>
            </h2>
            <div className="space-y-4">
              {/* CPU */}
              <div className="card">
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium">CPU</span>
                  <span className="text-sm font-bold text-primary">{totalCpu}m</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-3">
                  <div className="bg-gradient-to-r from-primary to-blue-400 h-3 rounded-full" style={{ width: `${Math.min(100, totalCpu / 60)}%` }} />
                </div>
              </div>

              {/* Memory */}
              <div className="card">
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium">Memory</span>
                  <span className="text-sm font-bold text-blue-400">{totalMem}Mi</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-3">
                  <div className="bg-gradient-to-r from-blue-400 to-blue-600 h-3 rounded-full" style={{ width: `${Math.min(100, totalMem / 40)}%` }} />
                </div>
              </div>

              {/* Disk */}
              <div className="card">
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium">Disk I/O</span>
                  <span className="text-sm font-bold text-green-400">Live</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-3">
                  <div className="bg-gradient-to-r from-green-400 to-green-600 h-3 rounded-full" style={{ width: `${Math.min(100, (serviceEntries.length * 18) + 10)}%` }} />
                </div>
              </div>

              {/* Network */}
              <div className="card">
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium">Network</span>
                  <span className="text-sm font-bold text-purple-400">{Math.round((state?.cluster_state?.network_health || 1) * 100)}%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-3">
                  <div className="bg-gradient-to-r from-purple-400 to-purple-600 h-3 rounded-full" style={{ width: `${Math.round((state?.cluster_state?.network_health || 1) * 100)}%` }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Pods Table */}
        <div className="mt-8">
          <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
            <Server className="w-5 h-5 text-primary" />
            <span>Pods</span>
          </h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-700">
                <tr>
                  <th className="text-left py-3 px-4 font-semibold">Pod Name</th>
                  <th className="text-left py-3 px-4 font-semibold">Status</th>
                  <th className="text-left py-3 px-4 font-semibold">CPU (m)</th>
                  <th className="text-left py-3 px-4 font-semibold">Memory (Mi)</th>
                  <th className="text-left py-3 px-4 font-semibold">Restarts</th>
                </tr>
              </thead>
              <tbody>
                {podEntries.map((pod) => {
                  const status = getPodStatus(pod.data)
                  return (
                  <tr key={pod.name} className="border-b border-slate-700/50 hover:bg-slate-700/50">
                    <td className="py-3 px-4 font-medium">{pod.name}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(status)}
                        <span className={colorClass(status)}>{status}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-300">{pod.data.resources?.cpu_millicores || 0}m</td>
                    <td className="py-3 px-4 text-slate-300">{pod.data.resources?.memory_mib || 0}Mi</td>
                    <td className="py-3 px-4">
                      <span className={(pod.data.restart_count || 0) > 0 ? 'text-yellow-400 font-semibold' : 'text-slate-400'}>
                        {pod.data.restart_count || 0}
                      </span>
                    </td>
                  </tr>
                )})}
                {podEntries.length === 0 && (
                  <tr>
                    <td className="py-6 px-4 text-slate-400" colSpan={5}>No pods available yet. Start or step an episode.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
