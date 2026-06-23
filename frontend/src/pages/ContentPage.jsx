import { useEffect, useState } from 'react'
import { Plus, Trash2, X } from 'lucide-react'
import api from '../api'

const TYPE_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'blog', label: 'Blog' },
  { value: 'social_twitter', label: 'Social Twitter' },
  { value: 'social_linkedin', label: 'Social LinkedIn' },
  { value: 'email', label: 'Email' },
  { value: 'newsletter', label: 'Newsletter' },
]

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'review', label: 'Review' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'published', label: 'Published' },
]

const TYPE_BADGE = {
  blog: 'bg-indigo-600 text-white',
  social_twitter: 'bg-violet-600 text-white',
  social_linkedin: 'bg-violet-600 text-white',
  email: 'bg-amber-600 text-white',
  newsletter: 'bg-emerald-600 text-white',
}

const STATUS_BADGE = {
  draft: 'bg-slate-600 text-slate-200',
  review: 'bg-yellow-600 text-yellow-100',
  scheduled: 'bg-blue-600 text-blue-100',
  published: 'bg-green-600 text-green-100',
}

export default function ContentPage() {
  const [items, setItems] = useState([])
  const [campaigns, setCampaigns] = useState([])
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [loading, setLoading] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [newContent, setNewContent] = useState({
    campaign_id: '',
    title: '',
    content_type: 'blog',
    status: 'draft',
    body: '',
  })

  const fetchContent = async () => {
    setLoading(true)
    try {
      const params = {}
      if (search) params.search = search
      if (type) params.type = type
      if (status) params.status = status
      const res = await api.get('/content', { params })
      setItems(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchContent()
  }, [search, type, status])

  useEffect(() => {
    api.get('/campaigns').then((res) => setCampaigns(res.data)).catch(console.error)
  }, [])

  const handlePublish = async (id) => {
    await api.post(`/content/${id}/publish`)
    fetchContent()
  }

  const handleSchedule = async (id) => {
    await api.post(`/content/${id}/schedule`)
    fetchContent()
  }

  const handleCreateContent = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const payload = {
        ...newContent,
        campaign_id: newContent.campaign_id ? Number(newContent.campaign_id) : undefined,
      }
      await api.post('/content', payload)
      setShowCreateModal(false)
      setNewContent({
        campaign_id: '',
        title: '',
        content_type: 'blog',
        status: 'draft',
        body: '',
      })
      fetchContent()
    } catch (err) {
      console.error(err)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteContent = async (id) => {
    const confirmed = window.confirm('Delete this content item?')
    if (!confirmed) return
    setDeletingId(id)
    try {
      await api.delete(`/content/${id}`)
      fetchContent()
    } catch (err) {
      console.error(err)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <input
          type="text"
          placeholder="Search content..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
        >
          <Plus size={16} />
          Add Content
        </button>
      </div>

      {loading && <p className="text-slate-400">Loading...</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((item) => (
          <div key={item.id} className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
            <div className="h-32 bg-slate-700 flex items-center justify-center text-slate-500 text-sm">
              Thumbnail
            </div>
            <div className="p-4">
              <button
                onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                className="text-left w-full font-medium text-slate-100 hover:text-indigo-400 transition-colors mb-2"
              >
                {item.title}
              </button>
              <div className="flex flex-wrap gap-2 mb-3">
                <span className={`px-2 py-0.5 rounded text-xs capitalize ${TYPE_BADGE[item.content_type] || 'bg-slate-600'}`}>
                  {item.content_type.replace('_', ' ')}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs capitalize ${STATUS_BADGE[item.status]}`}>
                  {item.status}
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                Created: {new Date(item.created_at).toLocaleDateString()}
              </p>
              {expanded === item.id && (
                <p className="text-sm text-slate-300 mb-3 border-t border-slate-700 pt-3 line-clamp-4">
                  {item.body}
                </p>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => handlePublish(item.id)}
                  className="flex-1 px-3 py-1.5 bg-green-600/80 hover:bg-green-600 text-white text-sm rounded-lg transition-colors"
                >
                  Publish
                </button>
                <button
                  onClick={() => handleSchedule(item.id)}
                  className="flex-1 px-3 py-1.5 bg-blue-600/80 hover:bg-blue-600 text-white text-sm rounded-lg transition-colors"
                >
                  Schedule
                </button>
                <button
                  onClick={() => handleDeleteContent(item.id)}
                  disabled={deletingId === item.id}
                  className="px-3 py-1.5 bg-slate-700 hover:bg-red-600/80 text-slate-200 text-sm rounded-lg transition-colors disabled:opacity-50"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {!loading && items.length === 0 && (
        <p className="text-slate-400 text-center py-8">No content found.</p>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 w-full max-w-2xl relative">
            <button onClick={() => setShowCreateModal(false)} className="absolute top-4 right-4 text-slate-400 hover:text-white">
              <X size={20} />
            </button>
            <h3 className="text-lg font-semibold mb-4 text-slate-100">Add Content</h3>
            <form onSubmit={handleCreateContent} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Campaign</label>
                <select
                  value={newContent.campaign_id}
                  onChange={(e) => setNewContent({ ...newContent, campaign_id: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Auto-select first campaign</option>
                  {campaigns.map((campaign) => (
                    <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Content Type</label>
                <select
                  value={newContent.content_type}
                  onChange={(e) => setNewContent({ ...newContent, content_type: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                >
                  {TYPE_OPTIONS.filter((o) => o.value).map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Title</label>
                <input
                  value={newContent.title}
                  onChange={(e) => setNewContent({ ...newContent, title: e.target.value })}
                  required
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Status</label>
                <select
                  value={newContent.status}
                  onChange={(e) => setNewContent({ ...newContent, status: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                >
                  {STATUS_OPTIONS.filter((o) => o.value).map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm text-slate-400 mb-1">Body</label>
                <textarea
                  value={newContent.body}
                  onChange={(e) => setNewContent({ ...newContent, body: e.target.value })}
                  rows={5}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="md:col-span-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-slate-400 hover:text-white border border-slate-600 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-50"
                >
                  {creating ? 'Saving...' : 'Create Content'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
