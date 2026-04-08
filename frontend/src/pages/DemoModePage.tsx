import { useMemo, useRef, useState } from 'react'
import { Play, Square, Activity, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react'
import { demoApi, envApi } from '../api/client'
import { useDemoPrecomputed, useDemoScenarios, useHealth } from '../hooks/useApi'
import type { AgentAction, EnvState } from '../types/api'

type DemoRunRow = {
  level: number
  episodeId: string
  scenarioKey: string
  scenarioName: string
  incidents: number
  unhealthyPods: number
  reward: number
  status: string
}

const LEVEL_SEQUENCE = [1, 2, 3, 4, 5]

const DEMO_ACTION: AgentAction = {
  agent: 'diagnostics',
  action_type: 'query_metrics',
  target: 'svc-api',
}

function countUnhealthyPods(state: EnvState): number {
  const pods = state.cluster_state?.pods ?? {}
  return Object.values(pods).filter((pod) => !(pod as { ready?: boolean }).ready).length
}

export default function DemoModePage() {
  const [isRunning, setIsRunning] = useState(false)
  const [rows, setRows] = useState<DemoRunRow[]>([])
  const [liveNote, setLiveNote] = useState('Ready to run full demo tour.')
  const stopRef = useRef(false)

  const { data: health } = useHealth()
  const { data: scenarios } = useDemoScenarios()
  const { data: precomputed } = useDemoPrecomputed()

  const capabilities = useMemo(
    () => [
      {
        title: 'Dual LLM Routing',
        value:
          health?.ollama_available || health?.openrouter_available
            ? `${health?.ollama_available ? 'Ollama' : ''}${health?.ollama_available && health?.openrouter_available ? ' + ' : ''}${health?.openrouter_available ? 'OpenRouter' : ''}`
            : 'No LLM backend detected',
      },
      {
        title: 'Scenario Catalog',
        value: `${Object.keys(scenarios?.all_scenarios ?? {}).length} templates`,
      },
      {
        title: 'Precomputed Warm Cache',
        value: precomputed?.available ? 'Available' : 'Not generated yet',
      },
      {
        title: 'Realtime API',
        value: '/env + /demo + /ws/stream',
      },
    ],
    [health, precomputed?.available, scenarios?.all_scenarios],
  )

  const runShowcase = async () => {
    if (!scenarios) {
      setLiveNote('Scenario catalog unavailable. Check API connectivity first.')
      return
    }

    setIsRunning(true)
    stopRef.current = false
    setRows([])

    try {
      for (const level of LEVEL_SEQUENCE) {
        if (stopRef.current) {
          setLiveNote('Demo stopped by user.')
          break
        }

        setLiveNote(`Level ${level}: resetting episode...`)
        const reset = await envApi.reset(level)

        const recommended = scenarios.recommended?.[`level_${level}`]
        const fallback = Object.entries(scenarios.scenarios).find(([, value]) => value.level === level)
        const scenarioKey = recommended?.scenario_key ?? fallback?.[0] ?? ''
        const scenarioName = recommended?.name ?? fallback?.[1]?.name ?? 'Unknown scenario'

        if (scenarioKey) {
          setLiveNote(`Level ${level}: injecting ${scenarioKey}...`)
          await demoApi.injectIncident({
            scenario_key: scenarioKey,
            description: `Automated demo run for level ${level}`,
            level,
          })
        }

        let state = await envApi.getState()

        setLiveNote(`Level ${level}: stepping agents for live progression...`)
        for (let stepCount = 0; stepCount < 3; stepCount += 1) {
          const stepResponse = await envApi.step({
            episode_id: reset.episode_id,
            action: DEMO_ACTION,
          })

          const observation = stepResponse.observation
          if (observation?.episode_id) {
            state = observation
          } else {
            state = await envApi.getState()
          }

          if (stepResponse.terminated || stepResponse.truncated) {
            break
          }
        }

        setRows((prev) => [
          ...prev,
          {
            level,
            episodeId: state.episode_id,
            scenarioKey,
            scenarioName,
            incidents: state.active_incidents?.length ?? 0,
            unhealthyPods: countUnhealthyPods(state),
            reward: Number(state.cumulative_reward ?? 0),
            status: state.episode_status ?? 'running',
          },
        ])
      }

      setLiveNote('Demo tour complete. You can rerun it at any time.')
    } catch (error) {
      setLiveNote(`Demo failed: ${(error as Error).message}`)
    } finally {
      setIsRunning(false)
    }
  }

  const stopRequested = () => {
    stopRef.current = true
    setLiveNote('Stop requested. Demo will halt after current level step.')
  }

  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-primary" />
              Full Demo Mode
            </h1>
            <p className="text-slate-400 mt-2">
              One-click walkthrough across Levels 1-5 with scenario injection, live stepping, and capability proofs.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={runShowcase}
              disabled={isRunning}
              className="btn btn-primary inline-flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Run Full Demo
            </button>
            <button
              onClick={stopRequested}
              disabled={!isRunning}
              className="btn btn-secondary inline-flex items-center gap-2"
            >
              <Square className="w-4 h-4" />
              Stop
            </button>
          </div>
        </div>

        <div className="card">
          <div className="flex items-start gap-3">
            {liveNote.toLowerCase().includes('failed') ? (
              <AlertCircle className="w-5 h-5 text-danger mt-0.5" />
            ) : (
              <Activity className="w-5 h-5 text-primary mt-0.5" />
            )}
            <div>
              <div className="font-semibold">Live Status</div>
              <div className="text-slate-300 mt-1">{liveNote}</div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {capabilities.map((item) => (
            <div key={item.title} className="card">
              <div className="text-xs uppercase tracking-wide text-slate-400">{item.title}</div>
              <div className="text-lg font-semibold mt-2">{item.value}</div>
            </div>
          ))}
        </div>

        <div className="card overflow-x-auto">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle2 className="w-5 h-5 text-success" />
            <h2 className="text-xl font-bold">Scenario Walkthrough Results</h2>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="py-2 pr-3">Level</th>
                <th className="py-2 pr-3">Scenario</th>
                <th className="py-2 pr-3">Episode</th>
                <th className="py-2 pr-3">Incidents</th>
                <th className="py-2 pr-3">Unhealthy Pods</th>
                <th className="py-2 pr-3">Reward</th>
                <th className="py-2 pr-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.level}-${row.episodeId}`} className="border-b border-slate-800">
                  <td className="py-2 pr-3 font-semibold">L{row.level}</td>
                  <td className="py-2 pr-3">
                    <div className="font-medium">{row.scenarioName}</div>
                    <div className="text-xs text-slate-500">{row.scenarioKey}</div>
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs">{row.episodeId.slice(0, 14)}...</td>
                  <td className="py-2 pr-3">{row.incidents}</td>
                  <td className="py-2 pr-3">{row.unhealthyPods}</td>
                  <td className="py-2 pr-3">{row.reward.toFixed(3)}</td>
                  <td className="py-2 pr-3 capitalize">{row.status}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No run yet. Click Run Full Demo to generate a full capability showcase.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
