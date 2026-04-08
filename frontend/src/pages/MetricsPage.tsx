import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { TrendingUp, Activity, Zap } from 'lucide-react'
import { useEnvState } from '../hooks/useApi'
import MetricsDisplay from '../components/MetricsDisplay'

export default function MetricsPage() {
  const { data: state } = useEnvState()

  // Prepare reward history data
  const rewardData = (state?.reward_history || []).map((reward, idx) => ({
    step: idx + 1,
    reward: reward,
    cumulative: state?.reward_history.slice(0, idx + 1).reduce((a, b) => a + b, 0) || 0
  }))

  // Prepare service metrics
  const serviceData = Object.entries(state?.cluster_state?.services || {}).map(([name, service]) => ({
    name,
    errorRate: service.error_rate_percent,
    latency: service.p99_latency_ms,
    health: service.healthy ? 100 : 0
  }))

  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Metrics & Analytics</h1>
          <p className="text-slate-400">Real-time performance and reward tracking</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Cumulative Reward</div>
                <div className="text-2xl font-bold text-primary mt-1">
                  {state?.cumulative_reward?.toFixed(2) || '0.00'}
                </div>
              </div>
              <TrendingUp className="w-8 h-8 text-primary opacity-20" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Current Step</div>
                <div className="text-2xl font-bold mt-1">{state?.step || 0}</div>
              </div>
              <Activity className="w-8 h-8 text-blue-500 opacity-20" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Average Reward</div>
                <div className="text-2xl font-bold text-success mt-1">
                  {state?.reward_history?.length 
                    ? (state.reward_history.reduce((a, b) => a + b, 0) / state.reward_history.length).toFixed(2)
                    : '0.00'
                  }
                </div>
              </div>
              <Zap className="w-8 h-8 text-success opacity-20" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Services Healthy</div>
                <div className="text-2xl font-bold text-success mt-1">
                  {Object.values(state?.cluster_state?.services || {}).filter(s => s.healthy).length}
                  <span className="text-sm text-slate-400">
                    /{Object.keys(state?.cluster_state?.services || {}).length}
                  </span>
                </div>
              </div>
              <Activity className="w-8 h-8 text-success opacity-20" />
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {/* Reward Charts */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Reward History</h2>
            {rewardData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={rewardData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="step" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                    labelStyle={{ color: '#e2e8f0' }}
                  />
                  <Area type="monotone" dataKey="reward" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.3} name="Step Reward" />
                  <Area type="monotone" dataKey="cumulative" stroke="#10b981" fill="#10b981" fillOpacity={0.2} name="Cumulative" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center text-slate-400 py-16">No reward data yet</div>
            )}
          </div>

          {/* Service Metrics */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <h2 className="text-xl font-bold mb-4">Service Error Rates</h2>
              {serviceData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={serviceData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                      labelStyle={{ color: '#e2e8f0' }}
                    />
                    <Bar dataKey="errorRate" fill="#ef4444" name="Error Rate %" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-center text-slate-400 py-16">No service data</div>
              )}
            </div>

            <div className="card">
              <h2 className="text-xl font-bold mb-4">Service Latency (P99)</h2>
              {serviceData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={serviceData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                      labelStyle={{ color: '#e2e8f0' }}
                    />
                    <Bar dataKey="latency" fill="#f59e0b" name="Latency (ms)" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-center text-slate-400 py-16">No latency data</div>
              )}
            </div>
          </div>

          {/* Original Metrics Display */}
          <MetricsDisplay />
        </div>
      </div>
    </div>
  )
}
