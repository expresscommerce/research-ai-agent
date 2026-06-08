/* Execution Logs Page — Clean Professional Look */

async function renderLogs() {
    const sessionId = window._activeSessionId;
    const c = document.getElementById('page-container');
    if (!sessionId) { 
        c.innerHTML = `
            <div class="page-header">
                <div class="page-header-left">
                    <h1 class="page-title">Execution Logs</h1>
                </div>
            </div>
            <div class="page-content">
                <div class="card">
                    <div class="card-body">
                        <div class="empty-state" style="padding:var(--space-12) 0">
                            <h3 class="empty-state-title">No session selected</h3>
                            <p class="empty-state-text">Select a research session to view execution logs.</p>
                        </div>
                    </div>
                </div>
            </div>`; 
        return; 
    }
    
    c.innerHTML = `
        <div class="page-header">
            <div class="page-header-left">
                <h1 class="page-title">Execution Logs</h1>
                <p class="page-subtitle">Detailed execution log for the active session</p>
            </div>
            <div class="page-header-actions">
                <div class="tabs" id="log-filters">
                    <button class="tab active" onclick="filterLogs(null,this)">All</button>
                    <button class="tab" onclick="filterLogs('INFO',this)">Info</button>
                    <button class="tab" onclick="filterLogs('WARN',this)">Warn</button>
                    <button class="tab" onclick="filterLogs('ERROR',this)">Error</button>
                </div>
            </div>
        </div>
        <div class="page-content">
            <div class="card">
                <div class="card-body" style="padding:0" id="logs-container">
                    <div style="display:flex;justify-content:center;padding:var(--space-8)"><div class="spinner"></div></div>
                </div>
            </div>
        </div>`;
    loadLogs(sessionId);
}

async function loadLogs(sessionId, level) {
    try {
        const logs = await api.getLogs(sessionId, level);
        const lc = document.getElementById('logs-container');
        if (!logs.length) { 
            lc.innerHTML = '<div style="text-align:center;padding:var(--space-8);color:var(--text-tertiary)">No logs available</div>'; 
            return; 
        }
        lc.innerHTML = logs.map(l => `
            <div class="log-entry">
                <span class="log-time">${new Date(l.created_at).toLocaleTimeString()}</span>
                <span class="log-level ${l.level}">${l.level}</span>
                <span class="log-agent">${l.agent_type || '—'}</span>
                <span class="log-message">${escHtml(l.message)}</span>
            </div>
        `).join('');
    } catch (err) { 
        showToast('Failed to load logs: ' + err.message, 'error'); 
    }
}

function filterLogs(level, btn) {
    document.querySelectorAll('#log-filters .tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    loadLogs(window._activeSessionId, level);
}
