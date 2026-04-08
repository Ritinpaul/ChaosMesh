import { NavLink } from 'react-router-dom'
import { Home, Play, TrendingUp, AlertTriangle, Users, Activity, Settings, Zap, Theater, BookOpen } from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { path: '/', icon: Home, label: 'Dashboard', desc: 'Overview' },
  { path: '/episodes', icon: Play, label: 'Episodes', desc: 'Training' },
  { path: '/metrics', icon: TrendingUp, label: 'Metrics', desc: 'Analytics' },
  { path: '/incidents', icon: AlertTriangle, label: 'Incidents', desc: 'Active Issues' },
  { path: '/agents', icon: Users, label: 'Agents', desc: 'AI Agents' },
  { path: '/cluster', icon: Activity, label: 'Cluster', desc: 'Topology' },
  { path: '/demo-mode', icon: Theater, label: 'Demo Mode', desc: 'Full Tour' },
  { path: '/docs-center', icon: BookOpen, label: 'Docs', desc: 'Concept Guide' },
  { path: '/settings', icon: Settings, label: 'Settings', desc: 'Config' },
]

export default function Navbar() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <nav className={`bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-300 ${collapsed ? 'w-20' : 'w-64'} flex-shrink-0`}>
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between">
          {!collapsed && (
            <div className="flex items-center space-x-2">
              <Zap className="w-6 h-6 text-primary" />
              <span className="font-bold text-lg">ChaosMesh</span>
            </div>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 hover:bg-slate-700 rounded transition-colors"
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? '→' : '←'}
          </button>
        </div>
      </div>

      {/* Navigation Items */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-2">
          {navItems.map(({ path, icon: Icon, label, desc }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors group relative ${
                  isActive
                    ? 'bg-primary text-white shadow-lg shadow-primary/50'
                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                }`
              }
              title={collapsed ? label : undefined}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{label}</div>
                  <div className="text-xs text-slate-400 truncate">{desc}</div>
                </div>
              )}

              {/* Tooltip for collapsed state */}
              {collapsed && (
                <div className="absolute left-20 top-1/2 -translate-y-1/2 bg-slate-900 border border-slate-700 px-3 py-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap text-sm z-50">
                  {label}
                </div>
              )}
            </NavLink>
          ))}
        </div>
      </div>

      {/* Footer Info */}
      {!collapsed && (
        <div className="p-4 border-t border-slate-700">
          <div className="text-xs text-slate-400 space-y-2">
            <div className="font-semibold text-slate-300">Quick Keys</div>
            <div className="space-y-1 text-slate-500">
              <div><kbd className="bg-slate-700 px-2 py-1 rounded text-xs">1-5</kbd> Level</div>
              <div><kbd className="bg-slate-700 px-2 py-1 rounded text-xs">Space</kbd> Start</div>
              <div><kbd className="bg-slate-700 px-2 py-1 rounded text-xs">R</kbd> Refresh</div>
            </div>
          </div>
        </div>
      )}
    </nav>
  )
}
