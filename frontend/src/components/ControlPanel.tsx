import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { useResetEpisode } from '../hooks/useApi'

const LEVELS = [
  { value: 1, label: 'L1 - Pod Crash', desc: 'Simple pod failures' },
  { value: 2, label: 'L2 - Cascade', desc: 'Multi-service failures' },
  { value: 3, label: 'L3 - Ambiguous', desc: 'Unclear root causes' },
  { value: 4, label: 'L4 - Dynamic', desc: 'Changing conditions' },
  { value: 5, label: 'L5 - Compound', desc: 'Multiple simultaneous issues' }
]

export default function ControlPanel() {
  const [selectedLevel, setSelectedLevel] = useState(1)
  const resetMutation = useResetEpisode()

  const handleStartEpisode = async () => {
    try {
      const result = await resetMutation.mutateAsync(selectedLevel)
      console.log('Episode created:', result.episode_id)
    } catch (error) {
      console.error('Failed to create episode:', error)
    }
  }

  return (
    <div className="card">
      <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
        <Play className="w-5 h-5 text-primary" />
        <span>Episode Control</span>
      </h2>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Select Difficulty Level
          </label>
          <div className="space-y-2">
            {LEVELS.map(level => (
              <label
                key={level.value}
                className={`flex items-center space-x-3 p-3 rounded-md cursor-pointer transition-colors ${
                  selectedLevel === level.value
                    ? 'bg-primary/20 border border-primary'
                    : 'bg-slate-700 border border-transparent hover:border-slate-600'
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
                <div className="flex-1">
                  <div className="font-medium">{level.label}</div>
                  <div className="text-sm text-slate-400">{level.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        <button
          onClick={handleStartEpisode}
          disabled={resetMutation.isPending}
          className="btn btn-primary w-full flex items-center justify-center space-x-2"
        >
          {resetMutation.isPending ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Creating Episode...</span>
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              <span>Start New Episode</span>
            </>
          )}
        </button>

        {resetMutation.isSuccess && (
          <div className="p-3 bg-success/20 border border-success rounded-md text-sm">
            ✓ Episode created: {resetMutation.data.episode_id.slice(0, 16)}...
          </div>
        )}

        {resetMutation.isError && (
          <div className="p-3 bg-danger/20 border border-danger rounded-md text-sm">
            ✗ Failed to create episode: {(resetMutation.error as Error).message}
          </div>
        )}
      </div>
    </div>
  )
}
