import { Activity, Database, Zap } from 'lucide-react'
import { useHealth } from '../hooks/useApi'

export default function Header() {
  const { data: health, isLoading } = useHealth()

  return (
    <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Zap className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold text-slate-100">ChaosMesh Arena</h1>
            <p className="text-sm text-slate-400">Multi-Agent SRE Training Environment</p>
          </div>
        </div>

        <div className="flex items-center space-x-6">
          {isLoading ? (
            <div className="text-sm text-slate-400">Loading...</div>
          ) : health ? (
            <>
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${health.status === 'healthy' ? 'bg-success' : 'bg-danger'}`} />
                <span className="text-sm font-medium">{health.status}</span>
              </div>

              <div className="flex items-center space-x-2 text-sm">
                <Activity className="w-4 h-4" />
                <span>Ollama: {health.ollama_available ? '✓' : '✗'}</span>
              </div>

              <div className="flex items-center space-x-2 text-sm">
                <Database className="w-4 h-4" />
                <span>Redis: {health.redis_connected ? '✓' : '✗'}</span>
              </div>

              <div className="text-sm text-slate-400">
                v{health.version}
              </div>

              {health.active_episode && (
                <div className="text-sm px-3 py-1 bg-primary/20 rounded-md">
                  Episode: {health.active_episode.slice(0, 8)}...
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-danger">Server offline</div>
          )}
        </div>
      </div>
    </header>
  )
}
