import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import StatusBar from './components/StatusBar'

// Pages
import DashboardPage from './pages/DashboardPage'
import EpisodesPage from './pages/EpisodesPage'
import MetricsPage from './pages/MetricsPage'
import IncidentsPage from './pages/IncidentsPage'
import AgentsPage from './pages/AgentsPage'
import ClusterPage from './pages/ClusterPage'
import DemoModePage from './pages/DemoModePage'
import DocsPage from './pages/DocsPage'
import SettingsPage from './pages/SettingsPage'

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-col bg-slate-900">
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar Navigation */}
          <Navbar />
          
          {/* Main Content */}
          <main className="flex-1 flex flex-col overflow-auto">
            <div className="flex-1 overflow-auto">
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/episodes" element={<EpisodesPage />} />
                <Route path="/metrics" element={<MetricsPage />} />
                <Route path="/incidents" element={<IncidentsPage />} />
                <Route path="/agents" element={<AgentsPage />} />
                <Route path="/cluster" element={<ClusterPage />} />
                <Route path="/demo-mode" element={<DemoModePage />} />
                <Route path="/docs-center" element={<DocsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </div>

            {/* Status Bar Footer */}
            <StatusBar />
          </main>
        </div>
      </div>
    </Router>
  )
}

export default App
