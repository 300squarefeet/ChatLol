'use strict';

let _currentPath = '';

function init() {
  const params = new URLSearchParams(location.search);
  _currentPath = params.get('path') || '';

  const savedView = localStorage.getItem('chatlol_fm_view') || 'grid';
  setView(savedView);

  document.getElementById('btn-grid').addEventListener('click', () => setView('grid'));
  document.getElementById('btn-list').addEventListener('click', () => setView('list'));
  document.getElementById('btn-mkdir').addEventListener('click', openMkdirModal);
  document.getElementById('btn-upload').addEventListener('click', () => document.getElementById('file-input').click());
  document.getElementById('file-input').addEventListener('change', function() { uploadFiles(Array.from(this.files)); });
  document.getElementById('mkdir-confirm').addEventListener('click', confirmMkdir);
  document.getElementById('mkdir-cancel').addEventListener('click', closeMkdirModal);
  document.getElementById('mkdir-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') confirmMkdir();
    if (e.key === 'Escape') closeMkdirModal();
  });
  document.getElementById('search-input').addEventListener('input', function() { filterEntries(this.value); });

  applyTheme(localStorage.getItem('chatlol-theme') === 'white' ? 'white' : 'g100');
  document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

  document.addEventListener('dragenter', onDragEnter);
  document.addEventListener('dragleave', onDragLeave);
  document.addEventListener('dragover', function(e) { e.preventDefault(); });
  document.addEventListener('drop', onDrop);

  loadDir(_currentPath);
}

async function loadDir(path) {
  _currentPath = path;
  const qs = path ? '?path=' + encodeURIComponent(path) : '?';
  history.replaceState(null, '', qs);
  renderBreadcrumb(path);
  try {
    const resp = await fetch('/files/api/list?path=' + encodeURIComponent(path));
    if (!resp.ok) { showToast('Gagal memuat direktori', 'error'); return; }
    const data = await resp.json();
    renderEntries(data.entries);
  } catch (_) {
    showToast('Koneksi gagal', 'error');
  }
}

function renderEntries(entries) {
  const grid = document.getElementById('file-grid');
  const empty = document.getElementById('empty-state');
  grid.innerHTML = '';
  if (!entries.length) { empty.hidden = false; return; }
  empty.hidden = true;

  entries.forEach(function(entry) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.dataset.name = entry.name.toLowerCase();
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', (entry.type === 'dir' ? 'Buka folder ' : 'Unduh ') + entry.name);

    const icon = entry.type === 'dir' ? makeFolderIcon() : makeFileIcon(entry.name);
    const nameEl = document.createElement('span');
    nameEl.className = 'file-name';
    nameEl.textContent = entry.name;
    const sizeEl = document.createElement('span');
    sizeEl.className = 'file-size';
    sizeEl.textContent = entry.type === 'dir' ? 'Folder' : formatSize(entry.size);
    const dateEl = document.createElement('span');
    dateEl.className = 'file-date';
    dateEl.textContent = formatDate(entry.modified);

    card.appendChild(icon);
    card.appendChild(nameEl);
    card.appendChild(sizeEl);
    card.appendChild(dateEl);

    if (entry.type === 'dir') {
      card.addEventListener('click', function() {
        loadDir(_currentPath ? _currentPath + '/' + entry.name : entry.name);
      });
    } else {
      card.addEventListener('click', function() {
        const p = _currentPath ? _currentPath + '/' + entry.name : entry.name;
        window.location.href = '/files/download?path=' + encodeURIComponent(p);
      });
    }
    card.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
    });
    grid.appendChild(card);
  });
}

function filterEntries(query) {
  const q = query.toLowerCase().trim();
  document.querySelectorAll('.file-card').forEach(function(card) {
    card.hidden = q ? !card.dataset.name.includes(q) : false;
  });
}

function renderBreadcrumb(path) {
  const nav = document.getElementById('breadcrumb');
  nav.innerHTML = '';
  const parts = path ? path.split('/').filter(Boolean) : [];

  const root = document.createElement('span');
  root.className = 'breadcrumb-item' + (parts.length === 0 ? ' active' : '');
  root.textContent = '/';
  root.setAttribute('role', 'button');
  if (parts.length > 0) {
    root.tabIndex = 0;
    root.addEventListener('click', function() { loadDir(''); });
    root.addEventListener('keydown', function(e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadDir(''); } });
  }
  nav.appendChild(root);

  parts.forEach(function(part, i) {
    const sep = document.createElement('span');
    sep.className = 'breadcrumb-sep';
    sep.textContent = '›';
    nav.appendChild(sep);

    const item = document.createElement('span');
    item.className = 'breadcrumb-item' + (i === parts.length - 1 ? ' active' : '');
    item.textContent = part;
    item.setAttribute('role', 'button');
    if (i < parts.length - 1) {
      const targetPath = parts.slice(0, i + 1).join('/');
      item.tabIndex = 0;
      item.addEventListener('click', function() { loadDir(targetPath); });
      item.addEventListener('keydown', function(e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadDir(targetPath); } });
    }
    nav.appendChild(item);
  });
}

function setView(view) {
  document.getElementById('file-area').className = view === 'list' ? 'view-list' : 'view-grid';
  document.getElementById('btn-grid').classList.toggle('active', view === 'grid');
  document.getElementById('btn-list').classList.toggle('active', view === 'list');
  localStorage.setItem('chatlol_fm_view', view);
}

async function uploadFiles(files) {
  if (!files.length) return;
  const progressEl = document.getElementById('upload-progress');
  progressEl.hidden = false;
  progressEl.innerHTML = '';

  const promises = files.map(function(file) {
    return new Promise(function(resolve) {
      const item = document.createElement('div');
      item.className = 'progress-item';
      const nameSpan = document.createElement('span');
      nameSpan.textContent = file.name;
      const track = document.createElement('div');
      track.className = 'progress-bar-track';
      const fill = document.createElement('div');
      fill.className = 'progress-bar-fill';
      track.appendChild(fill);
      item.appendChild(nameSpan);
      item.appendChild(track);
      progressEl.appendChild(item);

      const xhr = new XMLHttpRequest();
      xhr.upload.addEventListener('progress', function(e) {
        if (e.lengthComputable) fill.style.width = (e.loaded / e.total * 100).toFixed(1) + '%';
      });
      xhr.addEventListener('load', function() { fill.style.width = '100%'; resolve(xhr.status < 300); });
      xhr.addEventListener('error', function() { resolve(false); });

      const fd = new FormData();
      fd.append('file', file);
      xhr.open('POST', '/files/api/upload?path=' + encodeURIComponent(_currentPath));
      xhr.send(fd);
    });
  });

  const results = await Promise.all(promises);
  const ok = results.filter(Boolean).length;
  const fail = results.length - ok;

  setTimeout(function() { progressEl.hidden = true; progressEl.innerHTML = ''; }, 1000);
  document.getElementById('file-input').value = '';
  if (ok)   showToast(ok + ' file berhasil diupload', 'success');
  if (fail) showToast(fail + ' file gagal diupload', 'error');
  loadDir(_currentPath);
}

function openMkdirModal() {
  document.getElementById('mkdir-modal').hidden = false;
  document.getElementById('mkdir-input').value = '';
  document.getElementById('mkdir-input').focus();
}

function closeMkdirModal() {
  document.getElementById('mkdir-modal').hidden = true;
}

async function confirmMkdir() {
  const name = document.getElementById('mkdir-input').value.trim();
  if (!name) return;
  closeMkdirModal();
  try {
    const resp = await fetch('/files/api/mkdir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: _currentPath, name: name }),
    });
    if (resp.ok) {
      showToast('Folder "' + name + '" dibuat', 'success');
      loadDir(_currentPath);
    } else {
      const data = await resp.json();
      showToast(data.detail || 'Gagal membuat folder', 'error');
    }
  } catch (_) {
    showToast('Koneksi gagal', 'error');
  }
}

let _dragDepth = 0;
function onDragEnter(e) { e.preventDefault(); _dragDepth++; if (_dragDepth === 1) document.getElementById('drop-overlay').hidden = false; }
function onDragLeave()   { _dragDepth--; if (_dragDepth === 0) document.getElementById('drop-overlay').hidden = true; }
function onDrop(e) {
  e.preventDefault();
  _dragDepth = 0;
  document.getElementById('drop-overlay').hidden = true;
  const files = Array.from(e.dataTransfer.files);
  if (files.length) uploadFiles(files);
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

function formatSize(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
}

function makeFolderIcon() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'file-icon icon-folder');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.5');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z');
  svg.appendChild(path);
  return svg;
}

const _EXT_CATEGORY = {
  code: ['js','jsx','ts','tsx','py','go','rs','java','c','cpp','h','rb','php','sh','swift','kt','html','css','scss','json','yaml','yml','toml','xml','md','sql'],
  image: ['png','jpg','jpeg','gif','webp','svg','bmp','ico','avif'],
  pdf: ['pdf'],
  doc: ['doc','docx','txt','rtf','odt','pages'],
  sheet: ['xls','xlsx','csv','ods'],
  archive: ['zip','tar','gz','tgz','rar','7z','bz2'],
  audio: ['mp3','wav','flac','ogg','m4a','aac'],
  video: ['mp4','mov','avi','mkv','webm','flv'],
};

function categoryFor(name) {
  const dot = name.lastIndexOf('.');
  if (dot < 1) return 'default';
  const ext = name.slice(dot + 1).toLowerCase();
  for (const cat in _EXT_CATEGORY) {
    if (_EXT_CATEGORY[cat].indexOf(ext) !== -1) return cat;
  }
  return 'default';
}

function _svg(children, extraClass) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'file-icon ' + extraClass);
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.5');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  children.forEach(function(c) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', c.tag);
    for (const k in c.attrs) el.setAttribute(k, c.attrs[k]);
    svg.appendChild(el);
  });
  return svg;
}

// path dasar dokumen (lembar dengan sudut terlipat)
function _docBase() {
  return [
    { tag: 'path', attrs: { d: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' } },
    { tag: 'polyline', attrs: { points: '14 2 14 8 20 8' } },
  ];
}

function makeFileIcon(name) {
  const cat = categoryFor(name);
  const cls = 'icon-' + cat;
  switch (cat) {
    case 'code':
      return _svg([
        { tag: 'polyline', attrs: { points: '16 18 22 12 16 6' } },
        { tag: 'polyline', attrs: { points: '8 6 2 12 8 18' } },
      ], cls);
    case 'image':
      return _svg([
        { tag: 'rect', attrs: { x: '3', y: '3', width: '18', height: '18', rx: '0' } },
        { tag: 'circle', attrs: { cx: '8.5', cy: '8.5', r: '1.5' } },
        { tag: 'polyline', attrs: { points: '21 15 16 10 5 21' } },
      ], cls);
    case 'archive':
      return _svg([
        { tag: 'rect', attrs: { x: '3', y: '3', width: '18', height: '18' } },
        { tag: 'line', attrs: { x1: '12', y1: '3', x2: '12', y2: '21' } },
        { tag: 'line', attrs: { x1: '10', y1: '7', x2: '14', y2: '7' } },
        { tag: 'line', attrs: { x1: '10', y1: '11', x2: '14', y2: '11' } },
      ], cls);
    case 'audio':
      return _svg([
        { tag: 'path', attrs: { d: 'M9 18V5l12-2v13' } },
        { tag: 'circle', attrs: { cx: '6', cy: '18', r: '3' } },
        { tag: 'circle', attrs: { cx: '18', cy: '16', r: '3' } },
      ], cls);
    case 'video':
      return _svg([
        { tag: 'polygon', attrs: { points: '23 7 16 12 23 17 23 7' } },
        { tag: 'rect', attrs: { x: '1', y: '5', width: '15', height: '14', rx: '0' } },
      ], cls);
    case 'pdf':
    case 'doc':
    case 'sheet':
    default:
      // dokumen dengan garis teks; default tanpa garis
      var children = _docBase();
      if (cat === 'pdf' || cat === 'doc' || cat === 'sheet') {
        children.push({ tag: 'line', attrs: { x1: '8', y1: '13', x2: '16', y2: '13' } });
        children.push({ tag: 'line', attrs: { x1: '8', y1: '17', x2: '13', y2: '17' } });
      }
      return _svg(children, 'icon-' + cat);
  }
}

document.addEventListener('DOMContentLoaded', init);
