import MetricsDisplay from '../components/MetricsDisplay'
import IncidentList from '../components/IncidentList'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

export default function DashboardPage() {
  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <Link
            to="/episodes"
            className="btn btn-secondary inline-flex items-center space-x-2"
          >
            <span>Manage Episodes</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        
        <div className="space-y-6">
          <MetricsDisplay />
          <IncidentList />
        </div>
      </div>
    </div>
  )
}
