/* ── State ─────────────────────────────────────────── */
let username = localStorage.getItem('chatlol_username') || '';
let currentSessionId = null;
let ws = null;
let isStreaming = false;
let pendingFileId = null;
let pendingFileName = null;
let providers = [];

/* ── DOM refs ───────────────────────────────────────── */
const $ = id => document.getElementById(id);
const usernameModal   = $('username-modal');
const usernameInput   = $('username-input');
const usernameForm    = $('username-form');
const usernameDisplay = $('username-display');
const historyList     = $('history-list');
const messages        = $('messages');
const emptyState      = $('empty-state');
const providerSelect  = $('provider-select');
const modelSelect     = $('model-select');
const messageInput    = $('message-input');
const sendBtn         = $('send-btn');
const uploadBtn       = $('upload-btn');
const fileInput       = $('file-input');
const filePreview     = $('file-preview');
const filePreviewName = $('file-preview-name');
const filePreviewRemove = $('file-preview-remove');
const mainEl          = $('main');

/* ── Init ───────────────────────────────────────────── */
async function init() {
  await loadProviders();
  if (!username) {
    usernameModal.classList.remove('hidden');
    usernameInput.focus();
  } else {
    startSession();
  }
}

async function loadProviders() {
  const res = await fetch('/providers');
  providers = await res.json();
  providerSelect.innerHTML = '';
  for (const p of providers) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.label;
    providerSelect.appendChild(opt);
  }
  updateModelSelect();
}

function updateModelSelect() {
  const pid = providerSelect.value;
  const provider = providers.find(p => p.id === pid);
  if (!provider) return;
  modelSelect.innerHTML = '';
  for (const m of provider.models) {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    modelSelect.appendChild(opt);
  }
}

function startSession() {
  usernameModal.classList.add('hidden');
  usernameDisplay.textContent = `@${username}`;
  connectWebSocket();
  loadHistory();
}

/* ── Username modal ─────────────────────────────────── */
usernameForm.addEventListener('submit', e => {
  e.preventDefault();
  const val = usernameInput.value.trim();
  if (!val) return;
  username = val;
  localStorage.setItem('chatlol_username', username);
  startSession();
});

/* ── WebSocket ───────────────────────────────────────── */
function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${encodeURIComponent(username)}`);

  ws.onopen = () => {
    sendBtn.disabled = false;
  };

  ws.onclose = () => {
    sendBtn.disabled = true;
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    // onclose will fire after onerror, handle reconnect there
  };
}

/* ── Send message ────────────────────────────────────── */
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isStreaming) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  isStreaming = true;
  setSendBtnLoading(true);
  setEmptyState(false);

  appendMessage('user', text, { fileName: pendingFileName });

  ws.send(JSON.stringify({
    session_id: currentSessionId,
    provider: providerSelect.value,
    model: modelSelect.value,
    message: text,
    file_id: pendingFileId,
  }));

  clearFilePreview();
  messageInput.value = '';
  autoResizeTextarea();

  const senderLabel = (providerSelect.options[providerSelect.selectedIndex]
      ? providerSelect.options[providerSelect.selectedIndex].textContent : providerSelect.value)
      + (modelSelect.value ? ' · ' + modelSelect.value : '');
  const assistantBubble = appendMessage('assistant', '', { senderLabel: senderLabel });

  const typing = document.createElement('span');
  typing.className = 'typing-indicator';
  typing.setAttribute('aria-label', 'Sedang mengetik');
  typing.innerHTML = '<span></span><span></span><span></span>';
  assistantBubble.appendChild(typing);

  const cursor = document.createElement('span');
  cursor.className = 'cursor-blink';

  let isError = false;
  let firstToken = true;
  let assistantText = '';

  ws.onmessage = ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.type === 'session_id') {
      currentSessionId = msg.session_id;
    } else if (msg.type === 'token') {
      if (firstToken) { typing.remove(); assistantBubble.appendChild(cursor); firstToken = false; }
      assistantText += msg.content;
      assistantBubble.insertBefore(document.createTextNode(msg.content), cursor);
      messages.scrollTop = messages.scrollHeight;
    } else if (msg.type === 'error') {
      isError = true;
      typing.remove(); cursor.remove();
      assistantBubble.textContent = `⚠ ${msg.message}`;
      assistantBubble.style.color = 'var(--danger)';
    } else if (msg.type === 'done') {
      // Server always sends "done" even after "error" — only do success actions if no error
      if (!isError) {
        typing.remove(); cursor.remove();
        // Render the full reply as Markdown (escaped + sanitized inside renderMarkdown)
        assistantBubble.classList.add('rendered');
        assistantBubble.innerHTML = renderMarkdown(assistantText);
        messages.scrollTop = messages.scrollHeight;
        loadHistory();
      }
      isStreaming = false;
      setSendBtnLoading(false);
    }
  };
}

/* ── Markdown rendering (safe: escape-first, no external lib) ─────────
   AI output is untrusted: everything is HTML-escaped before any markup
   is applied, and only http(s) links are allowed. No raw model HTML is
   ever inserted, so this is XSS-safe. */
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function mdInline(s) {
  // Links [text](http...) — text already escaped; URL may contain &amp; from escaping
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (m, t, u) => `<a href="${u.replace(/&amp;/g, '&')}" target="_blank" rel="noopener noreferrer">${t}</a>`);
  // Bold (** or __)
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__(.+?)__/g, '<strong>$1</strong>');
  // Italic (* or _) — avoid matching inside words for _
  s = s.replace(/(?<![*\w])\*(.+?)\*(?![*\w])/g, '<em>$1</em>');
  s = s.replace(/(?<![_\w])_(.+?)_(?![_\w])/g, '<em>$1</em>');
  // Strikethrough
  s = s.replace(/~~(.+?)~~/g, '<del>$1</del>');
  return s;
}

function renderMarkdown(src) {
  if (!src) return '';
  const blocks = [];
  const inlineCode = [];
  let t = src.replace(/\r\n/g, '\n');

  // 1) Extract fenced code blocks BEFORE escaping, then escape their content.
  t = t.replace(/```([^\n`]*)\n([\s\S]*?)```/g, (m, lang, code) => {
    const esc = escapeHtml(code.replace(/\n+$/, ''));
    const lbl = lang.trim() ? escapeHtml(lang.trim()) : 'code';
    blocks.push(
      `<div class="md-code-block"><div class="md-code-head">` +
      `<span class="md-code-lang">${lbl}</span>` +
      `<button class="md-code-copy" type="button" aria-label="Salin kode">Salin</button>` +
      `</div><pre><code>${esc}</code></pre></div>`
    );
    return `\n\u0000${blocks.length - 1}\u0000\n`;
  });

  // 2) Extract inline code BEFORE escaping (so content doesn't get double-escaped).
  t = t.replace(/`([^`\n]+)`/g, (m, c) => {
    inlineCode.push(escapeHtml(c));
    return `\u0001${inlineCode.length - 1}\u0001`;
  });

  // 3) Escape everything else.
  t = escapeHtml(t);

  // 4) Block-level parse.
  const lines = t.split('\n');
  let html = '';
  let listType = null, listItems = [], para = [], bq = [];
  const flushList = () => {
    if (listType) {
      html += `<${listType}>` + listItems.map(li => `<li>${mdInline(li)}</li>`).join('') + `</${listType}>`;
      listType = null; listItems = [];
    }
  };
  const flushPara = () => { if (para.length) { html += `<p>${mdInline(para.join('\n'))}</p>`; para = []; } };
  const flushBq = () => { if (bq.length) { html += `<blockquote>${bq.map(l => mdInline(l)).join('<br>')}</blockquote>`; bq = []; } };
  const flushAll = () => { flushList(); flushPara(); flushBq(); };

  for (const line of lines) {
    const cb = line.match(/^\u0000(\d+)\u0000$/);
    if (cb) { flushAll(); html += blocks[+cb[1]]; continue; }
    if (/^\s*$/.test(line)) { flushAll(); continue; }
    // Headings (escaped # is still #, so this works fine)
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { flushAll(); const lv = h[1].length; html += `<h${lv}>${mdInline(h[2])}</h${lv}>`; continue; }
    // HR: only match raw separator lines (at least 3 of the same char, no other text)
    if (/^\s*[-*_]{3,}\s*$/.test(line) && !/\S.*\S/.test(line.replace(/[-*_\s]/g, ''))) { flushAll(); html += '<hr>'; continue; }
    // Blockquote (escaped > = &gt;)
    const q = line.match(/^\s*&gt;\s?(.*)$/);
    if (q) { flushList(); flushPara(); bq.push(q[1]); continue; }
    // Unordered list
    const ul = line.match(/^\s*[-*+]\s+(.+)$/);
    if (ul) { flushPara(); flushBq(); if (listType && listType !== 'ul') flushList(); listType = 'ul'; listItems.push(ul[1]); continue; }
    // Ordered list
    const ol = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ol) { flushPara(); flushBq(); if (listType && listType !== 'ol') flushList(); listType = 'ol'; listItems.push(ol[1]); continue; }
    flushList(); flushBq();
    para.push(line.trim());
  }
  flushAll();

  // 5) Restore placeholders.
  html = html.replace(/\u0000(\d+)\u0000/g, (m, i) => blocks[+i] || '');
  html = html.replace(/\u0001(\d+)\u0001/g, (m, i) => `<code class="md-inline-code">${inlineCode[+i]}</code>`);
  return html;
}

/* ── UI helpers ─────────────────────────────────────── */
function appendMessage(role, text, opts) {
  opts = opts || {};
  const div = document.createElement('div');
  div.className = `message ${role}`;

  // Meta row: avatar + sender label
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  const avatar = document.createElement('span');
  avatar.className = 'message-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = role === 'user' ? 'U' : 'AI';
  const sender = document.createElement('span');
  sender.className = 'message-sender';
  sender.textContent = role === 'user' ? (username || 'Kamu') : (opts.senderLabel || 'Asisten');
  meta.appendChild(avatar);
  meta.appendChild(sender);
  div.appendChild(meta);

  if (opts.fileName) {
    const badge = document.createElement('div');
    badge.className = 'message-file-badge';
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('width', '12'); icon.setAttribute('height', '12');
    icon.setAttribute('viewBox', '0 0 24 24'); icon.setAttribute('fill', 'none');
    icon.setAttribute('stroke', 'currentColor'); icon.setAttribute('stroke-width', '2');
    icon.setAttribute('aria-hidden', 'true');
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z');
    icon.appendChild(p);
    badge.appendChild(icon);
    const fn = document.createElement('span');
    fn.textContent = ' ' + opts.fileName;
    badge.appendChild(fn);
    div.appendChild(badge);
  }

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  if (text) {
    if (role === 'assistant') {
      bubble.classList.add('rendered');
      bubble.innerHTML = renderMarkdown(text);
    } else {
      bubble.textContent = text;
    }
  }
  div.appendChild(bubble);

  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function setSendBtnLoading(loading) {
  sendBtn.disabled = loading;
  sendBtn.innerHTML = loading
    ? '<div class="spinner"></div>'
    : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';
}

function setEmptyState(show) {
  emptyState.style.display = show ? 'flex' : 'none';
  messages.style.display = show ? 'none' : 'flex';
}

/* ── History ─────────────────────────────────────────── */
async function loadHistory() {
  const res = await fetch(`/history/${encodeURIComponent(username)}`);
  const sessions = await res.json();
  renderHistory(sessions);
}

function renderHistory(sessions) {
  historyList.innerHTML = '';
  if (!sessions.length) return;

  const groups = groupByDate(sessions);
  for (const [label, items] of Object.entries(groups)) {
    const groupLabel = document.createElement('div');
    groupLabel.className = 'history-group-label';
    groupLabel.textContent = label;
    historyList.appendChild(groupLabel);

    for (const s of items) {
      const item = document.createElement('div');
      item.className = 'history-item' + (s.id === currentSessionId ? ' active' : '');
      item.setAttribute('role', 'listitem');
      item.setAttribute('tabindex', '0');

      const title = document.createElement('span');
      title.className = 'history-item-title';
      title.textContent = s.title || 'New Chat';

      const delBtn = document.createElement('button');
      delBtn.className = 'history-item-delete';
      delBtn.setAttribute('aria-label', `Hapus: ${s.title}`);
      delBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>';
      delBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await fetch(`/history/${encodeURIComponent(username)}/${s.id}`, { method: 'DELETE' });
        if (currentSessionId === s.id) { newChat(); }
        loadHistory();
      });

      item.appendChild(title);
      item.appendChild(delBtn);
      item.addEventListener('click', () => openSession(s.id));
      item.addEventListener('keydown', e => { if (e.key === 'Enter') openSession(s.id); });
      historyList.appendChild(item);
    }
  }
}

async function openSession(sessionId) {
  currentSessionId = sessionId;
  messages.innerHTML = '';
  setEmptyState(false);

  const res = await fetch(`/history/${encodeURIComponent(username)}/${sessionId}`);
  const msgs = await res.json();
  for (const m of msgs) {
    appendMessage(m.role, m.content, { fileName: m.file_name });
  }
  loadHistory();
}

function groupByDate(sessions) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const groups = {};
  for (const s of sessions) {
    const d = new Date(s.created_at);
    let label;
    if (d.toDateString() === today.toDateString()) label = 'Hari ini';
    else if (d.toDateString() === yesterday.toDateString()) label = 'Kemarin';
    else label = d.toLocaleDateString('id-ID', { day: 'numeric', month: 'long' });
    groups[label] = groups[label] || [];
    groups[label].push(s);
  }
  return groups;
}

function newChat() {
  currentSessionId = null;
  messages.innerHTML = '';
  setEmptyState(true);
  loadHistory();
}

/* ── File upload ─────────────────────────────────────── */
uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
  fileInput.value = '';
});

filePreviewRemove.addEventListener('click', clearFilePreview);

async function uploadFile(file) {
  const form = new FormData();
  form.append('file', file);
  try {
    const res = await fetch('/upload', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json();
      alert(`Upload gagal: ${err.detail}`);
      return;
    }
    const data = await res.json();
    pendingFileId = data.file_id;
    pendingFileName = data.name;
    filePreviewName.textContent = data.name;
    filePreview.classList.add('visible');
  } catch {
    alert('Gagal mengunggah file. Coba lagi.');
  }
}

function clearFilePreview() {
  pendingFileId = null;
  pendingFileName = null;
  filePreview.classList.remove('visible');
  filePreviewName.textContent = '';
}

/* ── Drag & drop ─────────────────────────────────────── */
mainEl.addEventListener('dragover', e => {
  e.preventDefault();
  mainEl.classList.add('drag-over');
});
mainEl.addEventListener('dragleave', () => mainEl.classList.remove('drag-over'));
mainEl.addEventListener('drop', e => {
  e.preventDefault();
  mainEl.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

/* ── Textarea auto-resize ────────────────────────────── */
function autoResizeTextarea() {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 140) + 'px';
}

messageInput.addEventListener('input', autoResizeTextarea);
messageInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

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
  const btn = $('theme-toggle');
  if (btn) btn.setAttribute('aria-label', isWhite ? 'Beralih ke tema terang' : 'Beralih ke tema gelap');
}

function toggleTheme() {
  const isWhite = document.documentElement.getAttribute('data-theme') === 'white';
  applyTheme(isWhite ? 'g100' : 'white');
}

/* ── Event bindings ──────────────────────────────────── */
sendBtn.addEventListener('click', sendMessage);
providerSelect.addEventListener('change', updateModelSelect);
$('btn-new-chat').addEventListener('click', newChat);
$('theme-toggle').addEventListener('click', toggleTheme);

/* Copy buttons inside rendered code blocks (event delegation) */
messages.addEventListener('click', e => {
  const btn = e.target.closest('.md-code-copy');
  if (!btn) return;
  const codeEl = btn.closest('.md-code-block')?.querySelector('pre code');
  if (!codeEl) return;
  const text = codeEl.textContent;
  const done = () => { btn.textContent = 'Tersalin'; setTimeout(() => { btn.textContent = 'Salin'; }, 1500); };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
});

function fallbackCopy(text, onSuccess) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); onSuccess(); } catch (_) {}
  document.body.removeChild(ta);
}

/* ── Start ───────────────────────────────────────────── */
applyTheme(localStorage.getItem('chatlol-theme') === 'white' ? 'white' : 'g100');
setEmptyState(true);
init();
