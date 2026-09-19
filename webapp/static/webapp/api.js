// Shared helpers used by every page. Plain fetch() against the DRF API - no build step needed.
const API = '/api';

function getAccessToken() { return localStorage.getItem('access'); }
function getRefreshToken() { return localStorage.getItem('refresh'); }

function saveTokens(data) {
  localStorage.setItem('access', data.access);
  if (data.refresh) localStorage.setItem('refresh', data.refresh);
}

function logout() {
  localStorage.removeItem('access');
  localStorage.removeItem('refresh');
  window.location.href = '/';
}

// Wraps fetch with the JWT header and a single silent refresh-and-retry on 401.
async function apiFetch(path, options = {}) {
  options.headers = options.headers || {};
  const token = getAccessToken();
  if (token) options.headers['Authorization'] = `Bearer ${token}`;

  let res = await fetch(`${API}${path}`, options);
  if (res.status === 401 && getRefreshToken()) {
    const refreshRes = await fetch(`${API}/accounts/login/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: getRefreshToken() }),
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      saveTokens(data);
      options.headers['Authorization'] = `Bearer ${getAccessToken()}`;
      res = await fetch(`${API}${path}`, options);
    } else {
      logout();
    }
  }
  return res;
}

// Populates the top-nav with the current user + shows Logout button. Redirects
// to "/" if not authenticated (used to guard the dashboard page).
async function requireAuth() {
  if (!getAccessToken()) {
    window.location.href = '/';
    return null;
  }
  const res = await apiFetch('/accounts/me/');
  if (!res.ok) {
    logout();
    return null;
  }
  const me = await res.json();
  document.getElementById('nav-user').textContent = `${me.username} (${me.role})`;
  document.getElementById('nav-logout').classList.remove('d-none');
  return me;
}

function statusBadge(status) {
  const cls = status === 'VERIFIED' ? 'badge-verified' : status === 'PENDING' ? 'badge-pending' : 'badge-unverified';
  return `<span class="badge ${cls}">${status}</span>`;
}
