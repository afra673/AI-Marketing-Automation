/* AI Marketing Automation — Full SPA (no build required) */
const API = '/api/v1';

const NAV = [
  { path: '/', label: 'Dashboard', icon: 'dashboard' },
  { path: '/calendar', label: 'Calendar', icon: 'calendar_month' },
  { path: '/agents', label: 'Agents', icon: 'smart_toy' },
  { path: '/content', label: 'Content', icon: 'description' },
  { path: '/analytics', label: 'Analytics', icon: 'monitoring' },
  { path: '/integrations', label: 'Integrations', icon: 'hub' },
  { path: '/settings', label: 'Settings', icon: 'settings' },
];

const PAGE_TITLES = {
  '/': 'Dashboard',
  '/calendar': 'Editorial Calendar',
  '/agents': 'Agent Control',
  '/content': 'Content Library',
  '/analytics': 'Analytics',
  '/integrations': 'Integrations',
  '/settings': 'Settings',
};

let sseSource = null;
let chartInstances = [];

function getToken() { return localStorage.getItem('token'); }
function getUser() { try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; } }
function setAuth(token, user) {
  localStorage.setItem('token', token);
  localStorage.setItem('user', JSON.stringify(user));
}
function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(API + path, { ...options, headers });
  if (res.status === 401) {
    clearAuth();
    navigate('/login');
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res.text();
}

function navigate(path) {
  if (path === '/login') {
    history.pushState({}, '', '/login');
  } else {
    history.pushState({}, '', path);
  }
  render();
}

function icon(name) {
  return `<span class="material-symbols-outlined" style="font-size:20px">${name}</span>`;
}

function statusDot(status) {
  const colors = { completed: '#22c55e', running: '#eab308', failed: '#ef4444', idle: '#6b7280' };
  return `<span class="status-dot" style="background:${colors[status] || colors.idle}"></span>`;
}

function badge(text, color) {
  return `<span class="badge" style="background:${color};color:#fff">${text}</span>`;
}

function formatTime(iso) {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleString();
}

function destroyCharts() {
  chartInstances.forEach(c => c.destroy());
  chartInstances = [];
}

function closeSSE() {
  if (sseSource) { sseSource.close(); sseSource = null; }
}

/* ─── LOGIN ─── */
function renderLogin() {
  closeSSE();
  destroyCharts();
  document.getElementById('app').innerHTML = `
    <div class="login-page">
      <div class="glass-card modal" style="max-width:420px">
        <div style="text-align:center;margin-bottom:24px">
          <h1 style="font-family:'Instrument Serif',serif;font-size:28px;color:#b8d0ff;margin:0 0 8px">AI Marketing Automation</h1>
          <p style="color:#8d909c;margin:0">AI-Powered Marketing Platform</p>
        </div>
        <div id="login-error"></div>
        <form id="login-form">
          <label style="display:block;color:#8d909c;font-size:13px;margin-bottom:4px">Email</label>
          <input type="email" id="email" value="admin@demo.com" required style="margin-bottom:12px" />
          <label style="display:block;color:#8d909c;font-size:13px;margin-bottom:4px">Password</label>
          <input type="password" id="password" value="password123" required style="margin-bottom:16px" />
          <button type="submit" class="btn-primary" style="width:100%">Login</button>
        </form>
        <div class="glass-card" style="margin-top:16px;padding:12px;text-align:center;font-size:13px;color:#8d909c">
          Demo: <strong style="color:#e2e2e8">admin@demo.com</strong> / <strong style="color:#e2e2e8">password123</strong>
        </div>
      </div>
    </div>`;

  document.getElementById('login-form').onsubmit = async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('login-error');
    errEl.innerHTML = '';
    try {
      const data = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: document.getElementById('email').value,
          password: document.getElementById('password').value,
        }),
      });
      setAuth(data.access_token, data.user);
      navigate('/');
    } catch (err) {
      errEl.innerHTML = `<div class="error-msg">${err.message || 'Login failed'}</div>`;
    }
  };
}

/* ─── LAYOUT ─── */
function renderShell(title, subtitle, bodyHtml) {
  const path = location.pathname === '/login' ? '/' : location.pathname;
  const user = getUser();
  const navHtml = NAV.map(n => `
    <button class="nav-link ${path === n.path ? 'active' : ''}" data-nav="${n.path}">
      ${icon(n.icon)} ${n.label}
    </button>`).join('');

  document.getElementById('app').innerHTML = `
    <aside class="sidebar">
      <div style="padding:24px 24px 16px">
        <h1 style="font-family:'Instrument Serif',serif;font-size:22px;color:#b8d0ff;margin:0">AI Marketing Automation</h1>
        <div style="display:flex;align-items:center;gap:8px;margin-top:8px">
          <span class="status-dot" style="background:#4ddcc6"></span>
          <span style="font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:#8d909c">AI Active</span>
        </div>
      </div>
      <nav style="flex:1;padding:0 12px">${navHtml}</nav>
      <div style="padding:16px 24px;border-top:1px solid rgba(67,71,81,0.2)">
        <button class="btn-primary" style="width:100%;margin-bottom:12px" id="sidebar-new-campaign">New Campaign</button>
        <button class="nav-link" id="logout-btn" style="color:#ffb4ab">${icon('logout')} Logout</button>
      </div>
    </aside>
    <main class="main-content">
      <header style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:32px;flex-wrap:wrap;gap:16px">
        <div>
          <h2 style="font-family:'Instrument Serif',serif;font-size:32px;margin:0 0 4px;color:#e2e2e8">${title}</h2>
          ${subtitle ? `<p style="color:#8d909c;margin:0">${subtitle}</p>` : ''}
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="color:#8d909c;font-size:14px">${user?.name || 'User'}</span>
        </div>
      </header>
      <div id="page-body">${bodyHtml}</div>
    </main>
    <div id="modal-root"></div>`;

  document.querySelectorAll('[data-nav]').forEach(el => {
    el.onclick = () => navigate(el.dataset.nav);
  });
  document.getElementById('logout-btn').onclick = () => { clearAuth(); navigate('/login'); };
  document.getElementById('sidebar-new-campaign').onclick = () => showCampaignModal();
}

function showCampaignModal(onSuccess) {
  const root = document.getElementById('modal-root');
  root.innerHTML = `
    <div class="modal-overlay" id="modal-close-overlay">
      <div class="modal" onclick="event.stopPropagation()">
        <h3 style="margin:0 0 16px;color:#e2e2e8">Launch New Campaign</h3>
        <label style="color:#8d909c;font-size:13px">Campaign Name</label>
        <input id="camp-name" style="margin:4px 0 12px" />
        <label style="color:#8d909c;font-size:13px">Description</label>
        <textarea id="camp-desc" rows="3" style="margin:4px 0 16px"></textarea>
        <label style="color:#8d909c;font-size:13px">Status</label>
        <select id="camp-status" style="margin:4px 0 16px">
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
        </select>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn-secondary" id="modal-cancel">Cancel</button>
          <button class="btn-primary" id="modal-save">Create Campaign</button>
        </div>
      </div>
    </div>`;
  document.getElementById('modal-cancel').onclick = () => { root.innerHTML = ''; };
  document.getElementById('modal-close-overlay').onclick = (e) => {
    if (e.target.id === 'modal-close-overlay') root.innerHTML = '';
  };
  document.getElementById('modal-save').onclick = async () => {
    await api('/campaigns', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('camp-name').value,
        description: document.getElementById('camp-desc').value,
        status: document.getElementById('camp-status').value,
      }),
    });
    root.innerHTML = '';
    if (onSuccess) onSuccess();
    else if (location.pathname === '/') renderDashboard();
  };
}

/* ─── DASHBOARD ─── */
async function renderDashboard() {
  renderShell('Dashboard', 'Overview of campaigns, agents, and activity.', '<p style="color:#8d909c">Loading...</p>');
  try {
    const [overview, agents, campaigns, logs] = await Promise.all([
      api('/analytics/overview'),
      api('/agents/status'),
      api('/campaigns'),
      api('/agents/logs'),
    ]);
    const activeAgents = agents.filter(a => a.status === 'running' || a.status === 'completed').length;
    const engagement = overview.total_views > 0
      ? ((overview.total_clicks / overview.total_views) * 100).toFixed(1) + '%' : '0%';

    document.getElementById('page-body').innerHTML = `
      <div class="stat-grid">
        ${statCard('Total Campaigns', campaigns.length, 'campaign')}
        ${statCard('Total Views', overview.total_views.toLocaleString(), 'visibility')}
        ${statCard('Avg Engagement', engagement, 'insights')}
        ${statCard('Active Agents', activeAgents, 'smart_toy')}
      </div>
      <div class="glass-card" style="padding:20px;margin:24px 0">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:12px;flex-wrap:wrap">
          <h3 style="color:#e2e2e8;margin:0">Campaigns</h3>
          <button class="btn-primary" id="dashboard-new-campaign" style="padding:10px 14px">New Campaign</button>
        </div>
        <div class="card-grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr))">
          ${campaigns.map(c => `
            <div class="glass-card" style="padding:16px">
              <div style="display:flex;justify-content:space-between;gap:12px;align-items:start">
                <div>
                  <h4 style="margin:0 0 6px;color:#e2e2e8">${c.name}</h4>
                  <p style="font-size:12px;color:#8d909c;margin:0 0 10px">${c.description || 'No description provided'}</p>
                </div>
                <span class="badge" style="background:#334155">${c.status}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:12px">
                <span style="font-size:12px;color:#8d909c">${(c.goals || []).length ? c.goals.join(', ') : 'No goals set'}</span>
                <button class="btn-secondary" data-delete-campaign="${c.id}" style="padding:8px 10px">Delete</button>
              </div>
            </div>`).join('')}
        </div>
      </div>
      <h3 style="color:#e2e2e8;margin-bottom:12px">Agent Status</h3>
      <div class="stat-grid" style="margin-bottom:24px">
        ${agents.map(a => `
          <div class="glass-card" style="padding:16px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              ${statusDot(a.status)}
              <strong style="text-transform:capitalize;color:#e2e2e8">${a.name}</strong>
            </div>
            <p style="font-size:12px;color:#8d909c;margin:4px 0">Last run: ${formatTime(a.last_run)}</p>
            <p style="font-size:12px;color:#8d909c;margin:0">Tokens: ${(a.tokens_used || 0).toLocaleString()}</p>
          </div>`).join('')}
      </div>
      <div class="glass-card" style="padding:20px">
        <h3 style="color:#e2e2e8;margin:0 0 16px">Recent Activity</h3>
        ${(logs.slice(0, 10)).map(l => `
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(67,71,81,0.2);font-size:13px">
            <span style="display:flex;align-items:center;gap:8px">
              ${statusDot(l.status)}
              <span style="text-transform:capitalize;color:#e2e2e8">${l.agent_name}</span>
            </span>
            <span style="color:#8d909c">${formatTime(l.started_at)}</span>
          </div>`).join('') || '<p style="color:#8d909c">No activity yet</p>'}
      </div>`;
    document.getElementById('dashboard-new-campaign').onclick = () => showCampaignModal(renderDashboard);
    document.querySelectorAll('[data-delete-campaign]').forEach(btn => {
      btn.onclick = async () => {
        if (!confirm('Delete this campaign and its related content?')) return;
        await api(`/campaigns/${btn.dataset.deleteCampaign}`, { method: 'DELETE' });
        renderDashboard();
      };
    });
  } catch (e) {
    document.getElementById('page-body').innerHTML = `<div class="error-msg">${e.message}</div>`;
  }
}

function statCard(label, value, ic) {
  return `<div class="glass-card" style="padding:20px">
    <div style="display:flex;justify-content:space-between;align-items:start">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#8d909c">${label}</span>
      ${icon(ic)}
    </div>
    <div class="gradient-text" style="font-size:36px;font-weight:700;margin-top:12px">${value}</div>
  </div>`;
}

/* ─── CALENDAR ─── */
let calYear, calMonth;
async function renderCalendar() {
  const now = new Date();
  if (calYear === undefined) { calYear = now.getFullYear(); calMonth = now.getMonth(); }
  renderShell('Editorial Calendar', 'Content schedule across the month.', '<p style="color:#8d909c">Loading...</p>');
  try {
    const content = await api('/content');
    const monthName = new Date(calYear, calMonth).toLocaleString('default', { month: 'long', year: 'numeric' });
    const firstDay = new Date(calYear, calMonth, 1).getDay();
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const weekdays = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    const typeColors = {
      blog: '#aac7ff', social_twitter: '#a78bfa', social_linkedin: '#a78bfa',
      email: '#fbbf24', newsletter: '#34d399',
    };

    let cells = '';
    for (let i = 0; i < firstDay; i++) cells += `<div class="calendar-cell" style="background:#0c0e13"></div>`;
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${calYear}-${String(calMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const dayItems = content.filter(c => {
        const dt = c.scheduled_at || c.created_at;
        return dt && dt.startsWith(dateStr);
      });
      const isToday = d === now.getDate() && calMonth === now.getMonth() && calYear === now.getFullYear();
      cells += `<div class="calendar-cell" style="${isToday ? 'outline:2px solid #4ddcc6' : ''}">
        <strong style="color:${isToday ? '#4ddcc6' : '#8d909c'}">${d}</strong>
        ${dayItems.map(item => `
          <div class="content-card-mini" style="border-left-color:${typeColors[item.content_type] || '#aac7ff'}"
               data-content-id="${item.id}" title="${item.title}">
            ${item.title}
          </div>`).join('')}
      </div>`;
    }

    document.getElementById('page-body').innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="margin:0;color:#e2e2e8;font-family:'Instrument Serif',serif">${monthName}</h3>
        <div style="display:flex;gap:8px">
          <button class="btn-secondary" id="cal-prev">${icon('chevron_left')}</button>
          <button class="btn-secondary" id="cal-next">${icon('chevron_right')}</button>
        </div>
      </div>
      <div class="glass-card" style="overflow:hidden">
        <div class="calendar-grid">${weekdays.map(w => `<div style="padding:10px;text-align:center;font-size:12px;color:#8d909c;border-bottom:1px solid rgba(67,71,81,0.2)">${w}</div>`).join('')}${cells}</div>
      </div>`;

    document.getElementById('cal-prev').onclick = () => {
      calMonth--; if (calMonth < 0) { calMonth = 11; calYear--; }
      renderCalendar();
    };
    document.getElementById('cal-next').onclick = () => {
      calMonth++; if (calMonth > 11) { calMonth = 0; calYear++; }
      renderCalendar();
    };
    document.querySelectorAll('[data-content-id]').forEach(el => {
      el.onclick = () => {
        const item = content.find(c => c.id == el.dataset.contentId);
        if (item) showContentModal(item);
      };
    });
  } catch (e) {
    document.getElementById('page-body').innerHTML = `<div class="error-msg">${e.message}</div>`;
  }
}

function showContentModal(item) {
  const root = document.getElementById('modal-root');
  root.innerHTML = `
    <div class="modal-overlay" id="modal-close-overlay">
      <div class="modal" style="max-width:560px" onclick="event.stopPropagation()">
        <h3 style="margin:0 0 8px;color:#e2e2e8">${item.title}</h3>
        <p style="font-size:12px;color:#8d909c;margin:0 0 12px">${item.content_type.replace(/_/g,' ')} · ${item.status}</p>
        <p style="color:#c3c6d2;font-size:14px;line-height:1.6;white-space:pre-wrap">${item.body || ''}</p>
        <button class="btn-secondary" style="margin-top:16px" onclick="document.getElementById('modal-root').innerHTML=''">Close</button>
      </div>
    </div>`;
  document.getElementById('modal-close-overlay').onclick = (e) => {
    if (e.target.id === 'modal-close-overlay') root.innerHTML = '';
  };
}

/* ─── AGENTS ─── */
const AGENT_INFO = [
  { name: 'strategy', label: 'Strategy', desc: 'Analyzes goals and defines campaign strategy' },
  { name: 'research', label: 'Research', desc: 'Gathers market data and competitor insights' },
  { name: 'writing', label: 'Writing', desc: 'Generates blog posts, emails, and copy' },
  { name: 'design', label: 'Design', desc: 'Creates visual assets and brand materials' },
  { name: 'distribution', label: 'Distribution', desc: 'Schedules and publishes across channels' },
];

async function renderAgents() {
  renderShell('Agent Control', 'Run and monitor the AI marketing pipeline.', '<p style="color:#8d909c">Loading...</p>');
  closeSSE();
  try {
    const agents = await api('/agents/status');
    const statusMap = Object.fromEntries(agents.map(a => [a.name, a]));

    document.getElementById('page-body').innerHTML = `
      <h3 style="color:#e2e2e8;margin-bottom:12px">Pipeline</h3>
      <div class="pipeline-row" style="margin-bottom:32px">
        ${AGENT_INFO.map((a, i) => {
          const st = statusMap[a.name]?.status || 'idle';
          return `${i > 0 ? `<span style="color:#8d909c;font-size:20px">→</span>` : ''}
          <div class="glass-card pipeline-box" style="padding:16px">
            <strong style="color:#e2e2e8">${a.label}</strong>
            <p style="font-size:11px;color:#8d909c;margin:6px 0 10px">${a.desc}</p>
            ${badge(st, st === 'completed' ? '#166534' : st === 'running' ? '#854d0e' : st === 'failed' ? '#991b1b' : '#434751')}
            <button class="btn-primary" style="margin-top:10px;width:100%;font-size:12px;padding:8px" data-run-agent="${a.name}">Run</button>
          </div>`;
        }).join('')}
      </div>
      <h3 style="color:#e2e2e8;margin-bottom:8px">Live Logs</h3>
      <div class="logs-panel" id="live-logs"><p style="color:#6b7280">Connecting to log stream...</p></div>
      <h3 style="color:#e2e2e8;margin:24px 0 12px">Token Usage</h3>
      <div class="glass-card" style="overflow:hidden">
        <table>
          <thead><tr><th>Agent</th><th>Status</th><th>Tokens</th><th>Cost ($)</th><th>Last Run</th></tr></thead>
          <tbody>${agents.map(a => `
            <tr>
              <td style="text-transform:capitalize;color:#e2e2e8">${a.name}</td>
              <td>${badge(a.status, a.status === 'completed' ? '#166534' : a.status === 'running' ? '#854d0e' : '#434751')}</td>
              <td>${(a.tokens_used||0).toLocaleString()}</td>
              <td>$${(a.cost_usd||0).toFixed(4)}</td>
              <td style="color:#8d909c">${formatTime(a.last_run)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;

    document.querySelectorAll('[data-run-agent]').forEach(btn => {
      btn.onclick = async () => {
        btn.textContent = 'Running...';
        btn.disabled = true;
        await api(`/agents/${btn.dataset.runAgent}/run`, { method: 'POST' });
        setTimeout(() => renderAgents(), 1500);
      };
    });

    startSSE();
  } catch (e) {
    document.getElementById('page-body').innerHTML = `<div class="error-msg">${e.message}</div>`;
  }
}

function startSSE() {
  const token = getToken();
  if (!token) return;
  sseSource = new EventSource(`/api/v1/agents/logs?stream=true&token=${encodeURIComponent(token)}`);
  const panel = () => document.getElementById('live-logs');
  sseSource.addEventListener('log', (e) => {
    const el = panel();
    if (!el) return;
    try {
      const d = JSON.parse(e.data);
      if (el.querySelector('p')) el.innerHTML = '';
      el.innerHTML += `<div style="padding:2px 0;color:#c3c6d2"><span style="color:#6b7280">[${new Date(d.timestamp).toLocaleTimeString()}]</span> <span style="color:#4ddcc6">[${d.agent}]</span> ${d.message}</div>`;
      el.scrollTop = el.scrollHeight;
    } catch { /* ignore */ }
  });
}

/* ─── CONTENT ─── */
let contentFilters = { search: '', type: '', status: '' };
async function renderContent() {
  renderShell('Content Library', 'Manage and publish marketing content.', '<p style="color:#8d909c">Loading...</p>');
  closeSSE();
  try {
    const params = new URLSearchParams();
    if (contentFilters.search) params.set('search', contentFilters.search);
    if (contentFilters.type) params.set('type', contentFilters.type);
    if (contentFilters.status) params.set('status', contentFilters.status);
    const qs = params.toString() ? '?' + params.toString() : '';
    const [items, campaigns] = await Promise.all([
      api('/content' + qs),
      api('/campaigns'),
    ]);

    document.getElementById('page-body').innerHTML = `
      <div style="display:flex;flex-wrap:gap:12px;margin-bottom:20px;align-items:center">
        <input id="content-search" placeholder="Search content..." value="${contentFilters.search}" style="flex:1;min-width:180px" />
        <select id="content-type" style="width:auto">
          <option value="">All Types</option>
          <option value="blog">Blog</option>
          <option value="social_twitter">Social Twitter</option>
          <option value="social_linkedin">Social LinkedIn</option>
          <option value="email">Email</option>
          <option value="newsletter">Newsletter</option>
        </select>
        <select id="content-status" style="width:auto">
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="review">Review</option>
          <option value="scheduled">Scheduled</option>
          <option value="published">Published</option>
        </select>
        <button class="btn-primary" id="content-add-btn" style="padding:10px 14px">Add Content</button>
      </div>
      <div class="card-grid" id="content-grid">
        ${items.length ? items.map(item => contentCard(item)).join('') : '<p style="color:#8d909c">No content found.</p>'}
      </div>`;

    document.getElementById('content-type').value = contentFilters.type;
    document.getElementById('content-status').value = contentFilters.status;
    document.getElementById('content-add-btn').onclick = () => showContentModal(campaigns, renderContent);
    let searchTimer;
    document.getElementById('content-search').oninput = (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => { contentFilters.search = e.target.value; renderContent(); }, 300);
    };
    document.getElementById('content-type').onchange = (e) => { contentFilters.type = e.target.value; renderContent(); };
    document.getElementById('content-status').onchange = (e) => { contentFilters.status = e.target.value; renderContent(); };

    document.querySelectorAll('[data-publish]').forEach(btn => {
      btn.onclick = async () => { await api(`/content/${btn.dataset.publish}/publish`, { method: 'POST' }); renderContent(); };
    });
    document.querySelectorAll('[data-schedule]').forEach(btn => {
      btn.onclick = async () => { await api(`/content/${btn.dataset.schedule}/schedule`, { method: 'POST' }); renderContent(); };
    });
    document.querySelectorAll('[data-delete-content]').forEach(btn => {
      btn.onclick = async () => {
        if (!confirm('Delete this content item?')) return;
        await api(`/content/${btn.dataset.deleteContent}`, { method: 'DELETE' });
        renderContent();
      };
    });
    document.querySelectorAll('[data-expand]').forEach(btn => {
      btn.onclick = () => {
        const body = document.getElementById('body-' + btn.dataset.expand);
        body.classList.toggle('hidden');
      };
    });
  } catch (e) {
    document.getElementById('page-body').innerHTML = `<div class="error-msg">${e.message}</div>`;
  }
}

function contentCard(item) {
  const typeColors = { blog: '#4f46e5', social_twitter: '#7c3aed', social_linkedin: '#7c3aed', email: '#d97706', newsletter: '#059669' };
  const statusColors = { draft: '#475569', review: '#ca8a04', scheduled: '#2563eb', published: '#16a34a' };
  return `<div class="glass-card" style="overflow:hidden">
    <div style="height:100px;background:#282a2f;display:flex;align-items:center;justify-content:center;color:#6b7280;font-size:13px">Thumbnail</div>
    <div style="padding:16px">
      <button data-expand="${item.id}" style="background:none;border:none;color:#e2e2e8;font-weight:600;font-size:15px;cursor:pointer;text-align:left;padding:0;margin-bottom:8px">${item.title}</button>
      <div style="display:flex;gap:6px;margin-bottom:8px">
        ${badge(item.content_type.replace(/_/g,' '), typeColors[item.content_type] || '#475569')}
        ${badge(item.status, statusColors[item.status] || '#475569')}
      </div>
      <p style="font-size:12px;color:#8d909c;margin:0 0 8px">Created: ${new Date(item.created_at).toLocaleDateString()}</p>
      <p id="body-${item.id}" class="hidden" style="font-size:13px;color:#c3c6d2;border-top:1px solid rgba(67,71,81,0.3);padding-top:8px;margin:0 0 12px">${item.body || ''}</p>
      <div style="display:flex;gap:8px">
        <button class="btn-primary" style="flex:1;font-size:12px;padding:8px" data-publish="${item.id}">Publish</button>
        <button class="btn-secondary" style="flex:1" data-schedule="${item.id}">Schedule</button>
        <button class="btn-secondary" style="padding:8px 10px" data-delete-content="${item.id}">Delete</button>
      </div>
    </div>
  </div>`;
}

function showContentModal(campaigns, onSuccess) {
  const root = document.getElementById('modal-root');
  root.innerHTML = `
    <div class="modal-overlay" id="content-modal-close">
      <div class="modal" onclick="event.stopPropagation()" style="max-width:720px">
        <h3 style="margin:0 0 16px;color:#e2e2e8">Add Content</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div>
            <label style="color:#8d909c;font-size:13px">Campaign</label>
            <select id="content-campaign" style="margin:4px 0 12px">
              <option value="">Auto-select first campaign</option>
              ${campaigns.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}
            </select>
          </div>
          <div>
            <label style="color:#8d909c;font-size:13px">Content Type</label>
            <select id="content-type-create" style="margin:4px 0 12px">
              <option value="blog">Blog</option>
              <option value="social_twitter">Social Twitter</option>
              <option value="social_linkedin">Social LinkedIn</option>
              <option value="email">Email</option>
              <option value="newsletter">Newsletter</option>
            </select>
          </div>
          <div>
            <label style="color:#8d909c;font-size:13px">Title</label>
            <input id="content-title" style="margin:4px 0 12px" />
          </div>
          <div>
            <label style="color:#8d909c;font-size:13px">Status</label>
            <select id="content-status-create" style="margin:4px 0 12px">
              <option value="draft">Draft</option>
              <option value="review">Review</option>
              <option value="scheduled">Scheduled</option>
              <option value="published">Published</option>
            </select>
          </div>
          <div style="grid-column:1 / -1">
            <label style="color:#8d909c;font-size:13px">Body</label>
            <textarea id="content-body" rows="5" style="margin:4px 0 16px"></textarea>
          </div>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn-secondary" id="content-cancel">Cancel</button>
          <button class="btn-primary" id="content-save">Create Content</button>
        </div>
      </div>
    </div>`;
  document.getElementById('content-cancel').onclick = () => { root.innerHTML = ''; };
  document.getElementById('content-modal-close').onclick = (e) => {
    if (e.target.id === 'content-modal-close') root.innerHTML = '';
  };
  document.getElementById('content-save').onclick = async () => {
    await api('/content', {
      method: 'POST',
      body: JSON.stringify({
        campaign_id: document.getElementById('content-campaign').value || undefined,
        title: document.getElementById('content-title').value,
        content_type: document.getElementById('content-type-create').value,
        status: document.getElementById('content-status-create').value,
        body: document.getElementById('content-body').value,
      }),
    });
    root.innerHTML = '';
    if (onSuccess) onSuccess();
  };
}

/* ─── ANALYTICS ─── */
async function renderAnalytics() {
  renderShell('Analytics', 'Performance metrics across all channels.');
  closeSSE();
  destroyCharts();
  document.getElementById('page-body').innerHTML = '<p style="color:#8d909c">Loading...</p>';
  try {
    const [overview, channels, content] = await Promise.all([
      api('/analytics/overview'), api('/analytics/channels'), api('/content'),
    ]);

    document.getElementById('page-body').innerHTML = `
      <div class="stat-grid">
        ${statCard('Total Views', overview.total_views.toLocaleString(), 'visibility')}
        ${statCard('Total Clicks', overview.total_clicks.toLocaleString(), 'ads_click')}
        ${statCard('Total Shares', overview.total_shares.toLocaleString(), 'share')}
        ${statCard('Conversions', overview.conversions.toLocaleString(), 'conversion_path')}
      </div>
      <div class="glass-card" style="padding:20px;margin-bottom:24px">
        <h3 style="color:#e2e2e8;margin:0 0 16px">Views Over Time</h3>
        <canvas id="line-chart" height="100"></canvas>
      </div>
      <div class="glass-card" style="padding:20px;margin-bottom:24px">
        <h3 style="color:#e2e2e8;margin:0 0 16px">Channel Performance</h3>
        <canvas id="bar-chart" height="80"></canvas>
      </div>
      <div class="glass-card" style="overflow:hidden">
        <div style="padding:16px;border-bottom:1px solid rgba(67,71,81,0.2)"><h3 style="margin:0;color:#e2e2e8">Top Content</h3></div>
        <table>
          <thead><tr><th>Title</th><th>Type</th><th>Views</th><th>Clicks</th><th>Shares</th></tr></thead>
          <tbody>${content.slice(0,5).map((c,i) => `
            <tr>
              <td style="color:#e2e2e8">${c.title}</td>
              <td style="text-transform:capitalize;color:#8d909c">${c.content_type.replace(/_/g,' ')}</td>
              <td>${(500+i*120).toLocaleString()}</td>
              <td>${(45+i*15).toLocaleString()}</td>
              <td>${(8+i*3).toLocaleString()}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;

    const lineCtx = document.getElementById('line-chart').getContext('2d');
    chartInstances.push(new Chart(lineCtx, {
      type: 'line',
      data: {
        labels: (overview.daily_data || []).map(d => d.date.slice(5)),
        datasets: [{ label: 'Views', data: (overview.daily_data || []).map(d => d.views), borderColor: '#6366f1', tension: 0.3, fill: false }],
      },
      options: { responsive: true, plugins: { legend: { labels: { color: '#8d909c' } } }, scales: { x: { ticks: { color: '#8d909c' } }, y: { ticks: { color: '#8d909c' } } } },
    }));

    const chData = [
      { name: 'HubSpot', ...channels.hubspot },
      { name: 'Buffer', ...channels.buffer },
      { name: 'Email', ...channels.email },
      { name: 'Social', ...channels.social },
    ];
    const barCtx = document.getElementById('bar-chart').getContext('2d');
    chartInstances.push(new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: chData.map(c => c.name),
        datasets: [
          { label: 'Views', data: chData.map(c => c.views || 0), backgroundColor: '#6366f1' },
          { label: 'Clicks', data: chData.map(c => c.clicks || 0), backgroundColor: '#8b5cf6' },
        ],
      },
      options: { responsive: true, plugins: { legend: { labels: { color: '#8d909c' } } }, scales: { x: { ticks: { color: '#8d909c' } }, y: { ticks: { color: '#8d909c' } } } },
    }));
  } catch (e) {
    document.getElementById('page-body').innerHTML = `<div class="error-msg">${e.message}</div>`;
  }
}

/* ─── INTEGRATIONS ─── */
const INT_META = {
  hubspot: { color: '#ff7a59', desc: 'CMS, CRM & Email' },
  buffer: { color: '#2d9cdb', desc: 'Social Media Scheduling' },
  google_analytics: { color: '#34a853', desc: 'Traffic & Conversions' },
  openai: { color: '#412991', desc: 'GPT-4o & DALL-E 3' },
};

async function renderIntegrations() {
  renderShell('Integrations', 'Connect your marketing tools.');
  closeSSE();
  document.getElementById('page-body').innerHTML = '<p style="color:#8d909c">Loading...</p>';
  try {
    const items = await api('/integrations');
    document.getElementById('page-body').innerHTML = `<div class="card-grid">${items.map(i => {
      const meta = INT_META[i.key] || { color: '#6366f1', desc: i.description };
      return `<div class="glass-card" style="padding:24px">
        <div style="display:flex;gap:16px;align-items:start">
          <div style="width:48px;height:48px;border-radius:50%;background:${meta.color};display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:20px;flex-shrink:0">${i.name.charAt(0)}</div>
          <div style="flex:1">
            <h3 style="margin:0 0 4px;color:#e2e2e8">${i.name}</h3>
            <p style="margin:0 0 8px;font-size:13px;color:#8d909c">${meta.desc}</p>
            ${badge(i.connected ? 'Connected' : 'Disconnected', i.connected ? '#166534' : '#434751')}
            <p style="font-size:11px;color:#6b7280;margin:8px 0 0">Last synced: ${i.connected ? '2 hours ago' : 'Never'}</p>
          </div>
        </div>
        <button class="${i.connected ? 'btn-danger' : 'btn-primary'}" style="margin-top:16px" data-int-key="${i.key}" data-int-connected="${i.connected}">
          ${i.connected ? 'Disconnect' : 'Connect'}
        </button>
      </div>`;
    }).join('')}</div>`;

    document.querySelectorAll('[data-int-key]').forEach(btn => {
      btn.onclick = async () => {
        const key = btn.dataset.intKey;
        const connected = btn.dataset.intConnected === 'true';
        await api(`/integrations/${key}/${connected ? 'disconnect' : 'connect'}`, { method: 'POST' });
        renderIntegrations();
      };
    });
  } catch (e) {
    document.getElementById('page-body').innerHTML = `<div class="error-msg">${e.message}</div>`;
  }
}

/* ─── SETTINGS ─── */
function renderSettings() {
  renderShell('Settings', 'Brand voice, notifications, and team.');
  closeSSE();
  document.getElementById('page-body').innerHTML = `
    <div class="glass-card" style="padding:24px;margin-bottom:24px;max-width:640px">
      <h3 style="color:#e2e2e8;margin:0 0 16px">Brand Voice</h3>
      <label style="color:#8d909c;font-size:13px">Tone</label>
      <input placeholder="Professional, friendly, authoritative" style="margin:4px 0 12px" />
      <label style="color:#8d909c;font-size:13px">Writing Style</label>
      <input placeholder="Conversational with data-driven insights" style="margin:4px 0 12px" />
      <label style="color:#8d909c;font-size:13px">Target Audience</label>
      <input placeholder="Marketing managers, 25-45" style="margin:4px 0 16px" />
      <button class="btn-primary" id="save-brand">Save</button>
    </div>
    <div class="glass-card" style="padding:24px;margin-bottom:24px;max-width:640px">
      <h3 style="color:#e2e2e8;margin:0 0 16px">Notifications</h3>
      ${toggleRow('Email alerts for completed campaigns', true)}
      ${toggleRow('Slack notifications for agent errors', false)}
      ${toggleRow('Weekly analytics digest', true)}
    </div>
    <div class="glass-card" style="padding:24px;max-width:640px;overflow:hidden">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="color:#e2e2e8;margin:0">Team Members</h3>
        <button class="btn-secondary" disabled title="Coming Soon" style="opacity:0.5;cursor:not-allowed">Invite Member</button>
      </div>
      <table>
        <thead><tr><th>Name</th><th>Role</th></tr></thead>
        <tbody>
          <tr><td style="color:#e2e2e8">Admin User</td><td style="color:#8d909c">Owner</td></tr>
          <tr><td style="color:#e2e2e8">Jane Smith</td><td style="color:#8d909c">Editor</td></tr>
          <tr><td style="color:#e2e2e8">Bob Lee</td><td style="color:#8d909c">Viewer</td></tr>
        </tbody>
      </table>
    </div>`;
  document.getElementById('save-brand').onclick = () => {
    document.getElementById('save-brand').textContent = 'Saved!';
    setTimeout(() => { document.getElementById('save-brand').textContent = 'Save'; }, 2000);
  };
  document.querySelectorAll('.toggle').forEach(btn => {
    btn.onclick = () => btn.classList.toggle('on');
  });
}

function toggleRow(label, on) {
  return `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <span style="color:#c3c6d2;font-size:14px">${label}</span>
    <button class="toggle ${on ? 'on' : ''}" type="button"></button>
  </div>`;
}

/* ─── ROUTER ─── */
const ROUTES = {
  '/': renderDashboard,
  '/calendar': renderCalendar,
  '/agents': renderAgents,
  '/content': renderContent,
  '/analytics': renderAnalytics,
  '/integrations': renderIntegrations,
  '/settings': renderSettings,
};

function render() {
  const path = location.pathname;
  if (path === '/login' || !getToken()) {
    if (path !== '/login' && !getToken()) { navigate('/login'); return; }
    renderLogin();
    return;
  }
  const fn = ROUTES[path] || renderDashboard;
  fn();
}

window.addEventListener('popstate', render);
render();
