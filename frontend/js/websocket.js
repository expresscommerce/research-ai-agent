/* ═══════════════════════════════════════════════════
   WebSocket Manager — real-time research updates
   ═══════════════════════════════════════════════════ */

class WSManager {
    constructor() {
        this.connections = {};
        this.listeners = {};
    }

    connect(sessionId) {
        if (this.connections[sessionId]) return;
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${location.host}/ws/research/${sessionId}`);

        ws.onopen = () => console.log(`[WS] Connected to session ${sessionId}`);
        ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                this.emit(sessionId, data);
            } catch (err) { console.warn('[WS] Parse error', err); }
        };
        ws.onclose = () => {
            delete this.connections[sessionId];
            console.log(`[WS] Disconnected from session ${sessionId}`);
        };
        ws.onerror = (err) => console.error('[WS] Error', err);

        this.connections[sessionId] = ws;
    }

    disconnect(sessionId) {
        if (this.connections[sessionId]) {
            this.connections[sessionId].close();
            delete this.connections[sessionId];
        }
        delete this.listeners[sessionId];
    }

    on(sessionId, callback) {
        if (!this.listeners[sessionId]) this.listeners[sessionId] = [];
        this.listeners[sessionId].push(callback);
    }

    emit(sessionId, data) {
        (this.listeners[sessionId] || []).forEach(cb => cb(data));
    }

    disconnectAll() {
        Object.keys(this.connections).forEach(id => this.disconnect(id));
    }
}

const ws = new WSManager();
