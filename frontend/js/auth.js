/* ═══════════════════════════════════════════════════
   Auth — Login / Register handlers
   ═══════════════════════════════════════════════════ */

function showLogin() {
    document.getElementById('auth-login-form').style.display = 'block';
    document.getElementById('auth-register-form').style.display = 'none';
}

function showRegister() {
    document.getElementById('auth-login-form').style.display = 'none';
    document.getElementById('auth-register-form').style.display = 'block';
}

async function handleLogin() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    if (!email || !password) return showToast('Please fill in all fields', 'warning');

    const btn = document.getElementById('login-btn');
    btn.disabled = true; btn.textContent = 'Signing in...';
    try {
        const data = await api.login({ email, password });
        api.setToken(data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        showToast('Welcome back!', 'success');
        initApp();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.disabled = false; btn.textContent = 'Sign In';
    }
}

async function handleRegister() {
    const name = document.getElementById('register-name').value.trim();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    if (!name || !email || !password) return showToast('Please fill in all fields', 'warning');
    if (password.length < 6) return showToast('Password must be at least 6 characters', 'warning');

    const btn = document.getElementById('register-btn');
    btn.disabled = true; btn.textContent = 'Creating account...';
    try {
        const data = await api.register({ name, email, password });
        api.setToken(data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        showToast('Account created!', 'success');
        initApp();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.disabled = false; btn.textContent = 'Create Account';
    }
}

function handleLogout() {
    api.clearToken();
    ws.disconnectAll();
    document.getElementById('app-shell').style.display = 'none';
    document.getElementById('auth-view').style.display = 'flex';
    showLogin();
}
