import { Settings as SettingsIcon, RefreshCw, AlertCircle, CheckCircle, Sliders } from 'lucide-react'
import { useState } from 'react'

interface ApiConfig {
  apiKey: string
  apiUrl: string
  websocketUrl: string
}

interface AppSettings {
  autoRefreshInterval: number
  theme: 'dark' | 'light'
  enableNotifications: boolean
  enableWebSocketUpdates: boolean
  logLevel: 'debug' | 'info' | 'warn' | 'error'
}

export default function SettingsPage() {
  const [apiConfig, setApiConfig] = useState<ApiConfig>({
    apiKey: 'cm_demo_change_me',
    apiUrl: 'http://localhost:8000',
    websocketUrl: 'ws://localhost:8000/ws'
  })

  const [appSettings, setAppSettings] = useState<AppSettings>({
    autoRefreshInterval: 2000,
    theme: 'dark',
    enableNotifications: true,
    enableWebSocketUpdates: true,
    logLevel: 'info'
  })

  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')

  const handleApiConfigChange = (field: keyof ApiConfig, value: string) => {
    setApiConfig(prev => ({ ...prev, [field]: value }))
  }

  const handleAppSettingChange = (field: keyof AppSettings, value: any) => {
    setAppSettings(prev => ({ ...prev, [field]: value }))
  }

  const handleSaveSettings = async () => {
    setSaveStatus('saving')
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))
      localStorage.setItem('apiConfig', JSON.stringify(apiConfig))
      localStorage.setItem('appSettings', JSON.stringify(appSettings))
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 2000)
    }
  }

  const handleTestConnection = async () => {
    setTestStatus('testing')
    try {
      const response = await fetch(`${apiConfig.apiUrl}/health`, {
        headers: {
          'X-API-Key': apiConfig.apiKey
        }
      })
      if (response.ok) {
        setTestStatus('success')
        setTimeout(() => setTestStatus('idle'), 2000)
      } else {
        setTestStatus('error')
        setTimeout(() => setTestStatus('idle'), 2000)
      }
    } catch (error) {
      setTestStatus('error')
      setTimeout(() => setTestStatus('idle'), 2000)
    }
  }

  return (
    <div className="p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <SettingsIcon className="w-8 h-8 text-primary" />
            <h1 className="text-3xl font-bold">Settings</h1>
          </div>
          <p className="text-slate-400">Configure application and backend settings</p>
        </div>

        <div className="space-y-8">
          {/* API Configuration */}
          <section className="card">
            <h2 className="text-xl font-bold mb-6 flex items-center space-x-2">
              <SettingsIcon className="w-5 h-5 text-primary" />
              <span>Backend Configuration</span>
            </h2>

            <div className="space-y-4">
              {/* API Key */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  API Key
                </label>
                <input
                  type="password"
                  value={apiConfig.apiKey}
                  onChange={e => handleApiConfigChange('apiKey', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-primary"
                  placeholder="Enter your API key"
                />
                <p className="text-xs text-slate-400 mt-1">Keep this secret. Regenerate it if compromised.</p>
              </div>

              {/* API URL */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Backend URL
                </label>
                <input
                  type="text"
                  value={apiConfig.apiUrl}
                  onChange={e => handleApiConfigChange('apiUrl', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-primary"
                  placeholder="http://localhost:8000"
                />
              </div>

              {/* WebSocket URL */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  WebSocket URL
                </label>
                <input
                  type="text"
                  value={apiConfig.websocketUrl}
                  onChange={e => handleApiConfigChange('websocketUrl', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-primary"
                  placeholder="ws://localhost:8000/ws"
                />
              </div>

              {/* Test Connection Button */}
              <button
                onClick={handleTestConnection}
                disabled={testStatus === 'testing'}
                className={`w-full px-4 py-2 rounded-lg font-medium transition-all flex items-center justify-center space-x-2 ${
                  testStatus === 'testing'
                    ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                    : testStatus === 'success'
                    ? 'bg-green-600 text-white'
                    : testStatus === 'error'
                    ? 'bg-red-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {testStatus === 'testing' && <RefreshCw className="w-4 h-4 animate-spin" />}
                {testStatus === 'success' && <CheckCircle className="w-4 h-4" />}
                {testStatus === 'error' && <AlertCircle className="w-4 h-4" />}
                <span>{testStatus === 'testing' ? 'Testing...' : testStatus === 'success' ? 'Connected!' : testStatus === 'error' ? 'Connection Failed' : 'Test Connection'}</span>
              </button>
            </div>
          </section>

          {/* Application Settings */}
          <section className="card">
            <h2 className="text-xl font-bold mb-6 flex items-center space-x-2">
              <Sliders className="w-5 h-5 text-primary" />
              <span>Application Settings</span>
            </h2>

            <div className="space-y-4">
              {/* Auto Refresh Interval */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Auto-Refresh Interval (ms)
                </label>
                <input
                  type="number"
                  value={appSettings.autoRefreshInterval}
                  onChange={e => handleAppSettingChange('autoRefreshInterval', parseInt(e.target.value))}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-primary"
                  min="1000"
                  step="500"
                />
                <p className="text-xs text-slate-400 mt-1">How often to refresh data from the backend (1000ms minimum)</p>
              </div>

              {/* Theme Selection */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Theme
                </label>
                <select
                  value={appSettings.theme}
                  onChange={e => handleAppSettingChange('theme', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-primary"
                >
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                </select>
              </div>

              {/* Log Level */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Log Level
                </label>
                <select
                  value={appSettings.logLevel}
                  onChange={e => handleAppSettingChange('logLevel', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-primary"
                >
                  <option value="debug">Debug</option>
                  <option value="info">Info</option>
                  <option value="warn">Warning</option>
                  <option value="error">Error</option>
                </select>
              </div>

              {/* Feature Toggles */}
              <div className="space-y-3 pt-2 border-t border-slate-700">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={appSettings.enableNotifications}
                    onChange={e => handleAppSettingChange('enableNotifications', e.target.checked)}
                    className="w-4 h-4 rounded accent-primary"
                  />
                  <span className="text-slate-300">Enable Desktop Notifications</span>
                </label>

                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={appSettings.enableWebSocketUpdates}
                    onChange={e => handleAppSettingChange('enableWebSocketUpdates', e.target.checked)}
                    className="w-4 h-4 rounded accent-primary"
                  />
                  <span className="text-slate-300">Enable WebSocket Real-time Updates</span>
                </label>
              </div>
            </div>
          </section>

          {/* Save Button */}
          <div>
            <button
              onClick={handleSaveSettings}
              disabled={saveStatus === 'saving'}
              className={`w-full px-6 py-3 rounded-lg font-semibold transition-all flex items-center justify-center space-x-2 ${
                saveStatus === 'saving'
                  ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                  : saveStatus === 'saved'
                  ? 'bg-green-600 text-white'
                  : saveStatus === 'error'
                  ? 'bg-red-600 text-white'
                  : 'bg-primary hover:bg-primary-dark text-white'
              }`}
            >
              {saveStatus === 'saving' && <RefreshCw className="w-5 h-5 animate-spin" />}
              {saveStatus === 'saved' && <CheckCircle className="w-5 h-5" />}
              {saveStatus === 'error' && <AlertCircle className="w-5 h-5" />}
              <span>
                {saveStatus === 'saving'
                  ? 'Saving...'
                  : saveStatus === 'saved'
                  ? 'Settings Saved!'
                  : saveStatus === 'error'
                  ? 'Save Failed'
                  : 'Save Settings'}
              </span>
            </button>
          </div>

          {/* Debug Info */}
          <section className="card bg-slate-900 border-slate-600">
            <h3 className="text-sm font-bold text-slate-400 mb-3 uppercase">Debug Information</h3>
            <div className="space-y-2 text-xs font-mono text-slate-400">
              <div>Backend: <span className="text-slate-300">{apiConfig.apiUrl}</span></div>
              <div>WebSocket: <span className="text-slate-300">{apiConfig.websocketUrl}</span></div>
              <div>Theme: <span className="text-slate-300">{appSettings.theme}</span></div>
              <div>Log Level: <span className="text-slate-300">{appSettings.logLevel}</span></div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
