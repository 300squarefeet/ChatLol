'use strict';

function init() {
  loadCurrentSettings();

  document.getElementById('form-settings').addEventListener('submit', function(e) {
    e.preventDefault();
    saveSettings();
  });

  ['claude', 'openai', 'gemini', 'deepseek', 'openrouter', 'ninerouter'].forEach(function(name) {
    document.getElementById('toggle-' + name).addEventListener('click', function() {
      toggleVisibility('field-' + name, this);
    });
  });

  applyTheme(localStorage.getItem('chatlol-theme') === 'white' ? 'white' : 'g100');
  document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
}

/* ── Theme toggle (IBM Carbon: Gray 100 ⇄ White) ─────── */
function applyTheme(theme) {
  const isWhite = theme === 'white';
  if (isWhite) {
    document.documentElement.setAttribute('data-theme', 'white');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  localStorage.setItem('chatlol-theme', isWhite ? 'white' : 'g100');
  const moon = document.querySelector('.icon-theme-dark');
  const sun = document.querySelector('.icon-theme-light');
  if (moon && sun) {
    moon.style.display = isWhite ? 'none' : '';
    sun.style.display = isWhite ? '' : 'none';
  }
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.setAttribute('aria-label', isWhite ? 'Beralih ke tema terang' : 'Beralih ke tema gelap');
}

function toggleTheme() {
  const isWhite = document.documentElement.getAttribute('data-theme') === 'white';
  applyTheme(isWhite ? 'g100' : 'white');
}

async function loadCurrentSettings() {
  try {
    const resp = await fetch('/settings/api');
    if (!resp.ok) return;
    const data = await resp.json();

    const claudeEl = document.getElementById('field-claude');
    const openaiEl = document.getElementById('field-openai');
    const geminiEl = document.getElementById('field-gemini');

    if (data.ANTHROPIC_API_KEY) claudeEl.placeholder = data.ANTHROPIC_API_KEY;
    if (data.OPENAI_API_KEY)    openaiEl.placeholder  = data.OPENAI_API_KEY;
    if (data.GEMINI_API_KEY)    geminiEl.placeholder  = data.GEMINI_API_KEY;
    if (data.DEEPSEEK_API_KEY)   document.getElementById('field-deepseek').placeholder   = data.DEEPSEEK_API_KEY;
    if (data.OPENROUTER_API_KEY) document.getElementById('field-openrouter').placeholder = data.OPENROUTER_API_KEY;
    if (data.NINEROUTER_API_KEY) document.getElementById('field-ninerouter').placeholder = data.NINEROUTER_API_KEY;

    document.getElementById('field-port').value   = data.PORT   || 8000;
    document.getElementById('field-ollama').value = data.OLLAMA_URL || 'http://localhost:11434';
  } catch (_) {
    showToast('Gagal memuat pengaturan saat ini', 'error');
  }
}

async function saveSettings() {
  const btn = document.getElementById('btn-save');
  btn.disabled = true;
  btn.textContent = 'Menyimpan...';

  const body = {
    ANTHROPIC_API_KEY: document.getElementById('field-claude').value,
    OPENAI_API_KEY:    document.getElementById('field-openai').value,
    GEMINI_API_KEY:    document.getElementById('field-gemini').value,
    DEEPSEEK_API_KEY:   document.getElementById('field-deepseek').value,
    OPENROUTER_API_KEY: document.getElementById('field-openrouter').value,
    NINEROUTER_API_KEY: document.getElementById('field-ninerouter').value,
    PORT:              parseInt(document.getElementById('field-port').value, 10) || 8000,
    OLLAMA_URL:        document.getElementById('field-ollama').value || 'http://localhost:11434',
  };

  try {
    const resp = await fetch('/settings/api', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (resp.ok) {
      showToast('Pengaturan tersimpan', 'success');
      // Clear API key fields — user sees new placeholders on next load
      document.getElementById('field-claude').value = '';
      document.getElementById('field-openai').value = '';
      document.getElementById('field-gemini').value = '';
      document.getElementById('field-deepseek').value = '';
      document.getElementById('field-openrouter').value = '';
      document.getElementById('field-ninerouter').value = '';
      loadCurrentSettings();
    } else {
      const data = await resp.json().catch(function() { return {}; });
      showToast(data.detail || 'Gagal menyimpan pengaturan', 'error');
    }
  } catch (_) {
    showToast('Koneksi gagal', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Simpan Pengaturan';
  }
}

function toggleVisibility(fieldId, btn) {
  const input = document.getElementById(fieldId);
  const isHidden = input.type === 'password';
  input.type = isHidden ? 'text' : 'password';
  btn.setAttribute('aria-label',
    (isHidden ? 'Sembunyikan' : 'Tampilkan') + ' ' + fieldId.replace('field-', '') + ' API Key'
  );
}

function showToast(msg, type) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast ' + (type || 'success');
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(function() {
    toast.classList.add('fade-out');
    toast.addEventListener('animationend', function() { toast.remove(); });
  }, 3000);
}

document.addEventListener('DOMContentLoaded', init);
