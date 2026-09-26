/**
 * TradePulse Master Control Panel — Frontend Controller
 * Full CRUD, Real-Time Telemetry Feed & Hardware Lock Actions
 */

let AdminState = {
  activeTab: 'licenses',
  licenses: [],
  telemetry: [],
  stats: {},
  searchTerm: '',
  authToken: localStorage.getItem('tp_admin_token') || null
};

document.addEventListener('DOMContentLoaded', () => {
  checkAuth();
  // Poll telemetry and stats every 3 seconds when active
  setInterval(() => {
    if (AdminState.authToken) {
      loadStats();
      if (AdminState.activeTab === 'telemetry') {
        loadTelemetryData(false);
      }
    }
  }, 3000);
});

function checkAuth() {
  const overlay = document.getElementById('login-overlay');
  if (!AdminState.authToken) {
    if (overlay) overlay.classList.add('active');
  } else {
    if (overlay) overlay.classList.remove('active');
    loadAllData();
  }
}

async function handleAdminLogin(e) {
  if (e) e.preventDefault();
  const user = document.getElementById('admin-user-input')?.value.trim();
  const pass = document.getElementById('admin-pass-input')?.value.trim();

  try {
    const res = await fetch('/api/v1/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      AdminState.authToken = data.token;
      localStorage.setItem('tp_admin_token', data.token);
      document.getElementById('login-overlay')?.classList.remove('active');
      showToast('Master Admin Access Granted', 'success');
      loadAllData();
    } else {
      showToast(data.detail || 'Invalid Administrator Credentials', 'error');
    }
  } catch (err) {
    showToast('Failed to connect to Master Control Server', 'error');
  }
}
window.handleAdminLogin = handleAdminLogin;

function handleAdminLogout() {
  AdminState.authToken = null;
  localStorage.removeItem('tp_admin_token');
  document.getElementById('login-overlay')?.classList.add('active');
  showToast('Logged out of Master Control', 'info');
}
window.handleAdminLogout = handleAdminLogout;

function switchAdminTab(tab) {
  AdminState.activeTab = tab;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));

  const nav = document.getElementById(`nav-${tab}`);
  const pane = document.getElementById(`pane-${tab}`);
  if (nav) nav.classList.add('active');
  if (pane) pane.classList.add('active');

  if (tab === 'licenses') loadLicensesData();
  if (tab === 'telemetry') loadTelemetryData();
}
window.switchAdminTab = switchAdminTab;

async function loadAllData() {
  await loadStats();
  await loadLicensesData();
  await loadTelemetryData(false);
}

async function loadStats() {
  try {
    const res = await fetch('/api/v1/admin/stats');
    if (res.ok) {
      const stats = await res.json();
      AdminState.stats = stats;
      document.getElementById('metric-total-licenses').textContent = stats.total_licenses || 0;
      document.getElementById('metric-active-licenses').textContent = stats.active_licenses || 0;
      document.getElementById('metric-online-clients').textContent = stats.online_clients || 0;
      document.getElementById('metric-scanning-clients').textContent = stats.scanning_clients || 0;
      document.getElementById('badge-total-licenses').textContent = stats.total_licenses || 0;
      document.getElementById('badge-online-clients').textContent = `${stats.online_clients || 0} Online`;
    }
  } catch (e) {
    console.error('Stats load error', e);
  }
}

// ============================================================================
// Licenses Management (Subscriptions & HWID Binding)
// ============================================================================
async function loadLicensesData() {
  try {
    const res = await fetch('/api/v1/admin/licenses');
    if (res.ok) {
      AdminState.licenses = await res.json();
      renderLicensesTable();
    }
  } catch (e) {
    showToast('Failed to load licenses data', 'error');
  }
}
window.loadLicensesData = loadLicensesData;

function filterLicensesTable() {
  AdminState.searchTerm = document.getElementById('license-search-input')?.value.toLowerCase() || '';
  renderLicensesTable();
}
window.filterLicensesTable = filterLicensesTable;

function renderLicensesTable() {
  const tbody = document.getElementById('licenses-tbody');
  if (!tbody) return;

  const term = AdminState.searchTerm;
  const list = (AdminState.licenses || []).filter(l => {
    if (!term) return true;
    return (
      (l.customer_name || '').toLowerCase().includes(term) ||
      (l.license_key || '').toLowerCase().includes(term) ||
      (l.telegram_handle || '').toLowerCase().includes(term) ||
      (l.status || '').toLowerCase().includes(term)
    );
  });

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 24px; color: var(--text-dim);">No client licenses found. Click "+ Issue 1-Year License" to generate one.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(l => {
    const boundHwids = l.bound_hwids || [];
    const isBound = boundHwids.length > 0;
    const hwidDisplay = isBound
      ? `<span class="hwid-pill" title="${boundHwids.join(', ')}">🔒 ${boundHwids[0].substring(0, 10)}... (${boundHwids.length}/${l.max_devices || 1} PC)</span>`
      : '<span style="color: var(--text-dim); font-size: 11px;">🟡 Not Bound (Pending 1st Login)</span>';

    const statusClass = (l.status || 'ACTIVE').toLowerCase();
    const expDate = l.expires_at ? new Date(l.expires_at).toLocaleDateString() : 'N/A';

    return `
      <tr>
        <td>
          <div style="font-weight: 700; color: #fff;">${escapeHtml(l.customer_name)}</div>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 2px;">
            ${l.telegram_handle ? `<span style="color: #38bdf8;">${escapeHtml(l.telegram_handle)}</span> • ` : ''}
            ${l.customer_email ? escapeHtml(l.customer_email) : 'No Email'}
          </div>
        </td>
        <td>
          <div class="key-badge">
            <span>${l.license_key}</span>
            <button class="btn-action" style="padding: 1px 4px; font-size: 10px;" onclick="copyToClipboard('${l.license_key}')" title="Copy License Key">📋</button>
          </div>
        </td>
        <td>
          <div style="font-weight: 600; color: var(--text-main);">${l.plan_name || '1-Year Subscription'}</div>
          <div style="font-size: 11px; color: var(--text-dim);">Expires: <b>${expDate}</b></div>
        </td>
        <td>
          ${hwidDisplay}
        </td>
        <td>
          <span style="font-family: var(--font-mono); font-weight: 700;">${boundHwids.length} / ${l.max_devices || 1} PC</span>
        </td>
        <td>
          <span class="status-badge ${statusClass}">${l.status || 'ACTIVE'}</span>
        </td>
        <td style="text-align: right;">
          <div style="display: inline-flex; gap: 6px;">
            <button class="btn-action" onclick="resetHwid('${l.license_key}')" title="Unbind PC HWID so client can log in on a new machine">
              🔄 Reset HWID
            </button>
            <button class="btn-action" onclick="extendLicensePrompt('${l.license_key}')" title="Extend Subscription by 1 Year">
              ➕ +1 Yr
            </button>
            <button class="btn-action" onclick="toggleLicenseStatus('${l.license_key}')" title="Suspend or Activate">
              ${l.status === 'ACTIVE' ? '⏸️ Suspend' : '▶️ Activate'}
            </button>
            <button class="btn-action" onclick="promptSetDevices('${l.license_key}', ${l.max_devices || 1})" title="Authorize Multi-PC">
              💻 Limit
            </button>
            <button class="btn-action danger" onclick="deleteLicense('${l.license_key}')" title="Permanently Delete License">
              🗑️
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// ============================================================================
// Actions: HWID Reset, License Generation, Status Toggles
// ============================================================================
function openCreateLicenseModal() {
  document.getElementById('create-license-modal')?.classList.add('active');
}
window.openCreateLicenseModal = openCreateLicenseModal;

function closeCreateLicenseModal() {
  document.getElementById('create-license-modal')?.classList.remove('active');
}
window.closeCreateLicenseModal = closeCreateLicenseModal;

async function handleCreateLicense(e) {
  if (e) e.preventDefault();
  const name = document.getElementById('new-cust-name')?.value.trim();
  const email = document.getElementById('new-cust-email')?.value.trim();
  const tg = document.getElementById('new-cust-tg')?.value.trim();
  const duration = parseInt(document.getElementById('new-lic-duration')?.value || '365', 10);
  const devices = parseInt(document.getElementById('new-lic-devices')?.value || '1', 10);
  const notes = document.getElementById('new-lic-notes')?.value.trim();

  try {
    const res = await fetch('/api/v1/admin/licenses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        customer_name: name,
        customer_email: email,
        telegram_handle: tg,
        duration_days: duration,
        max_devices: devices,
        plan_name: duration >= 700 ? '2-Year Subscription' : (duration >= 365 ? '1-Year Subscription' : 'Trial Subscription'),
        notes: notes
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      closeCreateLicenseModal();
      showToast(`Issued License Key: ${data.license.license_key}`, 'success');
      loadAllData();
    }
  } catch (err) {
    showToast('Failed to create license', 'error');
  }
}
window.handleCreateLicense = handleCreateLicense;

async function resetHwid(licenseKey) {
  if (!confirm(`Are you sure you want to reset the Hardware ID binding for ${licenseKey}?\n\nThis will allow the user to bind and activate on a new computer.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/v1/admin/licenses/${licenseKey}/reset-hwid`, { method: 'POST' });
    if (res.ok) {
      showToast(`HWID Reset Successful! Client can now bind a new machine.`, 'success');
      loadAllData();
    }
  } catch (e) {
    showToast('Failed to reset HWID', 'error');
  }
}
window.resetHwid = resetHwid;

async function toggleLicenseStatus(licenseKey) {
  try {
    const res = await fetch(`/api/v1/admin/licenses/${licenseKey}/toggle-status`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      showToast(`License status changed to ${data.status}`, 'info');
      loadAllData();
    }
  } catch (e) {
    showToast('Failed to toggle status', 'error');
  }
}
window.toggleLicenseStatus = toggleLicenseStatus;

async function extendLicensePrompt(licenseKey) {
  try {
    const res = await fetch(`/api/v1/admin/licenses/${licenseKey}/extend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days: 365 })
    });
    if (res.ok) {
      const data = await res.json();
      showToast(`Extended 1-Year! New Expiry: ${new Date(data.expires_at).toLocaleDateString()}`, 'success');
      loadAllData();
    }
  } catch (e) {
    showToast('Failed to extend license', 'error');
  }
}
window.extendLicensePrompt = extendLicensePrompt;

async function promptSetDevices(licenseKey, currentMax) {
  const input = prompt(`Enter maximum authorized systems allowed for ${licenseKey}:`, currentMax);
  if (input === null) return;
  const num = parseInt(input, 10);
  if (isNaN(num) || num < 1) {
    showToast('Invalid device count', 'error');
    return;
  }
  try {
    const res = await fetch(`/api/v1/admin/licenses/${licenseKey}/set-max-devices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ max_devices: num })
    });
    if (res.ok) {
      showToast(`Updated machine allowance to ${num} systems`, 'success');
      loadAllData();
    }
  } catch (e) {
    showToast('Failed to update device limit', 'error');
  }
}
window.promptSetDevices = promptSetDevices;

async function deleteLicense(licenseKey) {
  if (!confirm(`⚠️ Permanently delete license ${licenseKey}? This action cannot be undone.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/v1/admin/licenses/${licenseKey}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('License deleted', 'info');
      loadAllData();
    }
  } catch (e) {
    showToast('Failed to delete license', 'error');
  }
}
window.deleteLicense = deleteLicense;

// ============================================================================
// Live Client Telemetry & Bot Monitor Feed
// ============================================================================
async function loadTelemetryData(showToastAlert = true) {
  try {
    const res = await fetch('/api/v1/admin/telemetry');
    if (res.ok) {
      AdminState.telemetry = await res.json();
      renderTelemetryTable();
      if (showToastAlert) showToast('Refreshed live client telemetry', 'info');
    }
  } catch (e) {
    console.error('Telemetry fetch error', e);
  }
}
window.loadTelemetryData = loadTelemetryData;

function renderTelemetryTable() {
  const tbody = document.getElementById('telemetry-tbody');
  if (!tbody) return;

  const list = AdminState.telemetry || [];
  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 24px; color: var(--text-dim);">No active client systems reporting telemetry yet.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(t => {
    const strategies = t.active_strategies || [];
    const stratBadges = strategies.length > 0
      ? strategies.map(s => `<span class="token-chip" style="font-size: 10px; padding: 1px 6px;">${escapeHtml(s)}</span>`).join(' ')
      : '<span style="color: var(--text-dim); font-size: 11px;">None Enabled</span>';

    const isOnline = isRecent(t.last_seen, 5);
    const onlineIndicator = isOnline
      ? '<span style="color: var(--emerald); font-weight: 700;">🟢 Online</span>'
      : '<span style="color: var(--text-dim);">⚪ Offline</span>';

    const botInfo = t.bot_token_prefix
      ? `<code>${t.bot_token_prefix}...</code> • ID: <code>${t.telegram_chat_id || 'N/A'}</code>`
      : '<span style="color: var(--text-dim); font-size: 11px;">Not Configured</span>';

    const quotexBadge = t.quotex_logged_in
      ? '<span style="color: var(--emerald); font-weight: 700;">Connected</span>'
      : '<span style="color: var(--gold);">Disconnected</span>';

    const scannerBadge = t.scanner_active
      ? '<span class="status-badge active" style="font-size: 9.5px;">⚡ SCANNING</span>'
      : '<span style="color: var(--text-dim); font-size: 11px;">Paused</span>';

    return `
      <tr>
        <td>
          <div style="font-weight: 700; color: #fff;">${escapeHtml(t.customer_name || 'Client User')}</div>
          <div style="font-size: 11px; font-family: var(--font-mono); color: var(--cyan-bright);">${t.license_key}</div>
        </td>
        <td>
          <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(t.hostname || 'PC')} (${escapeHtml(t.os_version || 'Windows')})</div>
          <div style="font-size: 10.5px; font-family: var(--font-mono); color: var(--text-dim);">HWID: ${t.hwid.substring(0, 12)}... • IP: ${t.ip_address || '---'}</div>
        </td>
        <td>
          ${botInfo}
        </td>
        <td>
          <div style="display: flex; flex-wrap: wrap; gap: 4px; max-width: 320px;">
            ${stratBadges}
          </div>
        </td>
        <td>
          <div>Quotex: ${quotexBadge}</div>
          <div style="margin-top: 3px;">Scanner: ${scannerBadge}</div>
        </td>
        <td>
          <div>${onlineIndicator}</div>
          <div style="font-size: 10.5px; color: var(--text-dim); margin-top: 2px;">${formatRelativeTime(t.last_seen)}</div>
        </td>
      </tr>
    `;
  }).join('');
}

// ============================================================================
// Helpers
// ============================================================================
function isRecent(isoStr, minutes = 5) {
  if (!isoStr) return false;
  const d = new Date(isoStr);
  const diff = (Date.now() - d.getTime()) / 1000 / 60;
  return diff <= minutes;
}

function formatRelativeTime(isoStr) {
  if (!isoStr) return 'Never';
  const d = new Date(isoStr);
  const diffSec = Math.round((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return d.toLocaleDateString();
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`Copied license key to clipboard!`, 'info');
  });
}
window.copyToClipboard = copyToClipboard;

function showToast(msg, type = 'info') {
  const container = document.getElementById('admin-toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type === 'success' ? '✅' : (type === 'error' ? '🛑' : 'ℹ️')}</span><span>${escapeHtml(msg)}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}
window.showToast = showToast;

function escapeHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
