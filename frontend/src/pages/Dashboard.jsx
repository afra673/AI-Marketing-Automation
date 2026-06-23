import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import api from '../api'

function StatusDot({ status }) {
  const colors = {
    completed: 'bg-green-500',
    running: 'bg-yellow-500',
    failed: 'bg-red-500',
    idle: 'bg-gray-500',
  }
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${colors[status] || colors.idle}`} />
}

function formatTime(iso) {
  if (!iso) return 'Never'
  return new Date(iso).toLocaleString()
}

export default function Dashboard() {
  const [overview, setOverview] = useState(null)
  const [agents, setAgents] = useState([])
  const [campaigns, setCampaigns] = useState([])
  const [recentLogs, setRecentLogs] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [newCampaign, setNewCampaign] = useState({ name: '', description: '', status: 'draft' })
  const [creating, setCreating] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/analytics/overview'),
      api.get('/agents/status'),
      api.get('/campaigns'),
      api.get('/agents/logs'),
    ]).then(([ov, ag, camp, logs]) => {
      setOverview(ov.data)
      setAgents(ag.data)
      setCampaigns(camp.data)
      setRecentLogs(logs.data)
    }).catch(console.error)
  }, [])

  const activeAgents = agents.filter((a) => a.status === 'running' || a.status === 'completed').length
  const publishedCount = overview ? Math.round(overview.total_views / 500) : 0
  const avgEngagement = overview && overview.total_views > 0
    ? ((overview.total_clicks / overview.total_views) * 100).toFixed(1) + '%'
    : '0%'

  const handleCreateCampaign = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      await api.post('/campaigns', newCampaign)
      const res = await api.get('/campaigns')
      setCampaigns(res.data)
      setShowModal(false)
      setNewCampaign({ name: '', description: '' })
    } catch (err) {
      console.error(err)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteCampaign = async (campaignId) => {
    const confirmed = window.confirm('Delete this campaign and its related content?')
    if (!confirmed) return
    setDeletingId(campaignId)
    try {
      await api.delete(`/campaigns/${campaignId}`)
      const res = await api.get('/campaigns')
      setCampaigns(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Campaigns" value={campaigns.length} />
        <StatCard label="Content Published" value={publishedCount} />
        <StatCard label="Avg Engagement" value={avgEngagement} />
        <StatCard label="Active Agents" value={activeAgents} />
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-200">Campaigns</h3>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
          >
            <Plus size={16} />
            New Campaign
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {campaigns.map((campaign) => (
            <div key={campaign.id} className="bg-slate-900/80 border border-slate-700 rounded-lg p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-slate-100">{campaign.name}</h4>
                  <p className="text-xs text-slate-400 mt-1">{campaign.description || 'No description provided'}</p>
                </div>
                <span className="px-2 py-0.5 rounded text-xs capitalize bg-slate-700 text-slate-200">{campaign.status}</span>
              </div>
              <div className="mt-4 flex items-center justify-between gap-3">
                <p className="text-xs text-slate-500">
                  Goals: {campaign.goals?.length ? campaign.goals.join(', ') : 'None'}
                </p>
                <button
                  onClick={() => handleDeleteCampaign(campaign.id)}
                  disabled={deletingId === campaign.id}
                  className="inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-slate-600 text-slate-300 hover:text-white hover:border-red-500 hover:bg-red-500/10 disabled:opacity-50"
                >
                  <Trash2 size={14} />
                  {deletingId === campaign.id ? 'Deleting' : 'Delete'}
                </button>
              </div>
            </div>
          ))}
          {campaigns.length === 0 && (
            <p className="text-slate-400 text-sm">No campaigns yet. Create one to start.</p>
          )}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-3 text-slate-200">Agent Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {agents.map((agent) => (
            <div key={agent.name} className="bg-slate-800 rounded-lg border border-slate-700 p-4">
              <div className="flex items-center gap-2 mb-2">
                <StatusDot status={agent.status} />
                <span className="font-medium capitalize text-slate-100">{agent.name}</span>
              </div>
              <p className="text-xs text-slate-400 mb-1">Last run: {formatTime(agent.last_run)}</p>
              <p className="text-xs text-slate-400">Tokens: {agent.tokens_used?.toLocaleString() || 0}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-5">
          <h3 className="text-lg font-semibold mb-4 text-slate-200">Recent Activity</h3>
          <ul className="space-y-3">
            {recentLogs.slice(0, 10).map((log) => (
              <li key={log.id} className="flex items-center justify-between text-sm border-b border-slate-700 pb-2">
                <div className="flex items-center gap-2">
                  <StatusDot status={log.status} />
                  <span className="capitalize text-slate-300">{log.agent_name}</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-400 capitalize">{log.status}</span>
                  <p className="text-xs text-slate-500">{formatTime(log.started_at)}</p>
                </div>
              </li>
            ))}
            {recentLogs.length === 0 && (
              <li className="text-slate-400 text-sm">No recent activity</li>
            )}
          </ul>
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 p-5 flex flex-col justify-center items-center">
          <h3 className="text-lg font-semibold mb-4 text-slate-200">Quick Actions</h3>
          <button
            onClick={() => setShowModal(true)}
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors inline-flex items-center gap-2"
          >
            <Plus size={16} />
            Launch New Campaign
          </button>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4 text-slate-100">Launch New Campaign</h3>
            <form onSubmit={handleCreateCampaign} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Campaign Name</label>
                <input
                  value={newCampaign.name}
                  onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })}
                  required
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Description</label>
                <textarea
                  value={newCampaign.description}
                  onChange={(e) => setNewCampaign({ ...newCampaign, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Status</label>
                <select
                  value={newCampaign.status}
                  onChange={(e) => setNewCampaign({ ...newCampaign, status: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="completed">Completed</option>
                </select>
              </div>
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-slate-400 hover:text-white border border-slate-600 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create Campaign'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-5">
      <p className="text-sm text-slate-400 mb-1">{label}</p>
      <p className="text-3xl font-bold text-slate-100">{value}</p>
    </div>
  )
}
