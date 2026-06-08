/* Research Workspace Page — ChatGPT chatbot prompt style */

async function renderResearch() {
    const container = document.getElementById('page-container');
    container.innerHTML = `
        <div class="page-content" style="max-width: 760px; margin: 60px auto 0 auto; display: flex; flex-direction: column; gap: var(--space-6);">
            <!-- Title -->
            <div style="text-align: center; margin-bottom: var(--space-4)">
                <h1 class="page-title" style="font-size: 2rem; margin-bottom: var(--space-2)">What do you want to research?</h1>
                <p class="page-subtitle" style="font-size: 1.05rem">Multi-agent orchestrator will plan, gather information, analyze, and generate reports.</p>
            </div>

            <!-- API Key Missing Warning -->
            <div id="key-warning-card" class="card" style="display:none; border-color:var(--error-border); background-color:var(--error-light);">
                <div class="card-body" style="color:var(--error); text-align: center;">
                    <div style="font-weight:var(--weight-semibold); margin-bottom:var(--space-1)">LLM API Key Required</div>
                    Please configure an API key in Settings before launching a research session.
                </div>
            </div>

            <!-- Chatbot Prompt Container -->
            <div class="card" id="research-workspace-card" style="border-radius: var(--radius-lg); box-shadow: var(--shadow-md); border: 1px solid var(--border)">
                <div class="card-body" style="padding: var(--space-5)">
                    
                    <!-- Top Bar: Model Selector Dropdown -->
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-4); border-bottom: 1px solid var(--border-light); padding-bottom: var(--space-3)">
                        <span style="font-size: var(--text-xs); font-weight: var(--weight-semibold); text-transform: uppercase; color: var(--text-tertiary); letter-spacing: 0.05em">Active Intelligence Model</span>
                        <div style="width: 220px">
                            <select class="form-select" id="research-model" style="font-size: var(--text-xs); padding: var(--space-2) var(--space-3)"></select>
                        </div>
                    </div>

                    <!-- Chat Input Field Wrapper -->
                    <div style="position: relative; background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3) var(--space-10) var(--space-3) var(--space-3)">
                        <textarea class="form-input" id="research-query" placeholder="Ask anything to research... (e.g. Current trends in cloud-native database architectures)" style="width: 100%; border: none; background: transparent; box-shadow: none; padding: 0; min-height: 90px; max-height: 300px; resize: none; font-size: var(--text-md); line-height: 1.5; outline: none" oninput="adjustTextareaHeight(this)"></textarea>
                        
                        <!-- Chat Send Action Button inside input box -->
                        <button id="submit-research-btn" onclick="submitResearch()" style="position: absolute; right: var(--space-3); bottom: var(--space-3); width: 34px; height: 34px; border-radius: 50%; border: none; background: var(--accent); color: white; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.2s ease, opacity 0.2s ease">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                        </button>
                    </div>

                </div>
            </div>
        </div>`;
    
    loadResearchConfig();
}

function adjustTextareaHeight(el) {
    el.style.height = 'auto';
    el.style.height = (el.scrollHeight) + 'px';
}

async function loadResearchConfig() {
    try {
        const config = await api.getApiKeys();
        const warningCard = document.getElementById('key-warning-card');
        const workspaceCard = document.getElementById('research-workspace-card');
        const modelSelect = document.getElementById('research-model');
        const submitBtn = document.getElementById('submit-research-btn');
        const queryTextarea = document.getElementById('research-query');

        if (!config.configured) {
            warningCard.style.display = 'block';
            submitBtn.disabled = true;
            queryTextarea.disabled = true;
            modelSelect.disabled = true;
            modelSelect.innerHTML = '<option value="">No Active Provider</option>';
            submitBtn.style.opacity = '0.5';
            submitBtn.style.cursor = 'not-allowed';
            return;
        }

        warningCard.style.display = 'none';
        submitBtn.disabled = false;
        queryTextarea.disabled = false;
        modelSelect.disabled = false;
        submitBtn.style.opacity = '1';
        submitBtn.style.cursor = 'pointer';

        // Populate supported models based on active detected provider
        modelSelect.innerHTML = (config.models || []).map(m => 
            `<option value="${m}">${m.split('/').pop()}</option>`
        ).join('');

    } catch (err) {
        showToast('Failed to load research configuration: ' + err.message, 'error');
    }
}

async function submitResearch() {
    const query = document.getElementById('research-query').value.trim();
    if (query.length < 10) return showToast('Research query must be at least 10 characters', 'warning');

    const model = document.getElementById('research-model').value || null;
    const btn = document.getElementById('submit-research-btn');
    
    btn.disabled = true;
    btn.style.opacity = '0.5';
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" class="spinner-svg" style="animation: spin 1s linear infinite"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="16"></circle></svg>';

    try {
        // Remove quality threshold and iterations selection from UI, balancing it inside code call
        const session = await api.createResearch({ 
            query, 
            model, 
            max_iterations: 3, 
            quality_threshold: 75 
        });
        showToast('Research session initiated.', 'success');
        window._activeSessionId = session.id;
        navigate('agents');
    } catch (err) {
        showToast('Failed to start research: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
    }
}
