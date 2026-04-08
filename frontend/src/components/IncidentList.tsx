import { AlertTriangle, Clock } from 'lucide-react'
import { useEnvState } from '../hooks/useApi'

export default function IncidentList() {
  const { data: state, isLoading } = useEnvState()

  if (isLoading) {
    return <div className="card"><div className="text-center text-slate-400">Loading incidents...</div></div>
  }

  const incidents = state?.active_incidents || []

  return (
    <div className="card">
      <h2 className="text-lg font-bold mb-4 flex items-center space-x-2">
        <AlertTriangle className="w-5 h-5 text-warning" />
        <span>Active Incidents ({incidents.length})</span>
      </h2>

      {incidents.length === 0 ? (
        <div className="text-center text-slate-400 py-8">
          No active incidents
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((incident) => (
            <div
              key={incident.incident_id}
              className="bg-slate-700 rounded-md p-4 border-l-4 border-danger"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">{incident.title}</h3>
                  <p className="text-sm text-slate-300 mt-1">{incident.description}</p>
                </div>
                <div className="text-xs px-2 py-1 bg-danger/20 rounded text-danger font-medium">
                  L{incident.level}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-3 text-sm">
                <div>
                  <div className="text-slate-400 mb-1">Affected Services</div>
                  <div className="flex flex-wrap gap-1">
                    {incident.affected_services?.length > 0 ? (
                      incident.affected_services.map(svc => (
                        <span key={svc} className="px-2 py-1 bg-slate-600 rounded text-xs">
                          {svc}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-500">None</span>
                    )}
                  </div>
                </div>

                <div>
                  <div className="text-slate-400 mb-1">Affected Pods</div>
                  <div className="flex flex-wrap gap-1">
                    {incident.affected_pods?.length > 0 ? (
                      incident.affected_pods.map(pod => (
                        <span key={pod} className="px-2 py-1 bg-slate-600 rounded text-xs">
                          {pod}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-500">None</span>
                    )}
                  </div>
                </div>
              </div>

              {incident.root_cause && (
                <div className="mt-3 p-2 bg-slate-800 rounded text-sm">
                  <div className="text-slate-400 text-xs mb-1">Root Cause</div>
                  <div className="text-warning">{incident.root_cause}</div>
                </div>
              )}

              <div className="mt-3 flex items-center text-xs text-slate-400">
                <Clock className="w-3 h-3 mr-1" />
                Detected: {new Date(incident.detected_at * 1000).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
