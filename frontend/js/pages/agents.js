/* Agent Activity Page — Clean Professional Timeline */

async function renderAgents() {
    const sessionId = window._activeSessionId;
    const container = document.getElementById('page-container');

    if (!sessionId) {
        container.innerHTML = `
            <div class="page-header">
                <div class="page-header-left">
                    <h1 class="page-title">Agent Activity</h1>
                    <p class="page-subtitle">Select a research session to view agent activity</p>
                </div>
            </div>
            <div class="page-content">
                <div class="card">
                    <div class="card-body">
                        <div class="empty-state" style="padding:var(--space-12) 0">
                            <h3 class="empty-state-title">No session selected</h3>
                            <p class="empty-state-text">Start a new research session or select one from the dashboard.</p>
                            <button class="btn btn-primary" onclick="navigate('research')">New Research</button>
                        </div>
                    </div>
                </div>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="page-header">
            <div class="page-header-left">
                <h1 class="page-title" id="agent-session-title">Agent Activity</h1>
                <p class="page-subtitle" id="agent-session-status">Loading...</p>
            </div>
            <div class="page-header-actions">
                <div class="live-indicator" id="live-indicator" style="display:none"><div class="live-dot"></div> Live</div>
                <button class="btn btn-secondary btn-sm" onclick="navigate('report')">View Report</button>
                <button class="btn btn-secondary btn-sm" onclick="navigate('sources')">View Sources</button>
            </div>
        </div>
        <div class="page-content">
            <div class="card">
                <div class="card-header"><h3 class="card-title">Execution Timeline</h3></div>
                <div class="card-body" id="agent-timeline-container">
                    <div style="display:flex;justify-content:center;padding:var(--space-8)"><div class="spinner spinner-lg"></div></div>
                </div>
            </div>
        </div>`;

    loadAgentActivity(sessionId);
    ws.connect(sessionId);
    ws.on(sessionId, handleAgentUpdate);
}

async function loadAgentActivity(sessionId) {
    try {
        const [session, executions] = await Promise.all([
            api.getResearch(sessionId),
            api.getExecutions(sessionId)
        ]);

        document.getElementById('agent-session-title').textContent = session.title || 'Research Session';
        document.getElementById('agent-session-status').textContent = `Status: ${session.status.toUpperCase()} | Iteration: ${session.iteration_count} | ${session.confidence_score ? (session.confidence_score*100).toFixed(0)+'% confidence' : 'Running...'}`;

        const isRunning = !['completed','failed'].includes(session.status);
        document.getElementById('live-indicator').style.display = isRunning ? 'flex' : 'none';

        renderTimeline(executions, session.status);
    } catch (err) { 
        showToast('Failed to load activity: ' + err.message, 'error'); 
    }
}

function renderTimeline(executions, sessionStatus) {
    const container = document.getElementById('agent-timeline-container');
    if (!executions.length) {
        if (['pending','planning'].includes(sessionStatus)) {
            container.innerHTML = `<div style="text-align:center;padding:var(--space-8)"><div class="spinner spinner-lg" style="margin:0 auto var(--space-4)"></div><p class="text-secondary">Agents are initializing workflow...</p></div>`;
        } else {
            container.innerHTML = '<div class="empty-state"><p class="text-secondary">No agent executions recorded</p></div>';
        }
        return;
    }

    container.innerHTML = `<div class="agent-timeline">${executions.map(e => {
        const agentColor = `timeline-dot ${e.agent_type}`;
        const isRunning = e.status === 'running' ? ' running' : '';
        return `
            <div class="timeline-item">
                <div class="${agentColor}${isRunning}"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-agent" style="color:var(--agent-${e.agent_type})">${e.agent_type.toUpperCase()}</span>
                        <div style="display:flex;align-items:center;gap:var(--space-3)">
                            ${getStatusBadge(e.status)}
                            <span class="timeline-time">${e.duration_seconds ? e.duration_seconds.toFixed(1)+'s' : 'Running...'}</span>
                        </div>
                    </div>
                    <div class="timeline-message">${getAgentMessage(e)}</div>
                    <div class="timeline-stats">
                        ${e.tokens_input ? `<span class="timeline-stat">Input: ${e.tokens_input} tokens</span>` : ''}
                        ${e.tokens_output ? `<span class="timeline-stat">Output: ${e.tokens_output} tokens</span>` : ''}
                        ${e.cost_estimate ? `<span class="timeline-stat">Cost: $${e.cost_estimate.toFixed(4)}</span>` : ''}
                        ${e.model_used ? `<span class="timeline-stat">Model: ${e.model_used.split('/').pop()}</span>` : ''}
                    </div>
                </div>
            </div>`;
    }).join('')}</div>`;
}

function getAgentMessage(execution) {
    const output = execution.output_data || {};
    switch (execution.agent_type) {
        case 'planner': return `Created strategy with ${(output.sub_topics||[]).length} sub-topics and ${(output.research_queries||[]).length} queries.`;
        case 'researcher': return `Gathered ${(output.findings||[]).length} findings from ${(output.sources||[]).length} sources.`;
        case 'analyzer': return `Identified ${(output.key_findings||[]).length} key findings, ${(output.trends||[]).length} trends, and ${(output.contradictions||[]).length} contradictions.`;
        case 'summarizer': return `Generated report draft with ${(output.key_insights||[]).length} insights and ${(output.recommendations||[]).length} recommendations.`;
        case 'critic': return `Quality score: ${output.quality_score || '?'}/100 — Verdict: ${output.verdict || 'reviewing'}`;
        default: return execution.status;
    }
}

function handleAgentUpdate(data) {
    if (data.event === 'agent_start' || data.event === 'agent_complete' || data.event === 'completed' || data.event === 'feedback_loop') {
        loadAgentActivity(window._activeSessionId);
    }
    if (data.event === 'completed') {
        showToast('Research execution completed.', 'success');
        document.getElementById('live-indicator').style.display = 'none';
    }
    if (data.event === 'error') {
        showToast('Research execution failed: ' + data.message, 'error');
        document.getElementById('live-indicator').style.display = 'none';
    }
}
