/* ═══════════════════════════════════════════════════
   API Client — fetch wrapper with auth
   ═══════════════════════════════════════════════════ */

const API_BASE = '/api/v1';

class ApiClient {
    constructor() {
        this.token = localStorage.getItem('auth_token');
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('auth_token', token);
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user');
    }

    async request(path, options = {}) {
        const url = `${API_BASE}${path}`;
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            this.clearToken();
            window.location.reload();
            throw new Error('Session expired');
        }
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        if (response.status === 204) return null;

        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/pdf')) {
            return response.blob();
        }
        return response.json();
    }

    get(path) { return this.request(path); }
    post(path, data) { return this.request(path, { method: 'POST', body: JSON.stringify(data) }); }
    put(path, data) { return this.request(path, { method: 'PUT', body: JSON.stringify(data) }); }
    delete(path) { return this.request(path, { method: 'DELETE' }); }

    // Auth
    register(data) { return this.post('/auth/register', data); }
    login(data) { return this.post('/auth/login', data); }
    getMe() { return this.get('/auth/me'); }

    // Research
    createResearch(data) { return this.post('/research', data); }
    listResearch(limit = 50) { return this.get(`/research?limit=${limit}`); }
    getResearch(id) { return this.get(`/research/${id}`); }
    deleteResearch(id) { return this.delete(`/research/${id}`); }

    // Agents
    getExecutions(sessionId) { return this.get(`/research/${sessionId}/agents`); }

    // Reports
    getReport(sessionId) { return this.get(`/research/${sessionId}/report`); }
    getSources(sessionId) { return this.get(`/research/${sessionId}/sources`); }
    async downloadPdf(sessionId) {
        const url = `${API_BASE}/research/${sessionId}/report/download`;
        const headers = {};
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
        const resp = await fetch(url, { headers });
        if (!resp.ok) throw new Error('Download failed');
        return resp.blob();
    }

    // Settings
    getApiKeys() { return this.get('/settings/api-keys'); }
    updateApiKeys(data) { return this.put('/settings/api-keys', data); }
    testApiKey(data) { return this.post('/settings/api-keys/test', data); }
    getModels() { return this.get('/settings/models'); }

    // Logs
    getLogs(sessionId, level) { return this.get(`/research/${sessionId}/logs${level ? '?level=' + level : ''}`); }
}

const api = new ApiClient();
