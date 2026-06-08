/* Dashboard Page — Clean Professional Look */

async function renderDashboard() {
    const container = document.getElementById('page-container');
    container.innerHTML = `
        <div class="page-header">
            <div class="page-header-left">
                <h1 class="page-title">Dashboard</h1>
                <p class="page-subtitle">Overview of your research activity</p>
            </div>
            <div class="page-header-actions">
                <button class="btn btn-primary" onclick="navigate('research')">
                    New Research
                </button>
            </div>
        </div>
        <div class="page-content">
            <div class="grid grid-4" id="stats-grid">
                <div class="card stat-card">
                    <div class="stat-card-header">
                        <span style="font-size:var(--text-xs); font-weight:var(--weight-bold); letter-spacing:0.05em; color:var(--accent); text-transform:uppercase">Sessions</span>
                    </div>
                    <div class="stat-value">—</div>
                    <div class="stat-label">Total Sessions</div>
                </div>
                <div class="card stat-card">
                    <div class="stat-card-header">
                        <span style="font-size:var(--text-xs); font-weight:var(--weight-bold); letter-spacing:0.05em; color:var(--success); text-transform:uppercase">Completed</span>
                    </div>
                    <div class="stat-value">—</div>
                    <div class="stat-label">Successful Projects</div>
                </div>
                <div class="card stat-card">
                    <div class="stat-card-header">
                        <span style="font-size:var(--text-xs); font-weight:var(--weight-bold); letter-spacing:0.05em; color:var(--warning); text-transform:uppercase">In Progress</span>
                    </div>
                    <div class="stat-value">—</div>
                    <div class="stat-label">Running Executions</div>
                </div>
                <div class="card stat-card">
                    <div class="stat-card-header">
                        <span style="font-size:var(--text-xs); font-weight:var(--weight-bold); letter-spacing:0.05em; color:var(--purple); text-transform:uppercase">Accuracy</span>
                    </div>
                    <div class="stat-value">—</div>
                    <div class="stat-label">Avg Confidence Score</div>
                </div>
            </div>
            <div class="recent-sessions">
                <div class="card">
                    <div class="card-header"><h3 class="card-title">Recent Research Sessions</h3></div>
                    <div id="sessions-list"><div class="card-body"><div style="display:flex;justify-content:center;padding:var(--space-8)"><div class="spinner"></div></div></div></div>
                </div>
            </div>
        </div>`;
    loadDashboardData();
}

async function loadDashboardData() {
    try {
        const data = await api.listResearch(20);
        const sessions = data.sessions || [];
        const completed = sessions.filter(s => s.status === 'completed');
        const running = sessions.filter(s => !['completed','failed','pending'].includes(s.status));
        const avgConf = completed.length ? (completed.reduce((a,s) => a + (s.confidence_score||0), 0) / completed.length * 100).toFixed(0) + '%' : '—';

        const stats = document.querySelectorAll('#stats-grid .stat-value');
        stats[0].textContent = sessions.length;
        stats[1].textContent = completed.length;
        stats[2].textContent = running.length;
        stats[3].textContent = avgConf;

        const list = document.getElementById('sessions-list');
        if (!sessions.length) {
            list.innerHTML = `
                <div class="card-body">
                    <div class="empty-state" style="padding:var(--space-12) 0">
                        <h3 class="empty-state-title">No research sessions yet</h3>
                        <p class="empty-state-text">Start your first AI-powered research session to generate findings.</p>
                        <button class="btn btn-primary" onclick="navigate('research')">Start Research</button>
                    </div>
                </div>`;
            return;
        }
        list.innerHTML = sessions.map(s => `
            <div class="session-row" onclick="viewSession('${s.id}')">
                <div class="session-info">
                    <div class="session-title-text">${escHtml(s.title || 'Untitled Session')}</div>
                    <div class="session-query">${escHtml(s.query)}</div>
                </div>
                <div class="session-meta">
                    ${getStatusBadge(s.status)}
                    ${s.confidence_score ? `<span class="confidence-value" style="color:${s.confidence_score >= 0.75 ? 'var(--success)' : s.confidence_score >= 0.5 ? 'var(--warning)' : 'var(--error)'}">${(s.confidence_score*100).toFixed(0)}%</span>` : ''}
                    <span class="session-time">${timeAgo(s.created_at)}</span>
                </div>
            </div>
        `).join('');
    } catch (err) { 
        showToast('Failed to load dashboard: ' + err.message, 'error'); 
    }
}

function viewSession(id) {
    window._activeSessionId = id;
    navigate('agents');
}

function getStatusBadge(status) {
    const map = {
        pending: 'badge-gray', planning: 'badge-purple', researching: 'badge-blue',
        analyzing: 'badge-blue', summarizing: 'badge-blue', reviewing: 'badge-orange',
        completed: 'badge-green', failed: 'badge-red'
    };
    return `<span class="badge ${map[status] || 'badge-gray'}">${status}</span>`;
}
