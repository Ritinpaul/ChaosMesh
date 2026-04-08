import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { TrendingUp } from 'lucide-react'
import { useEnvState } from '../hooks/useApi'

export default function MetricsDisplay() {
  const { data: state, isLoading } = useEnvState()

  if (isLoading) {
    return <div className="card"><div className="text-center text-slate-400">Loading metrics...</div></div>
  }

  if (!state) {
    return <div className="card"><div className="text-center text-slate-400">No data available</div></div>
  }

  // Prepare reward history data for chart
  const rewardData = (state.reward_history || []).map((reward, idx) => ({
    step: idx + 1,
    reward: reward
  }))

  // Prepare service metrics
  const services = Object.entries(state.cluster_state?.services || {})

  return (
    <div className="space-y-4">
      {/* Reward Chart */}
      <div className="card">
        <h2 className="text-lg font-bold mb-4 flex items-center space-x-2">
          <TrendingUp className="w-5 h-5 text-primary" />
          <span>Cumulative Reward: {state.cumulative_reward?.toFixed(2) || '0.00'}</span>
        </h2>

        {rewardData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={rewardData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="step" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Line type="monotone" dataKey="reward" stroke="#4f46e5" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center text-slate-400 py-8">No reward data yet</div>
        )}
      </div>

      {/* Service Health */}
      <div className="card">
        <h2 className="text-lg font-bold mb-4">Service Metrics</h2>
        
        {services.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {services.map(([name, service]) => (
              <div key={name} className="bg-slate-700 rounded-md p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{name}</span>
                  <div className={`w-3 h-3 rounded-full ${service.healthy ? 'bg-success' : 'bg-danger'}`} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <div className="text-slate-400">Error Rate</div>
                    <div className={service.error_rate_percent > 5 ? 'text-danger font-medium' : ''}>
                      {service.error_rate_percent?.toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-400">P99 Latency</div>
                    <div className={service.p99_latency_ms > 1000 ? 'text-warning font-medium' : ''}>
                      {service.p99_latency_ms?.toFixed(0)}ms
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-slate-400">No services running</div>
        )}
      </div>
    </div>
  )
}
