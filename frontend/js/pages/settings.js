/* Settings Page — Single API Key Management */

async function renderSettings() {
    const c = document.getElementById('page-container');
    c.innerHTML = `
        <div class="page-header">
            <div class="page-header-left">
                <h1 class="page-title">Settings</h1>
                <p class="page-subtitle">Configure your LLM provider API key</p>
            </div>
        </div>
        <div class="page-content">
            <div class="settings-grid">
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">LLM API Key Configuration</h3>
                    </div>
                    <div class="card-body">
                        <p class="text-secondary" style="margin-bottom:var(--space-4)">
                            Enter your LLM provider API key below. The platform automatically detects the provider (OpenAI, Anthropic, Gemini, DeepInfra, OpenRouter, Groq) based on the key format and encrypts it at rest.
                        </p>
                        
                        <div class="form-group">
                            <label class="form-label" for="settings-api-key">API Key</label>
                            <input class="form-input" type="password" id="settings-api-key" placeholder="Enter API key (starts with sk-, AIzaSy, gsk_, etc.)">
                        </div>

                        <div id="active-key-info" style="display:none; margin-bottom:var(--space-5); padding:var(--space-4); background:var(--bg-secondary); border:1px solid var(--border); border-radius:var(--radius-md)">
                            <div style="font-weight:var(--weight-semibold); margin-bottom:2px">Active Key Configured</div>
                            <div style="font-size:var(--text-sm); color:var(--text-secondary); margin-bottom:var(--space-3)" id="key-info-detail"></div>
                            
                            <div style="font-weight:var(--weight-semibold); font-size:var(--text-xs); text-transform:uppercase; color:var(--text-tertiary); letter-spacing:0.05em; margin-bottom:var(--space-2)">Supported Models</div>
                            <div id="supported-models-list" style="display:flex; flex-wrap:wrap; gap:var(--space-2)"></div>
                        </div>

                        <div style="display:flex; gap:var(--space-3)">
                            <button class="btn btn-primary" onclick="saveApiKey()">Save Key</button>
                            <button class="btn btn-secondary" onclick="testActiveKey()">Test Connection</button>
                            <button class="btn btn-ghost" id="remove-key-btn" onclick="removeApiKey()" style="display:none">Remove Key</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    loadSettingsData();
}

async function loadSettingsData() {
    try {
        const config = await api.getApiKeys();
        const infoDiv = document.getElementById('active-key-info');
        const detailSpan = document.getElementById('key-info-detail');
        const modelsDiv = document.getElementById('supported-models-list');
        const removeBtn = document.getElementById('remove-key-btn');
        const keyInput = document.getElementById('settings-api-key');

        if (config.configured) {
            infoDiv.style.display = 'block';
            removeBtn.style.display = 'inline-flex';
            detailSpan.textContent = `Provider: ${config.provider.toUpperCase()} | Key: ${config.masked_key}`;
            keyInput.value = ''; // Clear input as it's saved
            
            modelsDiv.innerHTML = (config.models || []).map(m => 
                `<span class="badge badge-blue">${m.split('/').pop()}</span>`
            ).join('');
        } else {
            infoDiv.style.display = 'none';
            removeBtn.style.display = 'none';
            detailSpan.textContent = '';
            modelsDiv.innerHTML = '';
        }
    } catch (err) {
        showToast('Failed to load configuration: ' + err.message, 'error');
    }
}

async function saveApiKey() {
    const key = document.getElementById('settings-api-key').value.trim();
    if (!key) return showToast('Please enter an API key', 'warning');
    
    try {
        showToast('Saving and detecting provider...', 'info');
        await api.updateApiKeys({ api_key: key });
        showToast('API key successfully saved and verified!', 'success');
        renderSettings();
    } catch (err) {
        showToast('Failed to save API key: ' + err.message, 'error');
    }
}

async function testActiveKey() {
    const inputKey = document.getElementById('settings-api-key').value.trim();
    
    try {
        showToast('Testing connection...', 'info');
        let result;
        if (inputKey) {
            result = await api.testApiKey({ api_key: inputKey });
        } else {
            // Test the already configured key by fetching settings first or sending placeholder
            // Wait, testApiKey endpoint takes api_key. We can prompt them to input a key or test if one exists.
            const config = await api.getApiKeys();
            if (!config.configured) {
                return showToast('No key configured to test. Please enter a key first.', 'warning');
            }
            // To test existing key, they can type it in or we can pass a test request. Let's ask them to enter it or test via backend.
            // Since backend decrypts it, we could add a test-stored-key endpoint, or just suggest typing the key in.
            return showToast('Please enter the API key in the field to test the connection.', 'warning');
        }
        
        if (result.success) {
            showToast(`Connection successful! Provider detected: ${result.provider.toUpperCase()}`, 'success');
        } else {
            showToast(`Connection failed: ${result.message}`, 'error');
        }
    } catch (err) {
        showToast('Test failed: ' + err.message, 'error');
    }
}

async function removeApiKey() {
    if (!confirm('Are you sure you want to remove your API key?')) return;
    try {
        await api.updateApiKeys({ api_key: '' });
        showToast('API key successfully removed', 'success');
        renderSettings();
    } catch (err) {
        showToast('Failed to remove API key: ' + err.message, 'error');
    }
}
