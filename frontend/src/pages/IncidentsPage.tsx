import IncidentList from '../components/IncidentList'
import { AlertTriangle, Filter } from 'lucide-react'
import { useEnvState } from '../hooks/useApi'
import { useState } from 'react'

export default function IncidentsPage() {
  const { data: state } = useEnvState()
  const [filterLevel, setFilterLevel] = useState<number | null>(null)

  const incidents = state?.active_incidents || []
  const filteredIncidents = filterLevel 
    ? incidents.filter(i => i.level === filterLevel)
    : incidents

  return (
    <div className="p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Active Incidents</h1>
          <p className="text-slate-400">Monitor and analyze system incidents</p>
        </div>

        {/* Filter Bar */}
        <div className="card mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Filter className="w-5 h-5 text-slate-400" />
              <span className="font-medium">Filter by Level:</span>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => setFilterLevel(null)}
                className={`px-3 py-1 rounded text-sm ${!filterLevel ? 'bg-primary text-white' : 'bg-slate-700'}`}
              >
                All
              </button>
              {[1, 2, 3, 4, 5].map(level => (
                <button
                  key={level}
                  onClick={() => setFilterLevel(level)}
                  className={`px-3 py-1 rounded text-sm ${filterLevel === level ? 'bg-primary text-white' : 'bg-slate-700'}`}
                >
                  L{level}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">Total Incidents</div>
                <div className="text-3xl font-bold text-danger mt-1">{incidents.length}</div>
              </div>
              <AlertTriangle className="w-8 h-8 text-danger opacity-20" />
            </div>
          </div>

          {[1, 2, 3].map(level => (
            <div key={level} className="card">
              <div>
                <div className="text-sm text-slate-400">Level {level}</div>
                <div className="text-2xl font-bold mt-1">
                  {incidents.filter(i => i.level === level).length}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Incidents List */}
        <IncidentList />

        {filteredIncidents.length === 0 && (
          <div className="card mt-6">
            <div className="text-center text-slate-400 py-16">
              <AlertTriangle className="w-16 h-16 mx-auto mb-4 opacity-20" />
              <div className="text-xl font-medium">No incidents found</div>
              <div className="text-sm mt-2">System is running smoothly</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
