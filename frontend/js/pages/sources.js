/* Sources Explorer Page — Clean Professional List */

async function renderSources() {
    const sessionId = window._activeSessionId;
    const c = document.getElementById('page-container');
    if (!sessionId) { 
        c.innerHTML = `
            <div class="page-header">
                <div class="page-header-left">
                    <h1 class="page-title">Source Explorer</h1>
                </div>
            </div>
            <div class="page-content">
                <div class="card">
                    <div class="card-body">
                        <div class="empty-state" style="padding:var(--space-12) 0">
                            <h3 class="empty-state-title">No session selected</h3>
                            <p class="empty-state-text">Select a research session to explore its reference sources.</p>
                        </div>
                    </div>
                </div>
            </div>`; 
        return; 
    }
    
    c.innerHTML = `
        <div class="page-header">
            <div class="page-header-left">
                <h1 class="page-title">Source Explorer</h1>
                <p class="page-subtitle">References and documentation discovered during research</p>
            </div>
        </div>
        <div class="page-content">
            <div id="sources-container">
                <div style="display:flex;justify-content:center;padding:var(--space-8)"><div class="spinner spinner-lg"></div></div>
            </div>
        </div>`;

    try {
        const sources = await api.getSources(sessionId);
        const sc = document.getElementById('sources-container');
        if (!sources.length) { 
            sc.innerHTML = `
                <div class="card">
                    <div class="card-body">
                        <div class="empty-state" style="padding:var(--space-12) 0">
                            <h3 class="empty-state-title">No sources yet</h3>
                            <p class="empty-state-text">Sources will appear here once the research agents gather reference materials.</p>
                        </div>
                    </div>
                </div>`; 
            return; 
        }
        sc.innerHTML = `<div class="source-grid">${sources.map(s => `
            <div class="card source-card">
                <div class="source-card-header">
                    <div class="source-title">${escHtml(s.title)}</div>
                    <span class="badge badge-blue">${s.source_type.toUpperCase()}</span>
                </div>
                ${s.content_snippet ? `<p class="source-snippet">${escHtml(s.content_snippet)}</p>` : ''}
                <div class="source-footer">
                    ${s.url ? `<a href="${escHtml(s.url)}" target="_blank" style="font-size:var(--text-xs); text-decoration:none; font-weight:var(--weight-semibold)">View Reference</a>` : '<span></span>'}
                    <span style="font-size:var(--text-xs);color:var(--text-tertiary)">Relevance: ${(s.relevance_score*100).toFixed(0)}%</span>
                </div>
            </div>
        `).join('')}</div>`;
    } catch (err) { 
        showToast('Failed to load sources: ' + err.message, 'error'); 
    }
}
