import { useEnvState } from '../hooks/useApi'

export default function StatusBar() {
  const { data: state, isLoading } = useEnvState()

  if (isLoading) {
    return (
      <div className="bg-slate-800 border-t border-slate-700 px-6 py-3">
        <div className="text-sm text-slate-400">Loading...</div>
      </div>
    )
  }

  if (!state) {
    return (
      <div className="bg-slate-800 border-t border-slate-700 px-6 py-3">
        <div className="text-sm text-slate-400">No episode active</div>
      </div>
    )
  }

  const { episode_id, step, current_level, cumulative_reward, active_incidents, difficulty_state } = state

  return (
    <div className="bg-slate-800 border-t border-slate-700 px-6 py-3">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center space-x-6">
          <div>
            <span className="text-slate-400">Episode:</span>{' '}
            <span className="font-mono font-medium">{episode_id?.slice(0, 12)}...</span>
          </div>

          <div>
            <span className="text-slate-400">Step:</span>{' '}
            <span className="font-medium">{step || 0}</span>
          </div>

          <div>
            <span className="text-slate-400">Level:</span>{' '}
            <span className="font-medium text-primary">L{current_level || 1}</span>
          </div>

          <div>
            <span className="text-slate-400">Reward:</span>{' '}
            <span className={`font-medium ${cumulative_reward >= 0 ? 'text-success' : 'text-danger'}`}>
              {cumulative_reward?.toFixed(2) || '0.00'}
            </span>
          </div>

          <div>
            <span className="text-slate-400">Incidents:</span>{' '}
            <span className={`font-medium ${active_incidents?.length > 0 ? 'text-danger' : 'text-success'}`}>
              {active_incidents?.length || 0}
            </span>
          </div>
        </div>

        {difficulty_state && (
          <div className="flex items-center space-x-4 text-xs">
            <div>
              <span className="text-slate-400">Successes:</span>{' '}
              <span className="font-medium">{difficulty_state.consecutive_successes}</span>
              <span className="text-slate-500"> / {difficulty_state.success_threshold}</span>
            </div>
            <div>
              <span className="text-slate-400">Total Episodes:</span>{' '}
              <span className="font-medium">{difficulty_state.total_episodes}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
