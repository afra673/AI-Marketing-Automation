import { useEffect, useState, useRef } from 'react'
import { ArrowRight } from 'lucide-react'
import api from '../api'

const AGENTS = [
  { name: 'strategy', label: 'Strategy', description: 'Analyzes goals and defines campaign strategy' },
  { name: 'research', label: 'Research', description: 'Gathers market data and competitor insights' },
  { name: 'writing', label: 'Writing', description: 'Generates blog posts, emails, and copy' },
  { name: 'design', label: 'Design', description: 'Creates visual assets and brand materials' },
  { name: 'distribution', label: 'Distribution', description: 'Schedules and publishes across channels' },
]

const STATUS_BADGE = {
  completed: 'bg-green-600/80 text-green-100',
  running: 'bg-yellow-600/80 text-yellow-100',
  failed: 'bg-red-600/80 text-red-100',
  idle: 'bg-slate-600 text-slate-200',
}

export default function AgentsPage() {
  const [agents, setAgents] = useState([])
  const [runningAgents, setRunningAgents] = useState({})
  const [logs, setLogs] = useState([])
  const logsEndRef = useRef(null)
  const logsPanelRef = useRef(null)

  useEffect(() => {
    api.get('/agents/status').then((res) => setAgents(res.data)).catch(console.error)
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) return

    const baseURL = api.defaults.baseURL || '/api/v1'
    const es = new EventSource(`${baseURL}/agents/logs?stream=true&token=${encodeURIComponent(token)}`)

    const handleLog = (event) => {
      try {
        const data = JSON.parse(event.data)
        setLogs((prev) => [...prev.slice(-99), data])
      } catch {
        setLogs((prev) => [...prev.slice(-99), { message: event.data, timestamp: new Date().toISOString() }])
      }
    }

    es.addEventListener('log', handleLog)
    es.onmessage = handleLog

    return () => es.close()
  }, [])

  useEffect(() => {
    if (logsPanelRef.current) {
      logsPanelRef.current.scrollTop = logsPanelRef.current.scrollHeight
    }
  }, [logs])

  const handleRun = async (agentName) => {
    setRunningAgents((prev) => ({ ...prev, [agentName]: true }))
    try {
      await api.post(`/agents/${agentName}/run`)
      const res = await api.get('/agents/status')
      setAgents(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setTimeout(() => {
        setRunningAgents((prev) => ({ ...prev, [agentName]: false }))
      }, 2000)
    }
  }

  const getAgentStatus = (name) => {
    const found = agents.find((a) => a.name === name)
    return found?.status || 'idle'
  }

  const formatTime = (iso) => {
    if (!iso) return 'Never'
    return new Date(iso).toLocaleString()
  }

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-lg font-semibold mb-4 text-slate-200">Agent Pipeline</h3>
        <div className="flex items-stretch gap-2 overflow-x-auto pb-2">
          {AGENTS.map((agent, idx) => (
            <div key={agent.name} className="flex items-center">
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 min-w-[180px] flex flex-col">
                <h4 className="font-semibold text-slate-100 capitalize">{agent.label}</h4>
                <p className="text-xs text-slate-400 mt-1 mb-3 flex-1">{agent.description}</p>
                <span className={`inline-block px-2 py-0.5 rounded text-xs capitalize mb-3 w-fit ${STATUS_BADGE[getAgentStatus(agent.name)]}`}>
                  {getAgentStatus(agent.name)}
                </span>
                <button
                  onClick={() => handleRun(agent.name)}
                  disabled={runningAgents[agent.name]}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors"
                >
                  {runningAgents[agent.name] ? 'Running...' : 'Run'}
                </button>
              </div>
              {idx < AGENTS.length - 1 && (
                <ArrowRight className="text-slate-500 mx-1 flex-shrink-0" size={24} />
              )}
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-3 text-slate-200">Live Logs</h3>
        <div
          ref={logsPanelRef}
          className="bg-slate-950 border border-slate-700 rounded-lg p-4 max-h-[300px] overflow-y-auto font-mono text-sm"
        >
          {logs.length === 0 && (
            <p className="text-slate-500">Waiting for log stream...</p>
          )}
          {logs.map((log, i) => (
            <div key={i} className="text-slate-300 py-0.5">
              <span className="text-slate-500">[{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '--:--:--'}]</span>
              {log.agent && <span className="text-indigo-400 ml-2 capitalize">[{log.agent}]</span>}
              <span className="ml-2">{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-3 text-slate-200">Token Usage</h3>
        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400">
                <th className="text-left p-3 font-medium">Agent</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-left p-3 font-medium">Tokens Used</th>
                <th className="text-left p-3 font-medium">Cost ($)</th>
                <th className="text-left p-3 font-medium">Last Run</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.name} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                  <td className="p-3 capitalize text-slate-200">{agent.name}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs capitalize ${STATUS_BADGE[agent.status]}`}>
                      {agent.status}
                    </span>
                  </td>
                  <td className="p-3 text-slate-300">{agent.tokens_used?.toLocaleString() || 0}</td>
                  <td className="p-3 text-slate-300">${(agent.cost_usd || 0).toFixed(4)}</td>
                  <td className="p-3 text-slate-400">{formatTime(agent.last_run)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
