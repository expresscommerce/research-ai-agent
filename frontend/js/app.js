/* ═══════════════════════════════════════════════════
   App — SPA Router + Init
   ═══════════════════════════════════════════════════ */

let currentPage = 'dashboard';

const PAGE_RENDERERS = {
    dashboard: renderDashboard,
    research: renderResearch,
    agents: renderAgents,
    sources: renderSources,
    report: renderReport,
    settings: renderSettings,
    logs: renderLogs,
};

function navigate(page) {
    if (!PAGE_RENDERERS[page]) return;
    currentPage = page;
    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(n => {
        n.classList.toggle('active', n.dataset.page === page);
    });
    // Render page
    PAGE_RENDERERS[page]();
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-message">${escHtml(message)}</span><button class="toast-close" onclick="this.parentElement.remove()">×</button>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function escHtml(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
}

function timeAgo(dateStr) {
    const now = new Date();
    const date = new Date(dateStr);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

function initApp() {
    const token = localStorage.getItem('auth_token');
    const user = JSON.parse(localStorage.getItem('user') || 'null');

    if (!token || !user) {
        document.getElementById('auth-view').style.display = 'flex';
        document.getElementById('app-shell').style.display = 'none';
        return;
    }

    api.setToken(token);
    document.getElementById('auth-view').style.display = 'none';
    document.getElementById('app-shell').style.display = 'flex';

    // Set user info in sidebar
    document.getElementById('user-name').textContent = user.name || 'User';
    document.getElementById('user-email').textContent = user.email || '';
    document.getElementById('user-avatar').textContent = (user.name || 'U')[0].toUpperCase();

    navigate('dashboard');
}

// Initialize on load
document.addEventListener('DOMContentLoaded', initApp);
