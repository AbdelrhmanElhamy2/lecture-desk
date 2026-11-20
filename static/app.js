/* ==========================================================================
   Lecture Desk — Modular Frontend Application
   Clean state management, XSS-safe DOM rendering, zero dead legacy code.
   ========================================================================== */

(() => {
  'use strict';

  // --- Constants ---
  const SUPPORTED_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.webm', '.wma'];
  const SUPPORTED_NOTES_EXTENSIONS = ['.pdf', '.txt', '.md'];

  const MODE_LABELS = {
    detailed: 'Detailed notes',
    revision: 'Quick revision',
    exam: 'Exam focus',
    verbatim_explained: "Doctor's words & simple",
  };

  const DISCIPLINE_PRESETS = {
    all: [
      'Signals & Linear Systems',
      'Thermodynamics & Heat Transfer',
      'Operating Systems & Concurrency',
      'Structural Analysis & Mechanics',
      'Power Electronics & Converters',
      'Bioinstrumentation & Biosensors',
      'Fluid Mechanics & Aerodynamics',
      'Chemical Reaction Kinetics',
      'Control Systems Engineering',
    ],
    ee: [
      'Circuit Analysis & KVL/KCL',
      'Signals & Linear Systems',
      'Power Electronics & Converters',
      'Analog CMOS & Op-Amps',
      'Electromagnetic Fields & Waves',
      'Digital Signal Processing (DSP)',
    ],
    me: [
      'Thermodynamics & Heat Transfer',
      'Fluid Mechanics & Aerodynamics',
      'Mechanics of Materials (Stress/Strain)',
      'Machine Design & Kinematics',
      'Engineering Dynamics & Vibrations',
    ],
    cs: [
      'Operating Systems & Concurrency',
      'Algorithms & Data Structures',
      'Computer Architecture & Organization',
      'Database Management Systems',
      'Computer Networks & Protocols',
    ],
    ce: [
      'Structural Analysis & Mechanics',
      'Reinforced Concrete & Steel Design',
      'Geotechnical & Soil Mechanics',
      'Fluid Hydraulics & Hydrology',
    ],
    chem: [
      'Chemical Reaction Kinetics & Reactor Design',
      'Mass Transfer & Separation Processes',
      'Chemical Engineering Thermodynamics',
      'Materials Science & Crystallography',
    ],
    bme: [
      'Bioinstrumentation & Biosensors',
      'Biomedical Signal Processing (ECG/EMG)',
      'Biomechanics & Biomaterials',
      'Medical Imaging Systems (MRI/CT/US)',
    ],
    sys: [
      'Control Systems Engineering',
      'Robotics & Kinematic Modeling',
      'Operations Research & Optimization',
    ],
  };

  // --- State ---
  let hasApiKey = false;
  let isGenerating = false;
  let activeJobId = null;
  let pollInterval = null;
  let lastWasDemo = false;

  let recordingsSources = [];
  let notesSources = [];

  let activeDisciplineFilter = 'all';
  let currentFolderSearchData = null;
  let isAddNoteDrawerOpen = false;

  let historyCache = [];
  let historyModeFilter = 'all';
  let currentResultHistoryId = null;
  let currentTranscriptRaw = '';
  let allAnswersExpanded = false;

  let recallQuestions = [];
  let recallMissed = [];
  let recallIndex = 0;
  let recallScore = 0;
  let recallAnswerRevealed = false;

  let successToastTimeout = null;
  let confirmResolver = null;

  // --- Utilities ---
  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatFileSize(bytes) {
    if (!bytes || bytes <= 0) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let val = bytes;
    while (val >= 1024 && i < units.length - 1) {
      val /= 1024;
      i++;
    }
    return `${val.toFixed(1)} ${units[i]}`;
  }

  // Lightweight safe math formatter for web reader (converts common LaTeX tokens to crisp Unicode + sub/sup)
  function formatInlineMathHtml(rawText) {
    let text = escapeHtml(rawText ?? '');
    if (!text) return '';

    text = text.replace(/\$\$/g, '$');

    const greekAndSymbols = [
      [/\\partial(?![a-zA-Z])/g, '&part;'],
      [/\\nabla(?![a-zA-Z])/g, '&nabla;'],
      [/\\sum(?![a-zA-Z])/g, '&Sigma;'],
      [/\\prod(?![a-zA-Z])/g, '&Pi;'],
      [/\\int(?![a-zA-Z])/g, '&int;'],
      [/\\infty(?![a-zA-Z])/g, '&infin;'],
      [/\\times(?![a-zA-Z])/g, '&times;'],
      [/\\cdot(?![a-zA-Z])/g, '&middot;'],
      [/\\pm(?![a-zA-Z])/g, '&plusmn;'],
      [/\\approx(?![a-zA-Z])/g, '&asymp;'],
      [/\\leq?(?![a-zA-Z])/g, '&le;'],
      [/\\geq?(?![a-zA-Z])/g, '&ge;'],
      [/\\neq?(?![a-zA-Z])/g, '&ne;'],
      [/\\rightarrow(?![a-zA-Z])/g, '&rarr;'],
      [/\\to(?![a-zA-Z])/g, '&rarr;'],
      [/\\perp(?![a-zA-Z])/g, '&perp;'],
      [/\\parallel(?![a-zA-Z])/g, '||'],
      [/\\degree|\\circ(?![a-zA-Z])/g, '&deg;'],
      [/\\alpha(?![a-zA-Z])/g, '&alpha;'],
      [/\\beta(?![a-zA-Z])/g, '&beta;'],
      [/\\gamma(?![a-zA-Z])/g, '&gamma;'],
      [/\\Delta(?![a-zA-Z])/g, '&Delta;'],
      [/\\delta(?![a-zA-Z])/g, '&delta;'],
      [/\\epsilon|\\varepsilon(?![a-zA-Z])/g, '&epsilon;'],
      [/\\zeta(?![a-zA-Z])/g, '&zeta;'],
      [/\\eta(?![a-zA-Z])/g, '&eta;'],
      [/\\theta(?![a-zA-Z])/g, '&theta;'],
      [/\\lambda(?![a-zA-Z])/g, '&lambda;'],
      [/\\mu(?![a-zA-Z])/g, '&mu;'],
      [/\\pi(?![a-zA-Z])/g, '&pi;'],
      [/\\rho(?![a-zA-Z])/g, '&rho;'],
      [/\\sigma(?![a-zA-Z])/g, '&sigma;'],
      [/\\tau(?![a-zA-Z])/g, '&tau;'],
      [/\\phi(?![a-zA-Z])/g, '&phi;'],
      [/\\Phi(?![a-zA-Z])/g, '&Phi;'],
      [/\\omega(?![a-zA-Z])/g, '&omega;'],
      [/\\Omega|\\ohm(?![a-zA-Z])/g, '&Omega;'],
      [/\\(sin|cos|tan|exp|ln|log)(?![a-zA-Z])/g, '$1'],
      [/\\left|\\right/g, ''],
    ];

    for (const [pat, rep] of greekAndSymbols) {
      text = text.replace(pat, rep);
    }

    text = text.replace(/\\text\{([^{}]+)\}/g, '$1');
    text = text.replace(/\\mathrm\{([^{}]+)\}/g, '$1');
    text = text.replace(/\\mathbf\{([^{}]+)\}/g, '<strong>$1</strong>');

    for (let i = 0; i < 3; i++) {
      text = text.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '($1 / $2)');
    }
    text = text.replace(/\\sqrt\{([^{}]+)\}/g, '&radic;($1)');

    // Subscripts & superscripts inside math expressions or explicit braced forms
    text = text.replace(/_\{([^{}]+)\}/g, '<sub>$1</sub>');
    text = text.replace(/\^\{([^{}]+)\}/g, '<sup>$1</sup>');
    text = text.replace(/\$([^$]+)\$/g, (_, expr) => {
      let clean = expr
        .replace(/_([a-zA-Z0-9])/g, '<sub>$1</sub>')
        .replace(/\^([\+\-]?[a-zA-Z0-9])/g, '<sup>$1</sup>');
      return clean;
    });

    return text;
  }

  // --- Theme Management (Warm Paper Light Default) ---
  function applyTheme(theme) {
    const isDark = theme === 'dark';
    document.documentElement.classList.toggle('dark', isDark);
    try {
      localStorage.setItem('lecturedesk_theme', theme);
    } catch (e) {}

    const sun = $('themeIconSun');
    const moon = $('themeIconMoon');
    const txt = $('themeToggleText');
    if (sun && moon && txt) {
      sun.classList.toggle('hidden', !isDark);
      moon.classList.toggle('hidden', isDark);
      txt.textContent = isDark ? 'Light' : 'Dark';
    }
  }

  function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    applyTheme(isDark ? 'light' : 'dark');
  }

  // --- Workspace View Switching ---
  function switchWorkspaceView(viewName) {
    const views = {
      create: $('viewCreate'),
      library: $('viewLibrary'),
      reader: $('resultsSection'),
    };
    const navs = {
      create: $('navCreate'),
      library: $('navLibrary'),
      reader: $('navReader'),
    };

    Object.entries(views).forEach(([key, el]) => {
      if (el) el.classList.toggle('hidden', key !== viewName);
    });
    Object.entries(navs).forEach(([key, btn]) => {
      if (btn) btn.classList.toggle('active', key === viewName);
    });

    if (viewName === 'library') {
      loadHistory();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // --- Notifications ---
  function showSuccessToast(msg, title = 'Done') {
    hideErrorBox();
    const box = $('successBox');
    if (!box) return;
    $('successTitleText').textContent = title;
    $('successMessage').textContent = msg;
    box.classList.remove('hidden');
    if (successToastTimeout) clearTimeout(successToastTimeout);
    successToastTimeout = setTimeout(hideSuccessToast, 4500);
  }

  function hideSuccessToast() {
    const box = $('successBox');
    if (box) box.classList.add('hidden');
    if (successToastTimeout) {
      clearTimeout(successToastTimeout);
      successToastTimeout = null;
    }
  }

  function showError(msg, title = 'Could not complete request') {
    hideSuccessToast();
    const box = $('errorBox');
    if (!box) return;
    $('errorTitleText').textContent = title;
    let displayMsg = msg || 'An unexpected error occurred.';
    if (typeof displayMsg === 'string' && (displayMsg.includes('503') || displayMsg.includes('UNAVAILABLE'))) {
      displayMsg = 'The transcription service is temporarily busy (503). Wait 15–30 seconds and click Retry, or switch to the fallback engine in Settings.';
    }
    $('errorMessage').textContent = displayMsg;
    box.classList.remove('hidden');
  }

  function hideErrorBox() {
    const box = $('errorBox');
    if (box) box.classList.add('hidden');
  }

  // --- In-App Confirmation Modal ---
  function askConfirm(title, body, okLabel = 'Confirm', isDanger = true) {
    return new Promise((resolve) => {
      confirmResolver = resolve;
      $('confirmModalTitle').textContent = title;
      $('confirmModalBody').textContent = body;
      const okBtn = $('confirmModalOkBtn');
      okBtn.textContent = okLabel;
      okBtn.className = isDanger ? 'btn btn-danger' : 'btn btn-primary';
      $('confirmModal').classList.remove('hidden');
      okBtn.focus();
    });
  }

  function resolveConfirmModal(accepted) {
    $('confirmModal').classList.add('hidden');
    if (confirmResolver) {
      const fn = confirmResolver;
      confirmResolver = null;
      fn(Boolean(accepted));
    }
  }

  // --- Settings Modal (API Key & Processing Engine) ---
  async function checkKeyStatus() {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      hasApiKey = Boolean(data.has_key);
      const dot = $('keyIndicator');
      const txt = $('keyText');
      if (dot) {
        dot.className = `status-dot ${hasApiKey ? 'ok' : 'warn'}`;
      }
      if (txt) {
        txt.textContent = hasApiKey ? 'Settings' : 'Add API Key';
      }
      if (data.model) {
        const modelSel = $('modelSelect');
        if (modelSel && Array.from(modelSel.options).some((o) => o.value === data.model)) {
          modelSel.value = data.model;
        }
      }
    } catch (err) {
      console.error('Config check failed:', err);
    }
  }

  function openSettingsModal() {
    $('keyModal').classList.remove('hidden');
    const inp = $('modalKeyInput');
    if (inp) {
      inp.value = '';
      inp.type = 'password';
      $('toggleKeyVisBtn').textContent = 'Show';
      inp.focus();
    }
  }

  function closeSettingsModal() {
    $('keyModal').classList.add('hidden');
  }

  function toggleKeyVisibility() {
    const inp = $('modalKeyInput');
    const btn = $('toggleKeyVisBtn');
    if (!inp || !btn) return;
    const isHidden = inp.type === 'password';
    inp.type = isHidden ? 'text' : 'password';
    btn.textContent = isHidden ? 'Hide' : 'Show';
  }

  async function saveApiKey() {
    const inp = $('modalKeyInput');
    const key = (inp?.value || '').trim();
    if (!key) {
      closeSettingsModal();
      return;
    }
    const formData = new FormData();
    formData.append('key', key);
    try {
      const res = await fetch('/api/set_key', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.success) {
        inp.value = '';
        closeSettingsModal();
        await checkKeyStatus();
        showSuccessToast('API key saved locally.', 'Settings updated');
      } else {
        showError(data.detail || data.message || 'Could not save API key.');
      }
    } catch (e) {
      showError('Could not save API key: ' + (e.message || e));
    }
  }

  // --- Diagram Lightbox ---
  function openLightbox(src, title, caption) {
    $('lightboxImg').src = src;
    $('lightboxImg').alt = title || 'Diagram';
    $('lightboxTitle').textContent = title || 'Diagram';
    $('lightboxCaption').textContent = caption || '';
    $('lightboxModal').classList.remove('hidden');
  }

  function closeLightbox() {
    $('lightboxModal').classList.add('hidden');
  }

  // --- Step 1: Unified Materials Intake ---
  function triggerUnifiedFilePick() {
    if (isGenerating) return;
    $('unifiedFileInput')?.click();
  }

  function triggerAudioFilePick() {
    if (isGenerating) return;
    $('audioFileInput')?.click();
  }

  function triggerNotesFilePick() {
    if (isGenerating) return;
    $('notesFileInput')?.click();
  }

  function handleUnifiedFileInput(event) {
    if (isGenerating) return;
    const files = Array.from(event.target.files || []);
    if (files.length) routeMixedFiles(files);
    event.target.value = '';
  }

  function handleComputerFileInput(event, role) {
    if (isGenerating) return;
    const files = Array.from(event.target.files || []);
    if (files.length) addComputerFiles(files, role);
    event.target.value = '';
  }

  function handleUnifiedDragOver(event) {
    if (isGenerating) return;
    event.preventDefault();
    $('unifiedDropzone')?.classList.add('drag-over');
  }

  function handleUnifiedDragLeave() {
    $('unifiedDropzone')?.classList.remove('drag-over');
  }

  function handleUnifiedDrop(event) {
    if (isGenerating) return;
    event.preventDefault();
    handleUnifiedDragLeave();
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length) routeMixedFiles(files);
  }

  function routeMixedFiles(files) {
    const audioBatch = [];
    const notesBatch = [];
    const rejected = [];

    for (const file of files) {
      const name = file.name || 'unnamed';
      const dotIdx = name.lastIndexOf('.');
      const ext = dotIdx >= 0 ? name.slice(dotIdx).toLowerCase() : '';
      if (SUPPORTED_AUDIO_EXTENSIONS.includes(ext)) {
        audioBatch.push(file);
      } else if (SUPPORTED_NOTES_EXTENSIONS.includes(ext)) {
        notesBatch.push(file);
      } else {
        rejected.push(name);
      }
    }

    if (audioBatch.length) addComputerFiles(audioBatch, 'audio');
    if (notesBatch.length) addComputerFiles(notesBatch, 'notes');
    if (rejected.length) {
      showError(
        `Unsupported file(s): ${rejected.join(', ')}. Supported audio: ${SUPPORTED_AUDIO_EXTENSIONS.join(', ')}; notes: ${SUPPORTED_NOTES_EXTENSIONS.join(', ')}.`
      );
    }
  }

  function addComputerFiles(files, role) {
    if (isGenerating || !files || !files.length) return;
    const validExts = role === 'audio' ? SUPPORTED_AUDIO_EXTENSIONS : SUPPORTED_NOTES_EXTENSIONS;
    let added = 0;

    for (const file of files) {
      const name = file.name || 'unnamed';
      const dotIdx = name.lastIndexOf('.');
      const ext = dotIdx >= 0 ? name.slice(dotIdx).toLowerCase() : '';
      if (!validExts.includes(ext)) {
        showError(`Unsupported ${role === 'audio' ? 'audio' : 'notes'} format '${ext || 'unknown'}' in "${name}". Supported: ${validExts.join(', ')}.`);
        continue;
      }

      const item = {
        id: 'u_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8),
        kind: 'upload',
        role,
        name,
        size: file.size || 0,
        status: 'ready',
        file,
        link: null,
        local_path: null,
        start_slide: '',
        end_slide: '',
      };

      if (role === 'audio') recordingsSources.push(item);
      else notesSources.push(item);
      added++;
    }

    if (added > 0) renderSourcesUI();
  }

  function toggleLinkDrawer(forceOpen) {
    if (isGenerating) return;
    const drawer = $('linkInputDrawer');
    if (!drawer) return;
    const shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : drawer.classList.contains('hidden');
    drawer.classList.toggle('hidden', !shouldOpen);
    if (shouldOpen) {
      $('courseFolderPanel')?.classList.add('hidden');
      $('sharedLinkInput')?.focus();
    }
  }

  function addSharedLinkItem() {
    if (isGenerating) return;
    const role = $('linkRoleSelect')?.value || 'audio';
    const inp = $('sharedLinkInput');
    const val = (inp?.value || '').trim();
    if (!val) return;

    const urls = val
      .split(/[\r\n,]+/)
      .map((s) => s.trim())
      .filter((s) => s.startsWith('http://') || s.startsWith('https://'));

    if (!urls.length) {
      showError('Enter at least one valid URL starting with http:// or https://.');
      return;
    }

    const validExts = role === 'audio' ? SUPPORTED_AUDIO_EXTENSIONS : SUPPORTED_NOTES_EXTENSIONS;
    let added = 0;

    for (const url of urls) {
      let inferredName = role === 'audio'
        ? `Audio Link ${recordingsSources.length + 1}`
        : `Slides Link ${notesSources.length + 1}`;
      try {
        const fn = new URL(url).pathname.split('/').filter(Boolean).pop();
        if (fn && fn.includes('.')) {
          const ext = '.' + fn.split('.').pop().toLowerCase();
          if (['.exe', '.bat', '.sh', '.bin', '.dmg', '.apk'].includes(ext)) {
            showError(`Unsupported file format '${ext}' in link.`);
            continue;
          }
          if (role === 'audio' && ['.png', '.jpg', '.pdf', '.docx'].includes(ext)) {
            showError(`Unsupported audio extension '${ext}' in link. Use: ${validExts.join(', ')}.`);
            continue;
          }
          if (role === 'notes' && ['.mp3', '.wav', '.m4a', '.mp4'].includes(ext)) {
            showError(`Unsupported notes extension '${ext}' in link. Use: ${validExts.join(', ')}.`);
            continue;
          }
          inferredName = decodeURIComponent(fn);
        }
      } catch (e) {}

      const item = {
        id: 'l_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8),
        kind: 'link',
        role,
        name: inferredName,
        size: 0,
        status: 'ready',
        file: null,
        link: url,
        local_path: null,
        start_slide: '',
        end_slide: '',
      };

      if (role === 'audio') recordingsSources.push(item);
      else notesSources.push(item);
      added++;
    }

    if (inp) inp.value = '';
    toggleLinkDrawer(false);
    if (added > 0) renderSourcesUI();
  }

  function clearAllSources() {
    if (isGenerating) return;
    recordingsSources = [];
    notesSources = [];
    renderSourcesUI();
  }

  function moveSourceItem(role, index, direction) {
    if (isGenerating) return;
    const list = role === 'audio' ? recordingsSources : notesSources;
    const targetIdx = index + direction;
    if (targetIdx < 0 || targetIdx >= list.length) return;
    [list[index], list[targetIdx]] = [list[targetIdx], list[index]];
    renderSourcesUI();
  }

  function removeSourceItem(role, index) {
    if (isGenerating) return;
    const list = role === 'audio' ? recordingsSources : notesSources;
    if (index >= 0 && index < list.length) {
      list.splice(index, 1);
      renderSourcesUI();
    }
  }

  function renderSourcesUI() {
    renderSourceList('audio', recordingsSources, $('recordingsList'), $('recordingsEmptyPrompt'), $('recordingsCountBadge'));
    renderSourceList('notes', notesSources, $('notesList'), $('notesEmptyPrompt'), $('notesCountBadge'));
    updateTotalSize();
    checkDuplicates();
    updateReadinessState();
  }

  function renderSourceList(role, items, container, emptyEl, countEl) {
    if (countEl) countEl.textContent = String(items.length);
    if (!container) return;
    container.replaceChildren();

    if (!items.length) {
      emptyEl?.classList.remove('hidden');
      return;
    }
    emptyEl?.classList.add('hidden');

    items.forEach((item, idx) => {
      const row = document.createElement('div');
      row.className = 'source-item';

      const left = document.createElement('div');
      left.className = 'source-item-left';

      const orderWrap = document.createElement('div');
      orderWrap.className = 'order-controls';

      const upBtn = document.createElement('button');
      upBtn.type = 'button';
      upBtn.className = 'order-btn';
      upBtn.textContent = '▲';
      upBtn.title = 'Move up';
      upBtn.disabled = isGenerating || idx === 0;
      upBtn.onclick = () => moveSourceItem(role, idx, -1);

      const downBtn = document.createElement('button');
      downBtn.type = 'button';
      downBtn.className = 'order-btn';
      downBtn.textContent = '▼';
      downBtn.title = 'Move down';
      downBtn.disabled = isGenerating || idx === items.length - 1;
      downBtn.onclick = () => moveSourceItem(role, idx, 1);

      orderWrap.append(upBtn, downBtn);

      const idxEl = document.createElement('span');
      idxEl.className = 'source-index';
      idxEl.textContent = `#${idx + 1}`;

      const kindBadge = document.createElement('span');
      kindBadge.className = item.kind === 'upload' ? 'badge badge-accent' : 'badge';
      kindBadge.textContent = item.kind === 'upload' ? 'Local' : item.kind === 'link' ? 'Link' : 'Folder';

      const nameEl = document.createElement('span');
      nameEl.className = 'source-name';
      nameEl.textContent = item.name;
      nameEl.title = item.name;

      left.append(orderWrap, idxEl, kindBadge, nameEl);

      const right = document.createElement('div');
      right.className = 'source-item-right';

      if (role === 'notes') {
        const rangeBox = document.createElement('div');
        rangeBox.className = 'slide-range-box';

        const lbl = document.createElement('span');
        lbl.textContent = 'Slides';

        const startInp = document.createElement('input');
        startInp.type = 'number';
        startInp.min = '1';
        startInp.placeholder = 'From';
        startInp.value = item.start_slide || '';
        startInp.disabled = isGenerating;
        startInp.className = 'slide-range-input';
        startInp.onchange = () => { notesSources[idx].start_slide = startInp.value; };

        const dash = document.createElement('span');
        dash.textContent = '–';

        const endInp = document.createElement('input');
        endInp.type = 'number';
        endInp.min = '1';
        endInp.placeholder = 'To';
        endInp.value = item.end_slide || '';
        endInp.disabled = isGenerating;
        endInp.className = 'slide-range-input';
        endInp.onchange = () => { notesSources[idx].end_slide = endInp.value; };

        rangeBox.append(lbl, startInp, dash, endInp);
        right.appendChild(rangeBox);
      }

      if (item.size > 0) {
        const sizeEl = document.createElement('span');
        sizeEl.className = 'badge badge-mono';
        sizeEl.textContent = formatFileSize(item.size);
        right.appendChild(sizeEl);
      }

      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'btn btn-ghost btn-icon';
      delBtn.title = 'Remove item';
      delBtn.disabled = isGenerating;
      delBtn.innerHTML = '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>';
      delBtn.onclick = () => removeSourceItem(role, idx);
      right.appendChild(delBtn);

      row.append(left, right);
      container.appendChild(row);
    });
  }

  function updateTotalSize() {
    let total = 0;
    recordingsSources.forEach((s) => { if (s.size) total += s.size; });
    notesSources.forEach((s) => { if (s.size) total += s.size; });
    const badge = $('totalSizeBadge');
    if (badge) badge.textContent = total > 0 ? formatFileSize(total) : '0 MB';
    const clearBtn = $('btnClearSources');
    if (clearBtn) {
      clearBtn.classList.toggle('hidden', recordingsSources.length === 0 && notesSources.length === 0);
    }
  }

  function checkDuplicates() {
    const banner = $('duplicateWarningBanner');
    const txt = $('duplicateWarningText');
    if (!banner) return;
    const seen = new Set();
    const dupes = new Set();
    for (const item of [...recordingsSources, ...notesSources]) {
      const key = `${item.name.toLowerCase()}::${item.size || 0}`;
      if (seen.has(key)) dupes.add(item.name);
      else seen.add(key);
    }
    if (dupes.size > 0) {
      if (txt) txt.textContent = `Duplicate file(s) detected: ${Array.from(dupes).join(', ')}. Sequential order will be preserved.`;
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }
  }

  function updateReadinessState() {
    const hint = $('readinessHint');
    if (!hint) return;
    const r = recordingsSources.length;
    const n = notesSources.length;
    if (r === 0) {
      hint.textContent = 'Add at least one recording to generate a guide.';
    } else {
      const recStr = `${r} recording${r === 1 ? '' : 's'}`;
      const noteStr = n > 0 ? `, ${n} slide deck${n === 1 ? '' : 's'}` : ' (audio-only)';
      hint.textContent = `Ready to process: ${recStr}${noteStr}.`;
    }
  }

  // --- Course Folder Panel ---
  function toggleCourseFolderPanel() {
    if (isGenerating) return;
    const panel = $('courseFolderPanel');
    if (!panel) return;
    const opening = panel.classList.contains('hidden');
    panel.classList.toggle('hidden', !opening);
    if (opening) {
      $('linkInputDrawer')?.classList.add('hidden');
      $('folderSessionQueryInput')?.focus();
    }
  }

  function closeCourseFolderPanel() {
    $('courseFolderPanel')?.classList.add('hidden');
  }

  async function loadDetectedCourses() {
    try {
      const res = await fetch('/api/detected_courses');
      const data = await res.json();
      const box = $('detectedCoursesBox');
      const chips = $('detectedCoursesChips');
      if (!box || !chips) return;

      if (data.success && Array.isArray(data.courses) && data.courses.length > 0) {
        const lbl = $('detectedCoursesHeaderLabel');
        if (lbl) lbl.textContent = data.semester_name ? `Detected local courses (${data.semester_name})` : 'Detected local courses';
        chips.replaceChildren();
        data.courses.forEach((c) => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'chip';
          btn.textContent = c.name;
          btn.onclick = () => selectCourseFolder(c.path, c.name);
          chips.appendChild(btn);
        });
        box.classList.remove('hidden');
      } else {
        box.classList.add('hidden');
      }
    } catch (err) {
      console.warn('Could not load detected local courses:', err);
    }
  }

  function selectCourseFolder(folderPath, courseName) {
    if (isGenerating) return;
    if ($('folderUrlInput')) $('folderUrlInput').value = folderPath;
    if ($('courseInput')) {
      $('courseInput').value = courseName;
      onOptionalChanged();
    }
    const qInp = $('folderSessionQueryInput');
    if (qInp && !qInp.value.trim()) qInp.value = 'Lecture 1';
    searchCourseFolder();
  }

  function setSessionQueryAndSearch(query) {
    if (isGenerating) return;
    const qInp = $('folderSessionQueryInput');
    if (qInp) {
      qInp.value = query;
      searchCourseFolder();
    }
  }

  async function searchCourseFolder() {
    if (isGenerating) return;
    const folderUrl = ($('folderUrlInput')?.value || '').trim();
    const sessionQuery = ($('folderSessionQueryInput')?.value || '').trim() || 'Lecture 1';
    const resultBox = $('folderSearchResultsBox');
    const btnText = $('searchFolderBtnText');

    if (!folderUrl) {
      showError('Enter a course folder path or public Google Drive folder link first.');
      $('folderUrlInput')?.focus();
      return;
    }

    resultBox.className = 'folder-results';
    resultBox.replaceChildren();
    const loadingRow = document.createElement('div');
    loadingRow.style.cssText = 'display:flex;align-items:center;gap:8px;font-size:13px;color:var(--ink-secondary);';
    const sp = document.createElement('div');
    sp.className = 'spinner';
    const txt = document.createElement('span');
    txt.textContent = `Scanning folder for "${sessionQuery}"...`;
    loadingRow.append(sp, txt);
    resultBox.appendChild(loadingRow);

    if (btnText) btnText.textContent = 'Scanning...';

    try {
      const formData = new FormData();
      formData.append('folder_url', folderUrl);
      formData.append('query', sessionQuery);
      const res = await fetch('/api/search_course_folder', { method: 'POST', body: formData });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Could not scan course folder.');
      }
      const data = await res.json();
      currentFolderSearchData = data;
      isAddNoteDrawerOpen = false;
      if ($('courseInput') && !$('courseInput').value.trim() && data.course_hint) {
        $('courseInput').value = data.course_hint;
        onOptionalChanged();
      }
      (data.records || []).forEach((r) => { if (r.selected === undefined) r.selected = true; });
      (data.notes || []).forEach((n) => { if (n.selected === undefined) n.selected = true; });
      renderFolderMaterialsUI();
    } catch (err) {
      resultBox.className = 'folder-results err';
      resultBox.replaceChildren();
      const p = document.createElement('p');
      p.style.cssText = 'margin:0;color:var(--danger-ink);font-size:13px;';
      p.textContent = `Folder scan error: ${err.message || err}`;
      resultBox.appendChild(p);
    } finally {
      if (btnText) btnText.textContent = 'Find materials';
    }
  }

  function renderFolderMaterialsUI() {
    const data = currentFolderSearchData;
    const box = $('folderSearchResultsBox');
    if (!box || !data) return;

    const recs = data.records || [];
    const notes = data.notes || [];
    const allCourseNotes = data.all_course_notes || [];

    const selRecs = recs.filter((r) => r.selected !== false).length;
    const selNotes = notes.filter((n) => n.selected !== false).length;

    const statusTone = data.status === 'found_both'
      ? 'ok'
      : data.status === 'not_found'
        ? 'err'
        : 'warn';

    box.className = `folder-results ${statusTone}`;
    box.replaceChildren();

    const header = document.createElement('div');
    header.className = 'stack-sm';
    const msgEl = document.createElement('strong');
    msgEl.style.fontSize = '13.5px';
    msgEl.textContent = data.message || 'Scan complete';
    header.appendChild(msgEl);

    if (data.is_section_query) {
      const taNote = document.createElement('p');
      taNote.className = 'step-desc';
      taNote.textContent = 'Teaching Assistant (AT) Section detected: all course slides and sheets are listed so you can pick the decks covered.';
      header.appendChild(taNote);
    }
    box.appendChild(header);

    if (recs.length || notes.length || allCourseNotes.length) {
      const grid = document.createElement('div');
      grid.className = 'folder-grid';

      // Recordings column
      const recCol = document.createElement('div');
      recCol.className = 'folder-col';
      const recHead = document.createElement('div');
      recHead.className = 'folder-col-head';
      const recLbl = document.createElement('span');
      recLbl.textContent = `Recordings (${selRecs}/${recs.length})`;
      const recSeg = document.createElement('div');
      recSeg.className = 'seg-mini';
      const recAll = document.createElement('button');
      recAll.type = 'button';
      recAll.textContent = 'All';
      if (recs.length > 0 && selRecs === recs.length) recAll.classList.add('active');
      recAll.onclick = () => { recs.forEach((r) => { r.selected = true; }); renderFolderMaterialsUI(); };
      const recNone = document.createElement('button');
      recNone.type = 'button';
      recNone.textContent = 'None';
      if (recs.length > 0 && selRecs === 0) recNone.classList.add('active');
      recNone.onclick = () => { recs.forEach((r) => { r.selected = false; }); renderFolderMaterialsUI(); };
      recSeg.append(recAll, recNone);
      recHead.append(recLbl, recSeg);
      recCol.appendChild(recHead);

      const recList = document.createElement('div');
      recList.className = 'folder-check-list';
      if (!recs.length) {
        const empty = document.createElement('p');
        empty.className = 'step-desc';
        empty.textContent = 'No recording matched this session.';
        recList.appendChild(empty);
      } else {
        recs.forEach((r, idx) => {
          const checked = r.selected !== false;
          const lbl = document.createElement('label');
          lbl.className = `folder-check-item ${checked ? 'checked' : 'unchecked'}`;
          const left = document.createElement('div');
          left.style.cssText = 'display:flex;align-items:center;gap:8px;min-width:0;';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.checked = checked;
          cb.onchange = () => { recs[idx].selected = cb.checked; renderFolderMaterialsUI(); };
          const nm = document.createElement('span');
          nm.className = 'source-name';
          nm.textContent = r.name;
          nm.title = r.name;
          left.append(cb, nm);
          lbl.appendChild(left);
          if (r.size) {
            const sz = document.createElement('span');
            sz.className = 'badge badge-mono';
            sz.textContent = formatFileSize(r.size);
            lbl.appendChild(sz);
          }
          recList.appendChild(lbl);
        });
      }
      recCol.appendChild(recList);

      // Notes column
      const noteCol = document.createElement('div');
      noteCol.className = 'folder-col';
      const noteHead = document.createElement('div');
      noteHead.className = 'folder-col-head';
      const noteLbl = document.createElement('span');
      noteLbl.textContent = `Slides & Notes (${selNotes}/${notes.length})`;
      const noteSeg = document.createElement('div');
      noteSeg.className = 'seg-mini';
      const noteAll = document.createElement('button');
      noteAll.type = 'button';
      noteAll.textContent = 'All';
      if (notes.length > 0 && selNotes === notes.length) noteAll.classList.add('active');
      noteAll.onclick = () => { notes.forEach((n) => { n.selected = true; }); renderFolderMaterialsUI(); };
      const noteNone = document.createElement('button');
      noteNone.type = 'button';
      noteNone.textContent = 'None';
      if (notes.length > 0 && selNotes === 0) noteNone.classList.add('active');
      noteNone.onclick = () => { notes.forEach((n) => { n.selected = false; }); renderFolderMaterialsUI(); };
      noteSeg.append(noteAll, noteNone);
      noteHead.append(noteLbl, noteSeg);
      noteCol.appendChild(noteHead);

      const noteList = document.createElement('div');
      noteList.className = 'folder-check-list';
      if (!notes.length) {
        const empty = document.createElement('p');
        empty.className = 'step-desc';
        empty.textContent = 'No slides matched initially.';
        noteList.appendChild(empty);
      } else {
        notes.forEach((n, idx) => {
          const checked = n.selected !== false;
          const lbl = document.createElement('label');
          lbl.className = `folder-check-item ${checked ? 'checked' : 'unchecked'}`;
          const left = document.createElement('div');
          left.style.cssText = 'display:flex;align-items:center;gap:8px;min-width:0;';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.checked = checked;
          cb.onchange = () => { notes[idx].selected = cb.checked; renderFolderMaterialsUI(); };
          const nm = document.createElement('span');
          nm.className = 'source-name';
          nm.textContent = n.name;
          nm.title = n.name;
          left.append(cb, nm);
          lbl.appendChild(left);
          const tag = document.createElement('span');
          tag.className = 'badge';
          tag.textContent = n.category === 'sheet' ? 'Sheet' : 'Slides';
          lbl.appendChild(tag);
          noteList.appendChild(lbl);
        });
      }
      noteCol.appendChild(noteList);

      // Extra / continued notes drawer
      const extraWrap = document.createElement('div');
      extraWrap.style.marginTop = '8px';
      const toggleExtraBtn = document.createElement('button');
      toggleExtraBtn.type = 'button';
      toggleExtraBtn.className = 'btn btn-sm';
      toggleExtraBtn.style.width = '100%';
      toggleExtraBtn.textContent = isAddNoteDrawerOpen ? 'Hide extra slides' : 'Add another slide deck';
      toggleExtraBtn.onclick = () => {
        isAddNoteDrawerOpen = !isAddNoteDrawerOpen;
        renderFolderMaterialsUI();
      };
      extraWrap.appendChild(toggleExtraBtn);

      if (isAddNoteDrawerOpen) {
        const drawer = document.createElement('div');
        drawer.className = 'stack-sm';
        drawer.style.cssText = 'margin-top:8px;padding-top:8px;border-top:1px solid var(--border-subtle);';

        const existingNames = new Set(notes.map((n) => n.name));
        const available = allCourseNotes.filter((an) => !existingNames.has(an.name));
        if (available.length) {
          available.forEach((an) => {
            const r = document.createElement('div');
            r.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;';
            const nm = document.createElement('span');
            nm.className = 'source-name';
            nm.textContent = an.name;
            const addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.className = 'btn btn-sm';
            addBtn.textContent = 'Add';
            addBtn.onclick = () => {
              notesSources.push({
                id: 'f_extra_' + Date.now(),
                kind: 'folder',
                role: 'notes',
                name: an.name,
                size: an.size || 0,
                status: 'ready',
                file: null,
                link: an.url || null,
                local_path: an.local_path || null,
                start_slide: '',
                end_slide: '',
              });
              closeCourseFolderPanel();
              renderSourcesUI();
              showSuccessToast(`Added "${an.name}" to Slides & Notes.`);
            };
            r.append(nm, addBtn);
            drawer.appendChild(r);
          });
        }

        const localLbl = document.createElement('label');
        localLbl.className = 'btn btn-sm';
        localLbl.textContent = 'Browse PDF / TXT / MD from computer';
        const fileInp = document.createElement('input');
        fileInp.type = 'file';
        fileInp.accept = '.pdf,.txt,.md';
        fileInp.className = 'hidden';
        fileInp.onchange = (ev) => {
          const f = ev.target.files?.[0];
          if (f) {
            addComputerFiles([f], 'notes');
            closeCourseFolderPanel();
          }
        };
        localLbl.appendChild(fileInp);
        drawer.appendChild(localLbl);
        extraWrap.appendChild(drawer);
      }

      noteCol.appendChild(extraWrap);
      grid.append(recCol, noteCol);
      box.appendChild(grid);
    }

    // Confirm add bar
    const footer = document.createElement('div');
    footer.className = 'toolbar-row';
    footer.style.cssText = 'margin-top:12px;padding-top:12px;border-top:1px solid var(--border-subtle);';
    const summary = document.createElement('span');
    summary.className = 'step-desc';
    summary.textContent = `${selRecs} recording(s) and ${selNotes} slide deck(s) selected.`;
    const addSelBtn = document.createElement('button');
    addSelBtn.type = 'button';
    addSelBtn.className = 'btn btn-primary btn-sm';
    addSelBtn.disabled = selRecs + selNotes === 0;
    addSelBtn.textContent = 'Add selected to materials';
    addSelBtn.onclick = addSelectedFolderItemsToSources;
    footer.append(summary, addSelBtn);
    box.appendChild(footer);

    // Other detected sessions
    if (Array.isArray(data.available_sessions) && data.available_sessions.length > 0) {
      const sessWrap = document.createElement('div');
      sessWrap.style.cssText = 'margin-top:10px;padding-top:10px;border-top:1px solid var(--border-subtle);';
      const lbl = document.createElement('span');
      lbl.className = 'field-label';
      lbl.textContent = 'Other sessions in this folder';
      const chipWrap = document.createElement('div');
      chipWrap.className = 'chip-list';
      data.available_sessions.forEach((s) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'chip';
        b.textContent = s;
        b.onclick = () => setSessionQueryAndSearch(s);
        chipWrap.appendChild(b);
      });
      sessWrap.append(lbl, chipWrap);
      box.appendChild(sessWrap);
    }
  }

  function addSelectedFolderItemsToSources() {
    if (isGenerating || !currentFolderSearchData) return;
    const recs = (currentFolderSearchData.records || []).filter((r) => r.selected !== false);
    const notes = (currentFolderSearchData.notes || []).filter((n) => n.selected !== false);
    if (!recs.length && !notes.length) return;

    recs.forEach((r, idx) => {
      recordingsSources.push({
        id: `f_a_${Date.now()}_${idx}`,
        kind: 'folder',
        role: 'audio',
        name: r.name,
        size: r.size || 0,
        status: 'ready',
        file: null,
        link: r.url || null,
        local_path: r.local_path || null,
        start_slide: '',
        end_slide: '',
      });
    });

    notes.forEach((n, idx) => {
      notesSources.push({
        id: `f_n_${Date.now()}_${idx}`,
        kind: 'folder',
        role: 'notes',
        name: n.name,
        size: n.size || 0,
        status: 'ready',
        file: null,
        link: n.url || null,
        local_path: n.local_path || null,
        start_slide: '',
        end_slide: '',
      });
    });

    closeCourseFolderPanel();
    renderSourcesUI();
    showSuccessToast(`Added ${recs.length} recording(s) and ${notes.length} slide deck(s).`);
  }

  // --- Step 2: Study Focus Selector ---
  function selectStudyMode(mode) {
    if (isGenerating) return;
    const sel = $('studyMode');
    if (sel) sel.value = mode;
    syncStudyModeCards();
  }

  function syncStudyModeCards() {
    const mode = $('studyMode')?.value || 'detailed';
    document.querySelectorAll('.mode-card').forEach((card) => {
      const isMatch = card.dataset.mode === mode;
      card.classList.toggle('active', isMatch);
      card.setAttribute('aria-checked', String(isMatch));
    });
  }

  // --- Step 3: Optional Details & Fixed Per-Discipline Course Presets ---
  function loadPresetMap() {
    try {
      const raw = localStorage.getItem('lecturedesk_course_presets_v2');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') return parsed;
      }
      // Migrate legacy 'user_engineering_subjects' if present
      const legacy = localStorage.getItem('user_engineering_subjects');
      if (legacy) {
        const arr = JSON.parse(legacy);
        if (Array.isArray(arr) && arr.length) return { all: arr };
      }
    } catch (e) {}
    return {};
  }

  function savePresetMap(map) {
    try {
      localStorage.setItem('lecturedesk_course_presets_v2', JSON.stringify(map));
    } catch (e) {}
  }

  function getSubjectsForDiscipline(discipline) {
    const map = loadPresetMap();
    if (Array.isArray(map[discipline])) return [...map[discipline]];
    return [...(DISCIPLINE_PRESETS[discipline] || DISCIPLINE_PRESETS.all)];
  }

  function saveSubjectsForDiscipline(discipline, list) {
    const map = loadPresetMap();
    map[discipline] = list;
    savePresetMap(map);
  }

  function selectDisciplineFilter(discipline) {
    activeDisciplineFilter = discipline || 'all';
    document.querySelectorAll('.discipline-tab').forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.discipline === activeDisciplineFilter);
    });
    renderSubjectPresets();
  }

  function renderSubjectPresets() {
    const container = $('subjectBadgesContainer');
    if (!container) return;
    const subjects = getSubjectsForDiscipline(activeDisciplineFilter);
    const current = ($('courseInput')?.value || '').trim().toLowerCase();
    container.replaceChildren();

    if (!subjects.length) {
      const empty = document.createElement('span');
      empty.className = 'step-desc';
      empty.textContent = 'No courses saved in this category. Add one below.';
      container.appendChild(empty);
      return;
    }

    subjects.forEach((subj, idx) => {
      const chip = document.createElement('div');
      chip.className = `chip ${current && current === subj.toLowerCase() ? 'active' : ''}`;

      const lbl = document.createElement('span');
      lbl.textContent = subj;
      lbl.onclick = () => {
        if (isGenerating) return;
        $('courseInput').value = subj;
        onOptionalChanged();
        renderSubjectPresets();
      };

      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'chip-remove';
      del.textContent = '×';
      del.title = `Remove ${subj}`;
      del.onclick = (e) => {
        e.stopPropagation();
        if (isGenerating) return;
        const list = getSubjectsForDiscipline(activeDisciplineFilter);
        list.splice(idx, 1);
        saveSubjectsForDiscipline(activeDisciplineFilter, list);
        renderSubjectPresets();
      };

      chip.append(lbl, del);
      container.appendChild(chip);
    });
  }

  function addCustomSubject() {
    if (isGenerating) return;
    const inp = $('newSubjectInput');
    const val = (inp?.value || '').trim();
    if (!val) return;
    const list = getSubjectsForDiscipline(activeDisciplineFilter);
    if (!list.some((s) => s.toLowerCase() === val.toLowerCase())) {
      list.push(val);
      saveSubjectsForDiscipline(activeDisciplineFilter, list);
    }
    inp.value = '';
    $('courseInput').value = val;
    onOptionalChanged();
    renderSubjectPresets();
  }

  async function resetDefaultSubjects() {
    if (isGenerating) return;
    const ok = await askConfirm(
      'Reset course presets',
      `Restore the default course list for "${activeDisciplineFilter.toUpperCase()}"?`,
      'Reset',
      false
    );
    if (!ok) return;
    const map = loadPresetMap();
    delete map[activeDisciplineFilter];
    savePresetMap(map);
    renderSubjectPresets();
  }

  function onOptionalChanged() {
    const course = ($('courseInput')?.value || '').trim();
    const parts = [];
    parts.push(course || 'Auto-detect course');
    const included = [];
    if ($('includeDiagrams')?.checked) included.push('Diagrams');
    if ($('includeExam')?.checked) included.push('Exam Bank');
    if ($('includeTranscript')?.checked) included.push('Transcript');
    parts.push(included.length ? included.join(', ') : 'Core notes only');
    const summaryEl = $('optionalSummaryText');
    if (summaryEl) summaryEl.textContent = parts.join(' • ');
  }

  // --- Processing & Progress ---
  function resetProgressSteps() {
    ['stepAudio', 'stepTranslate', 'stepAudit', 'stepVisuals', 'stepPDF'].forEach((id) => {
      $(id)?.classList.remove('active');
    });
    if ($('progressPercent')) $('progressPercent').textContent = '5%';
    if ($('progressBar')) $('progressBar').style.width = '5%';
    if ($('progressStatusText')) $('progressStatusText').textContent = 'Preparing lecture sources...';
  }

  function setFormLocked(locked) {
    isGenerating = locked;
    const ids = [
      'unifiedFileInput', 'audioFileInput', 'notesFileInput',
      'btnAddAudio', 'btnAddNotes', 'btnPasteLink', 'btnCourseFolder', 'btnClearSources',
      'folderUrlInput', 'folderSessionQueryInput', 'searchFolderBtn',
      'courseInput', 'lecturerInput', 'newSubjectInput', 'addSubjectBtn', 'resetSubjectsBtn',
      'studyMode', 'modelSelect', 'includeDiagrams', 'includeExam', 'includeTranscript',
      'saveMediaToDrive', 'processBtn', 'demoBtn',
    ];
    ids.forEach((id) => {
      const el = $(id);
      if (el) el.disabled = locked;
    });
    document.querySelectorAll('.mode-card').forEach((c) => { c.disabled = locked; });
    $('selectionLockBanner')?.classList.toggle('hidden', !locked);
    renderSourcesUI();
  }

  async function startProcessing(isDemo) {
    hideSuccessToast();
    hideErrorBox();
    $('retryBtn')?.classList.add('hidden');
    lastWasDemo = isDemo;

    if (!isDemo && !hasApiKey) {
      openSettingsModal();
      showError('Add an API key in Settings to process live recordings, or click "Try Sample Lecture" to preview without a key.');
      return;
    }

    if (!isDemo && recordingsSources.length === 0) {
      showError('Add at least one audio recording from your computer, a link, or a course folder.');
      return;
    }

    const formData = new FormData();
    formData.append('model', $('modelSelect')?.value || 'gemini-4-hydrogen');
    formData.append('study_mode', $('studyMode')?.value || 'detailed');
    formData.append('include_diagrams', String(Boolean($('includeDiagrams')?.checked)));
    formData.append('include_exam_questions', String(Boolean($('includeExam')?.checked)));
    formData.append('include_transcript', String(Boolean($('includeTranscript')?.checked)));
    formData.append('save_media_to_drive', String(Boolean($('saveMediaToDrive')?.checked)));

    const courseHint = ($('courseInput')?.value || '').trim();
    const lecturerHint = ($('lecturerInput')?.value || '').trim();
    if (courseHint) formData.append('course_hint', courseHint);
    if (lecturerHint) formData.append('lecturer_hint', lecturerHint);
    if (isDemo) formData.append('demo_mode', 'true');

    const sourcesList = [];
    recordingsSources.forEach((item, idx) => {
      sourcesList.push({
        id: item.id,
        kind: item.kind,
        role: 'audio',
        order: idx,
        display_name: item.name,
        size: item.size || 0,
        link: item.link || null,
        local_path: item.local_path || null,
      });
      if (item.kind === 'upload' && item.file) {
        formData.append(`file_${item.id}`, item.file);
      }
    });

    notesSources.forEach((item, idx) => {
      const sVal = item.start_slide ? parseInt(item.start_slide, 10) : null;
      const eVal = item.end_slide ? parseInt(item.end_slide, 10) : null;
      sourcesList.push({
        id: item.id,
        kind: item.kind,
        role: 'notes',
        order: idx,
        display_name: item.name,
        size: item.size || 0,
        link: item.link || null,
        local_path: item.local_path || null,
        start_slide: Number.isNaN(sVal) ? null : sVal,
        end_slide: Number.isNaN(eVal) ? null : eVal,
      });
      if (item.kind === 'upload' && item.file) {
        formData.append(`file_${item.id}`, item.file);
      }
    });

    if (sourcesList.length > 0) {
      formData.append('sources', JSON.stringify(sourcesList));
    }

    resetProgressSteps();
    setFormLocked(true);
    $('progressSection')?.classList.remove('hidden');

    try {
      const res = await fetch('/api/process_audio', { method: 'POST', body: formData });
      if (!res.ok) {
        let msg = 'Processing request failed.';
        const raw = await res.text();
        try {
          msg = JSON.parse(raw).detail || msg;
        } catch (e) {
          msg = raw || msg;
        }
        throw new Error(msg);
      }
      const data = await res.json();
      activeJobId = data.job_id;
      pollStatus();
    } catch (e) {
      showError(e.message || 'Could not start processing.');
      $('progressSection')?.classList.add('hidden');
      setFormLocked(false);
    }
  }

  function pollStatus() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      if (!activeJobId) return;
      try {
        const res = await fetch(`/api/status/${encodeURIComponent(activeJobId)}`);
        if (res.status === 404) {
          clearInterval(pollInterval);
          activeJobId = null;
          $('progressSection')?.classList.add('hidden');
          setFormLocked(false);
          showError('This job is no longer tracked by the server. Please start again.');
          $('retryBtn')?.classList.remove('hidden');
          return;
        }
        if (!res.ok) return;
        const job = await res.json();

        $('progressPercent').textContent = `${job.progress}%`;
        $('progressBar').style.width = `${job.progress}%`;
        $('progressStatusText').textContent = job.status_message || 'Processing...';

        $('stepAudio')?.classList.toggle('active', job.progress >= 10);
        $('stepTranslate')?.classList.toggle('active', job.progress >= 40);
        $('stepAudit')?.classList.toggle('active', job.progress >= 70);
        $('stepVisuals')?.classList.toggle('active', job.progress >= 85);
        $('stepPDF')?.classList.toggle('active', job.progress >= 95);

        if (job.status === 'completed') {
          clearInterval(pollInterval);
          activeJobId = null;
          $('progressSection')?.classList.add('hidden');
          setFormLocked(false);
          await loadHistory();
          const match = historyCache.find((e) => e.result && e.result.pdf_filename === job.result.pdf_filename);
          currentResultHistoryId = match ? match.id : null;
          displayResults(job.result);
          showSuccessToast(
            lastWasDemo ? 'Sample lecture study guide is ready.' : 'Your study guide is ready.',
            lastWasDemo ? 'Sample Complete' : 'Study Guide Ready'
          );
        } else if (job.status === 'failed' || job.status === 'cancelled') {
          clearInterval(pollInterval);
          activeJobId = null;
          $('progressSection')?.classList.add('hidden');
          setFormLocked(false);
          showError(
            job.error || (job.status === 'cancelled' ? 'Generation cancelled.' : 'Generation failed.'),
            job.status === 'cancelled' ? 'Cancelled' : 'Generation Failed'
          );
          if (job.status !== 'cancelled') $('retryBtn')?.classList.remove('hidden');
        }
      } catch (e) {
        console.error('Status poll error:', e);
      }
    }, 1200);
  }

  async function cancelCurrentJob() {
    if (!activeJobId) return;
    const ok = await askConfirm('Cancel generation?', 'Stop processing the current lecture? Uploaded temporary files will be cleaned up.', 'Cancel job', true);
    if (!ok) return;
    try {
      const res = await fetch(`/api/cancel/${encodeURIComponent(activeJobId)}`, { method: 'POST' });
      if (res.ok) {
        if (pollInterval) clearInterval(pollInterval);
        activeJobId = null;
        $('progressSection')?.classList.add('hidden');
        setFormLocked(false);
        showError('Generation was cancelled.', 'Cancelled');
      } else {
        showError('Could not cancel the running job.');
      }
    } catch (err) {
      showError('Cancellation failed: ' + (err.message || err));
    }
  }

  function retryLastJob() {
    $('retryBtn')?.classList.add('hidden');
    startProcessing(lastWasDemo);
  }

  // --- Library (History) ---
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      if (!res.ok) throw new Error('Could not load saved guides.');
      historyCache = await res.json();
      const countPill = $('libraryCountPill');
      if (countPill) countPill.textContent = String(historyCache.length);
      renderHistoryList();
    } catch (err) {
      const container = $('historyContainer');
      if (container) {
        container.replaceChildren();
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = 'Local history is currently unavailable.';
        container.appendChild(empty);
      }
    }
  }

  function setHistoryFilter(mode) {
    historyModeFilter = mode || 'all';
    document.querySelectorAll('#historyModeFilters .chip').forEach((c) => {
      c.classList.toggle('active', c.dataset.filter === historyModeFilter);
    });
    renderHistoryList();
  }

  function renderHistoryList() {
    const container = $('historyContainer');
    if (!container) return;
    const query = ($('historySearchInput')?.value || '').trim().toLowerCase();

    const filtered = historyCache.filter((entry) => {
      if (historyModeFilter !== 'all' && (entry.study_mode || 'detailed') !== historyModeFilter) {
        return false;
      }
      if (!query) return true;
      const r = entry.result || {};
      const hay = `${r.lecture_title || ''} ${entry.source_name || ''} ${r.course_name || ''} ${MODE_LABELS[entry.study_mode] || entry.study_mode || ''}`.toLowerCase();
      return hay.includes(query);
    });

    container.replaceChildren();

    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = historyCache.length
        ? 'No saved study guides match your search or filter.'
        : 'No saved study guides yet. Create one or try the sample lecture.';
      container.appendChild(empty);
      return;
    }

    filtered.forEach((entry) => {
      const r = entry.result || {};
      const row = document.createElement('div');
      row.className = 'history-row';

      const info = document.createElement('div');
      info.style.cssText = 'min-width:0;flex:1 1 260px;';

      const title = document.createElement('p');
      title.className = 'history-title';
      title.textContent = r.lecture_title || entry.source_name || 'Untitled guide';

      const modeBadge = document.createElement('span');
      modeBadge.className = 'badge';
      modeBadge.textContent = MODE_LABELS[entry.study_mode] || entry.study_mode || 'Detailed notes';
      title.appendChild(modeBadge);

      const notesRef = entry.notes_reference || r.notes_reference;
      if (notesRef) {
        const refBadge = document.createElement('span');
        refBadge.className = 'badge badge-accent';
        refBadge.textContent = notesRef;
        title.appendChild(refBadge);
      }

      const meta = document.createElement('p');
      meta.className = 'history-meta';
      const dt = entry.created_at ? new Date(entry.created_at).toLocaleString() : '';
      meta.textContent = [r.course_name || 'Course', dt].filter(Boolean).join(' • ');

      info.append(title, meta);

      const actions = document.createElement('div');
      actions.className = 'history-actions';

      const readBtn = document.createElement('button');
      readBtn.type = 'button';
      readBtn.className = 'btn btn-sm btn-primary';
      readBtn.textContent = 'Read';
      readBtn.onclick = () => openHistoryEntry(entry.id, readBtn);

      const viewLink = document.createElement('a');
      viewLink.className = 'btn btn-sm';
      viewLink.href = `/api/view/${encodeURIComponent(r.pdf_filename || '')}`;
      viewLink.target = '_blank';
      viewLink.rel = 'noopener';
      viewLink.textContent = 'View PDF';

      const dlLink = document.createElement('a');
      dlLink.className = 'btn btn-sm';
      dlLink.href = `/api/download/${encodeURIComponent(r.pdf_filename || '')}`;
      dlLink.download = '';
      dlLink.textContent = 'Download';

      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'btn btn-sm btn-ghost';
      delBtn.title = 'Delete study guide';
      delBtn.textContent = 'Delete';
      delBtn.onclick = () => deleteHistoryEntry(entry.id, r.lecture_title || entry.source_name);

      actions.append(readBtn, viewLink, dlLink, delBtn);
      row.append(info, actions);
      container.appendChild(row);
    });
  }

  async function openHistoryEntry(historyId, button) {
    const orig = button.textContent;
    button.disabled = true;
    button.textContent = 'Opening...';
    try {
      const res = await fetch(`/api/history/${encodeURIComponent(historyId)}`);
      if (!res.ok) throw new Error('This saved guide could not be loaded.');
      const entry = await res.json();
      if (!entry.result || !entry.result.guide) {
        throw new Error('This record does not include readable web content.');
      }
      currentResultHistoryId = entry.id;
      displayResults(entry.result);
    } catch (err) {
      showError(err.message || 'Could not open this saved guide.');
    } finally {
      button.disabled = false;
      button.textContent = orig;
    }
  }

  async function deleteHistoryEntry(historyId, title) {
    const ok = await askConfirm(
      'Delete study guide?',
      `Permanently remove "${title || 'this study guide'}" from local history and delete its PDF file?`,
      'Delete permanently',
      true
    );
    if (!ok) return;

    try {
      const res = await fetch(`/api/history/${encodeURIComponent(historyId)}`, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success) {
        showSuccessToast('Study guide deleted from history and disk.');
        if (currentResultHistoryId === historyId) {
          currentResultHistoryId = null;
          $('navReader')?.classList.add('hidden');
          switchWorkspaceView('library');
        }
        await loadHistory();
      } else {
        showError(data.detail || data.message || 'Could not delete record.');
      }
    } catch (err) {
      showError('Delete failed: ' + (err.message || err));
    }
  }

  async function deleteCurrentResult() {
    if (currentResultHistoryId) {
      await deleteHistoryEntry(currentResultHistoryId, $('resLectureTitle')?.textContent);
      return;
    }
    const href = $('downloadBtn')?.getAttribute('href') || '';
    const pdfName = decodeURIComponent(href.replace('/api/download/', ''));
    const match = historyCache.find((e) => e.result && e.result.pdf_filename === pdfName);
    if (match) {
      await deleteHistoryEntry(match.id, $('resLectureTitle')?.textContent);
    } else {
      showError('Could not locate this guide in history. Delete it directly from the Library tab.');
    }
  }

  // --- Study Guide Reader ---
  function displayResults(data) {
    $('navReader')?.classList.remove('hidden');
    switchWorkspaceView('reader');

    $('resLectureTitle').textContent = data.lecture_title || 'Study Guide';
    const notesRef = data.notes_reference || data.guide?.notes_reference;
    const notesAudited = Boolean(data.notes_audited || data.verification_report?.notes_audited || notesRef);
    const metaParts = [data.course_name || 'Course'];
    if (data.lecturer_name) metaParts.push(`Instructor: ${data.lecturer_name}`);
    if (notesRef) metaParts.push(`Slides: ${notesRef}`);
    $('resCourseLecturer').textContent = metaParts.join(' • ');

    const encodedPdf = encodeURIComponent(data.pdf_filename || '');
    $('downloadBtn').href = `/api/download/${encodedPdf}`;
    $('viewPdfBtn').href = `/api/view/${encodedPdf}`;

    const driveBadge = $('resDriveBadge');
    if (data.drive_pdf_path) {
      driveBadge?.classList.remove('hidden');
      $('resDriveBadgeText').textContent = `Saved to Drive: ${data.drive_pdf_filename || 'Study Guide.pdf'}`;
    } else {
      driveBadge?.classList.add('hidden');
    }

    $('metricSections').textContent = String(data.sections_count ?? 0);
    $('metricAlerts').textContent = String(data.alerts_count ?? 0);
    $('metricDiagrams').textContent = String(data.diagrams_count ?? 0);
    $('metricQuestions').textContent = String(data.exam_questions_count ?? 0);
    $('countHighlightsTab').textContent = String(data.alerts_count ?? 0);

    // Verification strip
    renderVerificationStrip(data, notesAudited);

    const guide = data.guide || {};
    window.currentStudyGuide = guide;

    renderExamAlerts(guide);
    renderChapters(guide);
    renderExamQuestions(guide);

    currentTranscriptRaw = guide.full_transcript_english || '';
    if ($('transcriptSearchInput')) $('transcriptSearchInput').value = '';
    filterTranscript();

    // Reset Active Recall state
    $('recallQuiz')?.classList.add('hidden');
    $('recallComplete')?.classList.add('hidden');
    $('recallRetryMissedBtn')?.classList.add('hidden');
    if ($('recallStartBtn')) $('recallStartBtn').textContent = 'Start quiz';

    // Default to Notes & Visuals if 0 alerts, otherwise Exam Alerts
    const alertCount = Number(data.alerts_count || 0);
    switchTab(alertCount > 0 ? 'tabHighlights' : 'tabChapters');
  }

  function renderVerificationStrip(data, notesAudited) {
    const report = data.verification_report || data.guide?.verification_report;
    const card = $('verificationCard');
    const titleEl = $('verifBadgeTitle');
    const tsEl = $('verifTimestamp');
    const sumEl = $('verifSummary');
    const reconBox = $('verifReconciliationContainer');
    const reconList = $('verifReconciliationList');

    if (!report) {
      card?.classList.add('hidden');
      return;
    }

    card.classList.remove('hidden');
    const scope = notesAudited ? 'Transcript & Slides Check' : 'Transcript Check';
    const isDemo = Boolean(report.is_simulation || data.is_demo || data.guide?.is_demo);

    if (report.audit_passed === false) {
      card.className = 'verif-strip err';
      titleEl.textContent = `${scope}: Unavailable`;
      tsEl.textContent = 'Audit could not be completed';
      sumEl.textContent = report.overall_fidelity_summary || 'Verification cross-check could not be completed.';
      reconBox.classList.add('hidden');
    } else if (report.contradictions_detected > 0) {
      card.className = 'verif-strip info';
      titleEl.textContent = `${scope}: ${report.contradictions_detected} Issue(s) Reconciled`;
      tsEl.textContent = 'Audio-to-transcript accuracy is not independently verified';
      sumEl.textContent = report.overall_fidelity_summary || '';
      if (Array.isArray(report.contradictions) && report.contradictions.length > 0) {
        reconBox.classList.remove('hidden');
        reconList.replaceChildren();
        report.contradictions.forEach((c) => {
          const item = document.createElement('div');
          item.className = 'callout';
          item.style.margin = '0';
          item.innerHTML = `
            <p class="callout-title">${escapeHtml(c.section_title)}</p>
            <p class="callout-body"><strong>Initial:</strong> ${escapeHtml(c.guide_statement)}<br>
            <strong>Transcript:</strong> ${escapeHtml(c.audio_truth)}<br>
            <strong>Fix:</strong> ${escapeHtml(c.correction_applied)}</p>
          `;
          reconList.appendChild(item);
        });
      } else {
        reconBox.classList.add('hidden');
      }
    } else if (isDemo) {
      card.className = 'verif-strip warn';
      titleEl.textContent = 'Sample Mode: Simulated Check';
      tsEl.textContent = 'No live audio recording was processed';
      sumEl.textContent = report.overall_fidelity_summary || 'Simulated sample study guide.';
      reconBox.classList.add('hidden');
    } else {
      card.className = 'verif-strip ok';
      titleEl.textContent = `${scope}: No Discrepancies Found`;
      tsEl.textContent = 'Audio-to-transcript accuracy is not independently verified';
      sumEl.textContent = report.overall_fidelity_summary || 'Checked against the transcript.';
      reconBox.classList.add('hidden');
    }
  }

  function renderExamAlerts(guide) {
    const container = $('alertsContainer');
    container.replaceChildren();
    const allAlerts = [];
    (guide.sections || []).forEach((s) => {
      if (Array.isArray(s.doctor_alerts)) allAlerts.push(...s.doctor_alerts);
    });

    if (!allAlerts.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state card';
      empty.textContent = 'No explicit professor exam alerts were detected in this lecture.';
      container.appendChild(empty);
      return;
    }

    allAlerts.forEach((a) => {
      const card = document.createElement('article');
      card.className = 'alert-card';
      card.innerHTML = `
        <div class="toolbar-row" style="margin-bottom:6px;">
          <strong style="font-size:13.5px;color:var(--ochre-ink);">${formatInlineMathHtml(a.highlight_title)}</strong>
          <span class="badge badge-ochre">${escapeHtml(a.alert_type || 'EXAM FOCUS')}</span>
        </div>
        <div class="alert-cue"><strong>Spoken cue:</strong> &ldquo;${formatInlineMathHtml(a.cue_detected)}&rdquo;</div>
        <p style="margin:6px 0;font-size:13.5px;"><strong>Core concept:</strong> ${formatInlineMathHtml(a.alert_content)}</p>
        <p style="margin:6px 0 0;font-size:13px;color:var(--danger-ink);"><strong>Exam pitfall:</strong> ${formatInlineMathHtml(a.exam_impact)}</p>
      `;
      container.appendChild(card);
    });
  }

  function renderChapters(guide) {
    const container = $('chaptersContainer');
    const tocBar = $('chapterTocBar');
    const tocChips = $('chapterTocChips');
    container.replaceChildren();
    tocChips.replaceChildren();

    const sections = guide.sections || [];
    if (sections.length > 1) {
      tocBar.classList.remove('hidden');
      sections.forEach((s) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chip';
        btn.textContent = `${s.section_number}. ${s.topic_title}`;
        btn.onclick = () => {
          document.getElementById(`chapter_${s.section_number}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        };
        tocChips.appendChild(btn);
      });
    } else {
      tocBar.classList.add('hidden');
    }

    sections.forEach((s) => {
      const secEl = document.createElement('article');
      secEl.className = 'chapter-card';
      secEl.id = `chapter_${s.section_number}`;

      const headHtml = `
        <div class="chapter-head">
          <h3>Chapter ${escapeHtml(s.section_number)}: ${formatInlineMathHtml(s.topic_title)}</h3>
          ${s.source_reference ? `<span class="badge badge-mono">${escapeHtml(s.source_reference)}</span>` : ''}
        </div>
      `;

      const explanationHtml = `<div class="prose-text">${formatInlineMathHtml(s.detailed_explanation)}</div>`;

      // Verbatim & Simplified Mode Callouts (now rendered in Web Reader too!)
      let verbatimHtml = '';
      if (s.doctor_exact_wording) {
        verbatimHtml += `
          <div class="callout callout-verbatim">
            <p class="callout-title">Doctor's Spoken Words (English Translation)</p>
            <p class="callout-body">&ldquo;${formatInlineMathHtml(s.doctor_exact_wording)}&rdquo;</p>
          </div>`;
      }
      if (s.simple_explanation) {
        verbatimHtml += `
          <div class="callout callout-simple">
            <p class="callout-title">In Simple Terms</p>
            <p class="callout-body">${formatInlineMathHtml(s.simple_explanation)}</p>
          </div>`;
      }
      if (s.practical_example) {
        verbatimHtml += `
          <div class="callout callout-example">
            <p class="callout-title">Practical Real-World Example</p>
            <p class="callout-body">${formatInlineMathHtml(s.practical_example)}</p>
          </div>`;
      }

      const bulletsHtml = (Array.isArray(s.key_bullet_points) && s.key_bullet_points.length)
        ? `<ul class="bullets-box">${s.key_bullet_points.map((b) => `<li>${formatInlineMathHtml(b)}</li>`).join('')}</ul>`
        : '';

      const formulasHtml = (Array.isArray(s.formulas) && s.formulas.length)
        ? s.formulas.map((f, idx) => `
            <div class="formula-card">
              <strong style="font-size:12.5px;color:var(--accent-ink);">Equation ${idx + 1}: ${formatInlineMathHtml(f.formula_name)}</strong>
              <div class="formula-expr">${formatInlineMathHtml(f.plain_text_expression || f.latex_expression)}</div>
              ${Array.isArray(f.variables_explanation) && f.variables_explanation.length
                ? `<p style="margin:6px 0 0;font-size:12.5px;color:var(--ink-secondary);"><strong>Where:</strong> ${f.variables_explanation.map(formatInlineMathHtml).join(' &bull; ')}</p>`
                : ''}
              ${f.exam_application
                ? `<p style="margin:5px 0 0;font-size:12.5px;color:var(--accent-ink);"><strong>Exam note:</strong> ${formatInlineMathHtml(f.exam_application)}</p>`
                : ''}
            </div>`).join('')
        : '';

      const tablesHtml = (Array.isArray(s.tables) && s.tables.length)
        ? s.tables.map((t) => `
            <div class="data-table-wrap">
              <div class="data-table-title">${formatInlineMathHtml(t.title)}</div>
              <table class="data-table">
                <thead><tr>${(t.columns || []).map((c) => `<th>${formatInlineMathHtml(c)}</th>`).join('')}</tr></thead>
                <tbody>
                  ${(t.rows || []).map((row) => `<tr>${row.map((cell) => `<td>${formatInlineMathHtml(cell)}</td>`).join('')}</tr>`).join('')}
                </tbody>
              </table>
            </div>`).join('')
        : '';

      secEl.innerHTML = headHtml + explanationHtml + verbatimHtml + bulletsHtml + formulasHtml + tablesHtml;

      // Append diagrams with safe click-to-zoom lightbox
      if (Array.isArray(s.diagrams) && s.diagrams.length) {
        s.diagrams.forEach((d) => {
          const fig = document.createElement('figure');
          fig.className = 'diagram-figure';
          const img = document.createElement('img');
          const safeSrc = `/assets/diagram_${encodeURIComponent(d.diagram_id)}.png`;
          img.src = safeSrc;
          img.alt = d.title || 'Diagram';
          img.title = 'Click to zoom';
          img.onclick = () => openLightbox(safeSrc, d.title, d.caption);
          const cap = document.createElement('figcaption');
          cap.className = 'diagram-caption';
          cap.textContent = `Figure: ${d.title || ''} — ${d.caption || ''}`;
          fig.append(img, cap);
          secEl.appendChild(fig);
        });
      }

      container.appendChild(secEl);
    });
  }

  function renderExamQuestions(guide) {
    const container = $('examContainer');
    container.replaceChildren();
    allAnswersExpanded = false;
    if ($('toggleAllAnswersBtn')) $('toggleAllAnswersBtn').textContent = 'Show all answers';

    const questions = guide.exam_readiness_section || [];
    if (!questions.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state card';
      empty.textContent = 'No exam practice questions were included for this guide.';
      container.appendChild(empty);
      return;
    }

    questions.forEach((q, idx) => {
      const card = document.createElement('article');
      card.className = 'exam-card stack-sm';

      const optsHtml = (Array.isArray(q.options) && q.options.length)
        ? `<div class="stack-sm" style="padding-left:10px;font-size:13.5px;color:var(--ink-secondary);">${q.options.map((o) => `<div>${formatInlineMathHtml(o)}</div>`).join('')}</div>`
        : '';

      const isDefinite = String(q.probability || '').toLowerCase().includes('definite');

      card.innerHTML = `
        <div class="toolbar-row">
          <span class="badge badge-accent">Question ${escapeHtml(q.question_number)} &bull; ${escapeHtml(q.question_type)}</span>
          <span class="badge ${isDefinite ? 'badge-danger' : 'badge-ochre'}">${escapeHtml(q.probability || 'Exam practice')}</span>
        </div>
        <p style="margin:4px 0;font-size:14.5px;font-weight:600;">${formatInlineMathHtml(q.question_prompt)}</p>
        ${optsHtml}
        <div>
          <button type="button" class="btn btn-sm" data-toggle-ans="ans_${idx}">Show model answer</button>
        </div>
        <div id="ans_${idx}" class="answer-box stack-sm hidden">
          <div><strong style="color:var(--forest-ink);">Model answer:</strong><div style="white-space:pre-line;margin-top:3px;">${formatInlineMathHtml(q.correct_answer)}</div></div>
          <div><strong>Grading rubric:</strong> ${formatInlineMathHtml(q.model_explanation)}</div>
          <div style="color:var(--ochre-ink);"><strong>Professor's hint:</strong> &ldquo;${formatInlineMathHtml(q.doctor_hint)}&rdquo;</div>
        </div>
      `;

      const toggleBtn = card.querySelector(`[data-toggle-ans="ans_${idx}"]`);
      const ansDiv = card.querySelector(`#ans_${idx}`);
      if (toggleBtn && ansDiv) {
        toggleBtn.onclick = () => {
          const opening = ansDiv.classList.contains('hidden');
          ansDiv.classList.toggle('hidden', !opening);
          toggleBtn.textContent = opening ? 'Hide model answer' : 'Show model answer';
        };
      }

      container.appendChild(card);
    });
  }

  function toggleAllExamAnswers() {
    allAnswersExpanded = !allAnswersExpanded;
    const btn = $('toggleAllAnswersBtn');
    if (btn) btn.textContent = allAnswersExpanded ? 'Hide all answers' : 'Show all answers';
    document.querySelectorAll('#examContainer [data-toggle-ans]').forEach((b) => {
      const targetId = b.getAttribute('data-toggle-ans');
      const div = $(targetId);
      if (div) div.classList.toggle('hidden', !allAnswersExpanded);
      b.textContent = allAnswersExpanded ? 'Hide model answer' : 'Show model answer';
    });
  }

  // --- Active Recall Quiz ---
  function startRecallQuiz() {
    const questions = (window.currentStudyGuide?.exam_readiness_section || []).filter((q) => q.question_prompt && q.correct_answer);
    if (!questions.length) return;
    recallMissed = [];
    $('recallRetryMissedBtn')?.classList.add('hidden');
    beginRecallQuiz(questions);
  }

  function startMissedRecallQuiz() {
    if (!recallMissed.length) return;
    const retry = [...recallMissed];
    recallMissed = [];
    $('recallRetryMissedBtn')?.classList.add('hidden');
    beginRecallQuiz(retry);
  }

  function beginRecallQuiz(questions) {
    recallQuestions = questions;
    recallIndex = 0;
    recallScore = 0;
    $('recallComplete')?.classList.add('hidden');
    $('recallQuiz')?.classList.remove('hidden');
    if ($('recallStartBtn')) $('recallStartBtn').textContent = 'Restart quiz';
    renderRecallQuestion();
  }

  function renderRecallQuestion() {
    const q = recallQuestions[recallIndex];
    const total = recallQuestions.length;
    recallAnswerRevealed = false;
    $('recallProgress').textContent = `Question ${recallIndex + 1} of ${total}`;
    $('recallScore').textContent = `${recallScore} got it`;
    $('recallProgressBar').style.width = `${(recallIndex / total) * 100}%`;
    $('recallPrompt').innerHTML = formatInlineMathHtml(q.question_prompt);

    const opts = $('recallOptions');
    opts.replaceChildren();
    (q.options || []).forEach((o) => {
      const p = document.createElement('div');
      p.innerHTML = formatInlineMathHtml(o);
      opts.appendChild(p);
    });

    const ans = $('recallAnswer');
    ans.innerHTML = `
      <div><strong style="color:var(--forest-ink);">Model answer:</strong> ${formatInlineMathHtml(q.correct_answer)}</div>
      <div><strong>Rubric:</strong> ${formatInlineMathHtml(q.model_explanation || 'Review the key reasoning.')}</div>
      <div style="color:var(--ochre-ink);"><strong>Lecture hint:</strong> ${formatInlineMathHtml(q.doctor_hint || 'No specific hint recorded.')}</div>
    `;
    ans.classList.add('hidden');
    $('recallRevealBtn')?.classList.remove('hidden');
    $('recallRating')?.classList.add('hidden');
  }

  function revealRecallAnswer() {
    recallAnswerRevealed = true;
    $('recallAnswer')?.classList.remove('hidden');
    $('recallRevealBtn')?.classList.add('hidden');
    $('recallRating')?.classList.remove('hidden');
  }

  function rateRecallAnswer(gotIt) {
    if (gotIt) recallScore++;
    else recallMissed.push(recallQuestions[recallIndex]);
    recallIndex++;
    if (recallIndex < recallQuestions.length) {
      renderRecallQuestion();
      return;
    }
    $('recallQuiz')?.classList.add('hidden');
    $('recallProgressBar').style.width = '100%';
    const complete = $('recallComplete');
    complete.textContent = recallMissed.length
      ? `Session complete: ${recallScore} of ${recallQuestions.length} marked "Got it". Retry the ${recallMissed.length} missed question(s).`
      : `Session complete: ${recallScore} of ${recallQuestions.length} marked "Got it".`;
    complete.classList.remove('hidden');
    $('recallRetryMissedBtn')?.classList.toggle('hidden', recallMissed.length === 0);
  }

  // --- Transcript Search & Copy ---
  function filterTranscript() {
    const container = $('transcriptContainer');
    const badge = $('transcriptMatchBadge');
    const q = ($('transcriptSearchInput')?.value || '').trim();
    if (!container) return;

    if (!q) {
      container.textContent = currentTranscriptRaw || 'No transcript available.';
      badge?.classList.add('hidden');
      return;
    }

    const escapedRaw = escapeHtml(currentTranscriptRaw);
    const escapedQuery = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(${escapedQuery})`, 'gi');
    let count = 0;
    const highlighted = escapedRaw.replace(re, (m) => {
      count++;
      return `<mark class="search-hit">${m}</mark>`;
    });
    container.innerHTML = highlighted;
    if (badge) {
      badge.textContent = `${count} match${count === 1 ? '' : 'es'}`;
      badge.classList.remove('hidden');
    }
  }

  async function copyTranscript() {
    if (!currentTranscriptRaw) return;
    try {
      await navigator.clipboard.writeText(currentTranscriptRaw);
      showSuccessToast('Transcript copied to clipboard.', 'Copied');
    } catch (e) {
      showError('Clipboard access was blocked by the browser.');
    }
  }

  // --- Reader Tabs ---
  function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach((p) => p.classList.add('hidden'));
    document.querySelectorAll('.reader-tab').forEach((b) => b.classList.remove('active'));
    $(tabId)?.classList.remove('hidden');

    const map = {
      tabHighlights: 'btnTabHighlights',
      tabChapters: 'btnTabChapters',
      tabExam: 'btnTabExam',
      tabTranscript: 'btnTabTranscript',
    };
    $(map[tabId])?.classList.add('active');
  }

  // --- Global Keyboard Shortcuts ---
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!$('lightboxModal')?.classList.contains('hidden')) { closeLightbox(); return; }
      if (!$('confirmModal')?.classList.contains('hidden')) { resolveConfirmModal(false); return; }
      if (!$('keyModal')?.classList.contains('hidden')) { closeSettingsModal(); return; }
    }

    // Active Recall keyboard shortcuts (only when quiz is visible and not typing in an input)
    const tag = (document.activeElement?.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    const quizOpen = !$('recallQuiz')?.classList.contains('hidden') && !$('tabExam')?.classList.contains('hidden');
    if (quizOpen) {
      if (e.code === 'Space' && !recallAnswerRevealed) {
        e.preventDefault();
        revealRecallAnswer();
      } else if (e.key === '1' && recallAnswerRevealed) {
        e.preventDefault();
        rateRecallAnswer(false);
      } else if (e.key === '2' && recallAnswerRevealed) {
        e.preventDefault();
        rateRecallAnswer(true);
      }
    }
  });

  // --- Expose handlers needed by HTML attributes ---
  Object.assign(window, {
    toggleTheme,
    switchWorkspaceView,
    hideSuccessToast,
    hideErrorBox,
    openSettingsModal,
    closeSettingsModal,
    toggleKeyVisibility,
    saveApiKey,
    resolveConfirmModal,
    closeLightbox,
    triggerUnifiedFilePick,
    triggerAudioFilePick,
    triggerNotesFilePick,
    handleUnifiedFileInput,
    handleComputerFileInput,
    handleUnifiedDragOver,
    handleUnifiedDragLeave,
    handleUnifiedDrop,
    toggleLinkDrawer,
    addSharedLinkItem,
    clearAllSources,
    toggleCourseFolderPanel,
    closeCourseFolderPanel,
    setSessionQueryAndSearch,
    searchCourseFolder,
    selectStudyMode,
    syncStudyModeCards,
    selectDisciplineFilter,
    addCustomSubject,
    resetDefaultSubjects,
    onOptionalChanged,
    startProcessing,
    cancelCurrentJob,
    retryLastJob,
    loadHistory,
    setHistoryFilter,
    renderHistoryList,
    deleteCurrentResult,
    switchTab,
    startRecallQuiz,
    startMissedRecallQuiz,
    revealRecallAnswer,
    rateRecallAnswer,
    toggleAllExamAnswers,
    filterTranscript,
    copyTranscript,
  });

  // --- Bootstrap ---
  window.addEventListener('DOMContentLoaded', () => {
    const savedTheme = (() => {
      try { return localStorage.getItem('lecturedesk_theme') || 'light'; } catch (e) { return 'light'; }
    })();
    applyTheme(savedTheme);
    checkKeyStatus();
    loadHistory();
    renderSubjectPresets();
    loadDetectedCourses();
    renderSourcesUI();
    syncStudyModeCards();
    onOptionalChanged();
  });
})();
