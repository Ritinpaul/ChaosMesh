import { useState } from 'react'
import { Play, Calendar, Award } from 'lucide-react'
import { useEnvState, useResetEpisode } from '../hooks/useApi'

const LEVELS = [
  { value: 1, label: 'L1 - Pod Crash', desc: 'Simple pod failures', color: 'bg-green-500' },
  { value: 2, label: 'L2 - Cascade', desc: 'Multi-service failures', color: 'bg-blue-500' },
  { value: 3, label: 'L3 - Ambiguous', desc: 'Unclear root causes', color: 'bg-yellow-500' },
  { value: 4, label: 'L4 - Dynamic', desc: 'Changing conditions', color: 'bg-orange-500' },
  { value: 5, label: 'L5 - Compound', desc: 'Multiple simultaneous issues', color: 'bg-red-500' }
]

export default function EpisodesPage() {
  const [selectedLevel, setSelectedLevel] = useState(1)
  const { data: state } = useEnvState()
  const resetMutation = useResetEpisode()

  const handleCreateEpisode = async () => {
    await resetMutation.mutateAsync(selectedLevel)
  }

  return (
    <div className="p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Episode Management</h1>
          <p className="text-slate-400">Create and manage training episodes</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Create New Episode */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
              <Play className="w-5 h-5 text-primary" />
              <span>Create New Episode</span>
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-3">
                  Select Difficulty Level
                </label>
                <div className="space-y-2">
                  {LEVELS.map(level => (
                    <label
                      key={level.value}
                      className={`flex items-center space-x-3 p-4 rounded-lg cursor-pointer transition-all border-2 ${
                        selectedLevel === level.value
                          ? 'border-primary bg-primary/10'
                          : 'border-slate-700 hover:border-slate-600'
                      }`}
                    >
                      <input
                        type="radio"
                        name="level"
                        value={level.value}
                        checked={selectedLevel === level.value}
                        onChange={() => setSelectedLevel(level.value)}
                        className="w-4 h-4"
                      />
                      <div className={`w-3 h-3 rounded-full ${level.color}`} />
                      <div className="flex-1">
                        <div className="font-medium">{level.label}</div>
                        <div className="text-sm text-slate-400">{level.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <button
                onClick={handleCreateEpisode}
                disabled={resetMutation.isPending}
                className="btn btn-primary w-full py-3 text-lg"
              >
                {resetMutation.isPending ? 'Creating...' : '🚀 Start New Episode'}
              </button>

              {resetMutation.isSuccess && (
                <div className="p-4 bg-success/20 border border-success rounded-lg">
                  <div className="font-medium">✓ Episode Created!</div>
                  <div className="text-sm mt-1 font-mono">
                    {resetMutation.data.episode_id}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Current Episode Info */}
          <div className="space-y-6">
            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
                <Calendar className="w-5 h-5 text-primary" />
                <span>Current Episode</span>
              </h2>

              {state?.episode_id ? (
                <div className="space-y-4">
                  <div>
                    <div className="text-sm text-slate-400 mb-1">Episode ID</div>
                    <div className="font-mono text-sm bg-slate-700 p-3 rounded">
                      {state.episode_id}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-slate-400 mb-1">Level</div>
                      <div className="text-2xl font-bold text-primary">
                        L{state.current_level}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-slate-400 mb-1">Step</div>
                      <div className="text-2xl font-bold">{state.step}</div>
                    </div>
                    <div>
                      <div className="text-sm text-slate-400 mb-1">Reward</div>
                      <div className={`text-2xl font-bold ${state.cumulative_reward >= 0 ? 'text-success' : 'text-danger'}`}>
                        {state.cumulative_reward.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-slate-400 mb-1">Incidents</div>
                      <div className={`text-2xl font-bold ${state.active_incidents.length > 0 ? 'text-danger' : 'text-success'}`}>
                        {state.active_incidents.length}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-slate-400 py-8">
                  No active episode
                </div>
              )}
            </div>

            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
                <Award className="w-5 h-5 text-primary" />
                <span>Progress</span>
              </h2>

              {state?.difficulty_state ? (
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-slate-400">Consecutive Successes</span>
                      <span className="font-medium">
                        {state.difficulty_state.consecutive_successes} / {state.difficulty_state.success_threshold}
                      </span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2">
                      <div
                        className="bg-success rounded-full h-2 transition-all"
                        style={{
                          width: `${(state.difficulty_state.consecutive_successes / state.difficulty_state.success_threshold) * 100}%`
                        }}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-center">
                    <div className="bg-slate-700 p-4 rounded-lg">
                      <div className="text-3xl font-bold text-primary">
                        {state.difficulty_state.total_episodes}
                      </div>
                      <div className="text-sm text-slate-400 mt-1">Total Episodes</div>
                    </div>
                    <div className="bg-slate-700 p-4 rounded-lg">
                      <div className="text-3xl font-bold text-success">
                        {state.difficulty_state.consecutive_successes}
                      </div>
                      <div className="text-sm text-slate-400 mt-1">Successes</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-slate-400 py-8">
                  No progress data
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
