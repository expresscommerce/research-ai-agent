/* Report Viewer Page — Clean Professional Look */

async function renderReport() {
    const sessionId = window._activeSessionId;
    const c = document.getElementById('page-container');
    if (!sessionId) { 
        c.innerHTML = `
            <div class="page-header">
                <div class="page-header-left">
                    <h1 class="page-title">Report Viewer</h1>
                </div>
            </div>
            <div class="page-content">
                <div class="card">
                    <div class="card-body">
                        <div class="empty-state" style="padding:var(--space-12) 0">
                            <h3 class="empty-state-title">No session selected</h3>
                            <p class="empty-state-text">Select a completed research session to view its generated report.</p>
                        </div>
                    </div>
                </div>
            </div>`; 
        return; 
    }
    
    c.innerHTML = `
        <div class="page-header">
            <div class="page-header-left">
                <h1 class="page-title">Research Report</h1>
                <p class="page-subtitle" id="report-subtitle">Loading...</p>
            </div>
            <div class="page-header-actions">
                <button class="btn btn-primary btn-sm" onclick="downloadPdf('${sessionId}')">Download PDF</button>
            </div>
        </div>
        <div class="page-content">
            <div id="report-area">
                <div style="display:flex;justify-content:center;padding:var(--space-8)"><div class="spinner spinner-lg"></div></div>
            </div>
        </div>`;

    try {
        const report = await api.getReport(sessionId);
        const session = await api.getResearch(sessionId);
        document.getElementById('report-subtitle').textContent = session.title || 'Report';
        const score = (report.confidence_score * 100).toFixed(0);
        const scoreClass = score >= 75 ? 'high' : score >= 50 ? 'medium' : 'low';
        const area = document.getElementById('report-area');
        
        area.innerHTML = `
            <div class="report-container">
                <div class="report-main">
                    <div class="report-header-bar" style="margin-bottom:var(--space-6)">
                        <div class="report-score">
                            <div class="score-ring ${scoreClass}">${score}%</div>
                            <div>
                                <div style="font-weight:var(--weight-semibold)">Confidence Score</div>
                                <div style="font-size:var(--text-xs);color:var(--text-secondary)">Revision #${report.revision_number}</div>
                            </div>
                        </div>
                    </div>
                    <div class="card" style="margin-bottom:var(--space-6)">
                        <div class="card-header"><h3 class="card-title">Executive Summary</h3></div>
                        <div class="card-body"><div class="report-content">${formatMarkdown(report.executive_summary || 'No summary available')}</div></div>
                    </div>
                    <div class="card">
                        <div class="card-header"><h3 class="card-title">Detailed Report</h3></div>
                        <div class="card-body"><div class="report-content">${formatMarkdown(report.detailed_report || 'No detailed report available')}</div></div>
                    </div>
                </div>
                <div class="report-sidebar">
                    <div class="card">
                        <div class="card-header"><h3 class="card-title">Key Insights</h3></div>
                        <div class="card-body">
                            ${(report.key_insights||[]).map(i => `
                                <div class="insight-card">
                                    <div class="insight-text">${escHtml(typeof i === 'object' ? i.insight || JSON.stringify(i) : i)}</div>
                                    ${typeof i === 'object' && i.impact ? `<div class="insight-meta">Impact: ${i.impact}</div>` : ''}
                                </div>
                            `).join('') || '<p class="text-secondary">No key insights documented.</p>'}
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header"><h3 class="card-title">Identified Risks</h3></div>
                        <div class="card-body">
                            ${(report.risks||[]).map(r => `
                                <div class="risk-card">
                                    <div class="risk-text">${escHtml(typeof r === 'object' ? r.risk || JSON.stringify(r) : r)}</div>
                                    ${typeof r === 'object' && r.severity ? `<div class="risk-meta">Severity: ${r.severity}</div>` : ''}
                                </div>
                            `).join('') || '<p class="text-secondary">No risks identified.</p>'}
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header"><h3 class="card-title">Strategic Recommendations</h3></div>
                        <div class="card-body">
                            ${(report.recommendations||[]).map(r => `
                                <div class="rec-card">
                                    <div class="insight-text">${escHtml(typeof r === 'object' ? r.recommendation || JSON.stringify(r) : r)}</div>
                                    ${typeof r === 'object' && r.priority ? `<div class="insight-meta">Priority: ${r.priority}</div>` : ''}
                                </div>
                            `).join('') || '<p class="text-secondary">No recommendations documented.</p>'}
                        </div>
                    </div>
                </div>
            </div>`;
    } catch (err) {
        document.getElementById('report-area').innerHTML = `
            <div class="card">
                <div class="card-body">
                    <div class="empty-state" style="padding:var(--space-12) 0">
                        <h3 class="empty-state-title">Report not ready</h3>
                        <p class="empty-state-text">${err.message}</p>
                    </div>
                </div>
            </div>`;
    }
}

async function downloadPdf(sessionId) {
    try {
        showToast('Downloading PDF...', 'info');
        const token = api.token || '';
        const url = `/api/v1/research/${sessionId}/report/download?token=${token}`;
        
        const a = document.createElement('a'); 
        a.href = url; 
        a.download = 'research_report.pdf';
        document.body.appendChild(a); 
        a.click(); 
        a.remove();
        showToast('PDF downloaded successfully.', 'success');
    } catch (err) { 
        showToast('PDF download failed: ' + err.message, 'error'); 
    }
}

function formatMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^\- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>').replace(/$/, '</p>');
}
