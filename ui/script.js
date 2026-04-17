// ============================================================
// script.js — SwitchBot UI
// ============================================================

// ── Referências DOM ──
const input = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const timeline = document.getElementById('timeline');
const statusDot = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');
const stopBar = document.getElementById('stopBar');
const stopBtn = document.getElementById('stopBtn');
const modelBadge = document.getElementById('modelBadge');

// Settings
const btnSettings = document.getElementById('btnSettings');
const btnCloseSettings = document.getElementById('btnCloseSettings');
const settingsPanel = document.getElementById('settingsPanel');
const settingsOverlay = document.getElementById('settingsOverlay');
const btnCloud = document.getElementById('btnCloud');
const btnLocal = document.getElementById('btnLocal');
const sectionCloud = document.getElementById('sectionCloud');
const sectionLocal = document.getElementById('sectionLocal');
const groqLoading = document.getElementById('groqLoading');
const groqModelList = document.getElementById('groqModelList');
const ollamaStatus = document.getElementById('ollamaStatus');
const installedSection = document.getElementById('installedSection');
const installedList = document.getElementById('installedList');
const catalogSection = document.getElementById('catalogSection');
const catalogList = document.getElementById('catalogList');
const btnSave = document.getElementById('btnSaveSettings');

// ── Estado Global ──
let isProcessing = false;
let currentExecutingCard = null;

// Seleção temporária no painel (só salva ao clicar em Aplicar)
let pendingProvider = null;
let pendingGroqModel = null;
let pendingOllamaModel = null;

// Config atual (carregada do servidor)
let currentConfig = { provider: 'groq', groq_model: '', ollama_model: null };

// ============================================================
// INICIALIZAÇÃO
// ============================================================
async function init() {
    await loadCurrentConfig();
    connectSSE();
}

async function loadCurrentConfig() {
    try {
        const res = await fetch('/api/settings');
        currentConfig = await res.json();
        updateModelBadge(currentConfig);
    } catch (e) {
        console.error('Erro ao carregar config:', e);
    }
}

function updateModelBadge(config) {
    if (config.provider === 'groq') {
        const short = config.groq_model.replace('llama-', 'L').replace('-versatile', '').replace('-instant', '');
        modelBadge.textContent = '☁️ ' + short;
    } else {
        modelBadge.textContent = '🖥️ ' + (config.ollama_model || 'local');
    }
}

// ============================================================
// SSE — REAL-TIME EVENTS
// ============================================================
function connectSSE() {
    const es = new EventSource('/api/events');

    es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'ping') return;

        if (data.type === 'feedback') {
            handleFeedback(data.msg_type, data.text);
        } else if (data.type === 'response') {
            handleResponse(data.text);
        }
    };

    es.onerror = () => {
        setStatus('error', 'Desconectado');
        setTimeout(() => {
            setStatus('', 'Reconectando...');
            connectSSE();
        }, 3000);
    };
}

// ============================================================
// AUDIO ENGINE
// ============================================================
function playSound(type) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        switch (type) {
            case 'success':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(523, ctx.currentTime);
                osc.frequency.setValueAtTime(659, ctx.currentTime + 0.1);
                osc.frequency.setValueAtTime(784, ctx.currentTime + 0.2);
                gain.gain.setValueAtTime(0.12, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.45);
                break;
            case 'error':
                osc.type = 'square';
                osc.frequency.setValueAtTime(330, ctx.currentTime);
                osc.frequency.setValueAtTime(220, ctx.currentTime + 0.15);
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3);
                break;
            case 'cancel':
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(440, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.2);
                gain.gain.setValueAtTime(0.1, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.25);
                break;
            case 'send':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(1200, ctx.currentTime);
                gain.gain.setValueAtTime(0.06, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.08);
                break;
            case 'saved':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(440, ctx.currentTime);
                osc.frequency.setValueAtTime(554, ctx.currentTime + 0.08);
                gain.gain.setValueAtTime(0.1, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.25);
                break;
        }
    } catch (e) { }
}

// ============================================================
// STATUS
// ============================================================
function setStatus(state, label) {
    statusDot.className = 'status-dot ' + state;
    statusLabel.textContent = label;
}

// ============================================================
// CARDS DA TIMELINE
// ============================================================
function clearWelcome() {
    const w = document.getElementById('welcomeMsg');
    if (w) {
        w.style.transition = 'opacity 0.3s, transform 0.3s';
        w.style.opacity = '0';
        w.style.transform = 'scale(0.95)';
        setTimeout(() => w.remove(), 300);
    }
}

function createCard(type, content) {
    clearWelcome();
    const card = document.createElement('div');

    switch (type) {
        case 'user':
            card.className = 'card card-user';
            card.textContent = content;
            break;

        case 'thought':
            card.className = 'card card-thought active';
            card.innerHTML = `
                <div class="card-header"><span>💭</span> Pensamento</div>
                <div>${escapeHtml(content)}</div>`;
            break;

        case 'executing':
            card.className = 'card card-executing';
            card.innerHTML = `
                <div class="spinner-sm"></div>
                <div>
                    <div class="card-header"><span>⚙️</span> Executando</div>
                    <div>${escapeHtml(content)}</div>
                </div>`;
            currentExecutingCard = card;
            break;

        case 'result':
            card.className = 'card card-result';
            card.innerHTML = `
                <div class="card-header"><span>✅</span> Resultado</div>
                <div><span class="typing-text"></span><span class="typing-cursor"></span></div>`;
            timeline.appendChild(card);
            timeline.scrollTop = timeline.scrollHeight;
            typeText(card.querySelector('.typing-text'), content, card.querySelector('.typing-cursor'));
            return card;

        case 'error':
            card.className = 'card card-error';
            card.innerHTML = `
                <div class="card-header"><span>❌</span> Erro</div>
                <div>${formatResponse(content)}</div>`;
            break;

        case 'cancelled':
            card.className = 'card card-cancelled';
            card.innerHTML = `
                <div class="card-header"><span>⏹️</span> Cancelada</div>
                <div>Tarefa interrompida pelo usuário.</div>`;
            break;
    }

    timeline.appendChild(card);
    timeline.scrollTop = timeline.scrollHeight;
    return card;
}

function removeExecutingCard() {
    if (currentExecutingCard) {
        currentExecutingCard.style.transition = 'opacity 0.2s, transform 0.2s';
        currentExecutingCard.style.opacity = '0';
        currentExecutingCard.style.transform = 'scale(0.95)';
        const ref = currentExecutingCard;
        setTimeout(() => ref.remove(), 200);
        currentExecutingCard = null;
    }
}

// ============================================================
// TYPING EFFECT
// ============================================================
function typeText(element, text, cursor) {
    const formatted = formatResponse(text);
    if (text.length > 500) {
        element.innerHTML = formatted;
        cursor?.remove();
        return;
    }
    const speed = text.length > 200 ? 5 : text.length > 80 ? 12 : 20;
    let i = 0;
    function type() {
        if (i < formatted.length) {
            if (formatted[i] === '<') {
                const end = formatted.indexOf('>', i);
                if (end !== -1) { element.innerHTML += formatted.substring(i, end + 1); i = end + 1; }
                else { element.innerHTML += formatted[i++]; }
            } else {
                element.innerHTML += formatted[i++];
            }
            timeline.scrollTop = timeline.scrollHeight;
            setTimeout(type, speed);
        } else {
            cursor?.remove();
        }
    }
    type();
}

// ============================================================
// HELPERS
// ============================================================
function escapeHtml(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
}

function formatResponse(t) {
    // Se a biblioteca marked estiver carregada, transforma Markdown em HTML
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true }); // Permite quebrar linha com Enter normal
        return marked.parse(t);
    }
    // Fallback original caso falhe
    return escapeHtml(t).replace(/\\n/g, '<br>').replace(/\n/g, '<br>');
}

// ============================================================
// FEEDBACK / RESPONSE HANDLERS
// ============================================================
function handleFeedback(msg_type, text) {
    if (msg_type === 'thought') {
        setStatus('thinking', 'Pensando...');
        timeline.querySelectorAll('.card-thought.active').forEach(c => c.classList.remove('active'));
        createCard('thought', text);
    } else if (msg_type === 'executing') {
        setStatus('executing', 'Executando...');
        removeExecutingCard();
        createCard('executing', text);
    } else if (msg_type === 'system') {
        setStatus('executing', 'Processando...');
        removeExecutingCard();
        createCard('executing', text);
    }
}

function handleResponse(text) {
    removeExecutingCard();
    hideStopBar();
    timeline.querySelectorAll('.card-thought.active').forEach(c => c.classList.remove('active'));

    const isCancelled = text.includes('cancelada') || text.includes('⏹️');
    const isError = text.startsWith('Erro') || text.includes('⚠️');

    if (isCancelled) {
        createCard('cancelled', text);
        setStatus('', 'Online');
        playSound('cancel');
    } else if (isError) {
        createCard('error', text);
        setStatus('error', 'Erro');
        playSound('error');
        setTimeout(() => setStatus('', 'Online'), 3000);
    } else {
        createCard('result', text);
        setStatus('', 'Online');
        playSound('success');
    }

    isProcessing = false;
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
}

// ============================================================
// STOP
// ============================================================
function showStopBar() { stopBar.classList.remove('hidden'); }
function hideStopBar() { stopBar.classList.add('hidden'); }

// ============================================================
// SEND
// ============================================================
async function handleSend(promptText) {
    const val = (promptText || input.value).trim();
    if (!val || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;
    input.value = '';

    playSound('send');
    createCard('user', val);
    setStatus('thinking', 'Analisando...');
    showStopBar();

    try {
        await fetch('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: val })
        });
    } catch (e) {
        hideStopBar();
        setStatus('error', 'Erro de conexão');
        createCard('error', 'Falha ao contatar o servidor: ' + e.message);
        playSound('error');
        isProcessing = false;
        sendBtn.disabled = false;
    }
}

// ============================================================
// SETTINGS PANEL
// ============================================================
function openSettings() {
    settingsPanel.classList.remove('hidden');
    settingsOverlay.classList.remove('hidden');

    // Copia config atual como pendente
    pendingProvider = currentConfig.provider;
    pendingGroqModel = currentConfig.groq_model;
    pendingOllamaModel = currentConfig.ollama_model;

    // Ativa o tab correto
    if (currentConfig.provider === 'ollama') {
        switchTab('ollama');
    } else {
        switchTab('groq');
    }
}

function closeSettings() {
    settingsPanel.classList.add('hidden');
    settingsOverlay.classList.add('hidden');
}

function switchTab(provider) {
    pendingProvider = provider;

    btnCloud.classList.toggle('active', provider === 'groq');
    btnLocal.classList.toggle('active', provider === 'ollama');
    sectionCloud.classList.toggle('hidden', provider !== 'groq');
    sectionLocal.classList.toggle('hidden', provider !== 'ollama');

    if (provider === 'groq') loadGroqModels();
    else loadOllamaModels();
}

// ── Groq ──────────────────────────────────────────────────
async function loadGroqModels() {
    groqLoading.classList.remove('hidden');
    groqModelList.innerHTML = '';

    try {
        const res = await fetch('/api/models/groq');
        const data = await res.json();

        groqLoading.classList.add('hidden');

        if (data.error) {
            groqModelList.innerHTML = `<div style="color:#ff5252;font-size:12px;padding:8px">${data.error}</div>`;
            return;
        }

        data.models.forEach(m => {
            const card = document.createElement('div');
            card.className = 'model-card' + (m.id === pendingGroqModel ? ' selected' : '');
            card.dataset.modelId = m.id;
            card.innerHTML = `
                <div class="model-card-name">${m.id}</div>
                <div class="model-card-meta">
                    <span class="model-tag">${m.owned_by || 'Meta'}</span>
                    <span class="model-tag size">${m.context}</span>
                </div>`;
            card.addEventListener('click', () => {
                document.querySelectorAll('#groqModelList .model-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                pendingGroqModel = m.id;
            });
            groqModelList.appendChild(card);
        });
    } catch (e) {
        groqLoading.classList.add('hidden');
        groqModelList.innerHTML = `<div style="color:#ff5252;font-size:12px;padding:8px">Erro ao carregar: ${e.message}</div>`;
    }
}

// ── Ollama ────────────────────────────────────────────────
async function loadOllamaModels() {
    ollamaStatus.className = 'ollama-status';
    ollamaStatus.innerHTML = '<div class="mini-spinner"></div> Verificando Ollama...';
    installedSection.classList.add('hidden');
    catalogSection.classList.add('hidden');

    try {
        const res = await fetch('/api/models/ollama');
        const data = await res.json();

        if (!data.running) {
            ollamaStatus.className = 'ollama-status offline';
            ollamaStatus.innerHTML = `
                <div>⚠️ Ollama não está em execução</div>
                <div style="font-size:11px">
                    Não instalado ou não iniciado.<br>
                    <a class="install-link" href="https://ollama.com/download" target="_blank">⬇️ Baixar Ollama para Windows</a>
                    <br><span style="color:#888">Após instalar, reinicie o SwitchBot.</span>
                </div>`;
            return;
        }

        ollamaStatus.className = 'ollama-status online';
        ollamaStatus.innerHTML = '✅ Ollama Online e pronto';

        // Modelos instalados
        if (data.installed.length > 0) {
            installedSection.classList.remove('hidden');
            installedList.innerHTML = '';
            data.installed.forEach(m => renderInstalledModel(m));
        }

        // Catálogo
        catalogSection.classList.remove('hidden');
        catalogList.innerHTML = '';
        data.catalog.forEach(m => renderCatalogModel(m));

    } catch (e) {
        ollamaStatus.className = 'ollama-status offline';
        ollamaStatus.innerHTML = `⚠️ Erro ao verificar Ollama: ${e.message}`;
    }
}

function renderInstalledModel(m) {
    const isActive = m.name === pendingOllamaModel;
    const card = document.createElement('div');
    card.className = 'model-card';
    card.id = `installed-${m.name.replace(/[:. ]/g, '-')}`;
    card.innerHTML = `
        <div class="model-card-name">${m.name}</div>
        <div class="model-card-meta">
            <span class="model-tag size">${m.size_gb} GB</span>
        </div>
        <div class="model-card-actions">
            <button class="btn-use${isActive ? ' active-model' : ''}" data-model="${m.name}">
                ${isActive ? '✓ Em uso' : '▶ Usar'}
            </button>
            <button class="btn-delete" data-model="${m.name}">🗑️</button>
        </div>`;

    card.querySelector('.btn-use').addEventListener('click', () => {
        document.querySelectorAll('.btn-use').forEach(b => {
            b.classList.remove('active-model');
            b.textContent = '▶ Usar';
        });
        const btn = card.querySelector('.btn-use');
        btn.classList.add('active-model');
        btn.textContent = '✓ Em uso';
        pendingOllamaModel = m.name;
        pendingProvider = 'ollama';
    });

    card.querySelector('.btn-delete').addEventListener('click', () => deleteModel(m.name, card));
    installedList.appendChild(card);
}

function renderCatalogModel(m) {
    if (m.installed) return; // Já está instalado, não mostra no catálogo

    const card = document.createElement('div');
    card.className = 'model-card';
    card.id = `catalog-${m.name.replace(/[:. ]/g, '-')}`;

    const isRec = m.tags.includes('recomendado');
    card.innerHTML = `
        <div class="model-card-name">${m.label}</div>
        <div class="model-card-meta">
            <span class="model-tag size">${m.size}</span>
            <span class="model-tag speed">${m.speed}</span>
            ${isRec ? '<span class="model-tag rec">⭐ Recomendado</span>' : ''}
        </div>
        <div class="model-card-desc">${m.desc}</div>
        <button class="btn-download" id="dl-${m.name.replace(/[:. ]/g, '-')}">
            ⬇️ Baixar
        </button>
        <div class="progress-wrap hidden" id="prog-${m.name.replace(/[:. ]/g, '-')}">
            <div class="progress-bar-track">
                <div class="progress-bar-fill" id="fill-${m.name.replace(/[:. ]/g, '-')}"></div>
            </div>
            <div class="progress-label">
                <span id="prog-status-${m.name.replace(/[:. ]/g, '-')}">Iniciando...</span>
                <span id="prog-pct-${m.name.replace(/[:. ]/g, '-')}">0%</span>
            </div>
        </div>`;

    card.querySelector('.btn-download').addEventListener('click', () => downloadModel(m.name));
    catalogList.appendChild(card);
}

// ── Download de modelo ────────────────────────────────────
function downloadModel(modelName) {
    const safeId = modelName.replace(/[:. ]/g, '-');
    const dlBtn = document.getElementById(`dl-${safeId}`);
    const progWrap = document.getElementById(`prog-${safeId}`);
    const fill = document.getElementById(`fill-${safeId}`);
    const progStat = document.getElementById(`prog-status-${safeId}`);
    const progPct = document.getElementById(`prog-pct-${safeId}`);

    if (!dlBtn) return;

    dlBtn.disabled = true;
    dlBtn.textContent = '⏳ Iniciando...';
    progWrap.classList.remove('hidden');

    const es = new EventSource(`/api/models/pull?model=${encodeURIComponent(modelName)}`);

    es.onmessage = (event) => {
        const data = JSON.parse(event.data);

        progStat.textContent = data.status;
        progPct.textContent = data.percent + '%';
        fill.style.width = data.percent + '%';

        if (data.total_gb > 0) {
            progStat.textContent = `${data.status} (${data.completed_gb}/${data.total_gb} GB)`;
        }

        if (data.done && !data.error) {
            es.close();
            fill.style.width = '100%';
            progStat.textContent = '✅ Concluído!';
            progPct.textContent = '100%';
            playSound('success');

            // Recarrega a lista após 1.5s
            setTimeout(() => loadOllamaModels(), 1500);
        }

        if (data.error) {
            es.close();
            fill.style.background = '#ff5252';
            progStat.textContent = data.status;
            dlBtn.disabled = false;
            dlBtn.textContent = '⬇️ Tentar novamente';
        }
    };

    es.onerror = () => {
        es.close();
        progStat.textContent = 'Erro de conexão';
        dlBtn.disabled = false;
        dlBtn.textContent = '⬇️ Tentar novamente';
    };
}

// ── Deletar modelo ────────────────────────────────────────
async function deleteModel(modelName, cardElement) {
    if (!confirm(`Remover "${modelName}"? Isso liberará espaço em disco.`)) return;

    try {
        const res = await fetch('/api/models/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName })
        });
        const data = await res.json();

        if (data.ok) {
            cardElement.style.opacity = '0';
            cardElement.style.transform = 'scale(0.95)';
            cardElement.style.transition = 'all 0.3s';
            setTimeout(() => {
                cardElement.remove();
                loadOllamaModels(); // Recarrega para mostrar no catálogo novamente
            }, 300);

            if (pendingOllamaModel === modelName) pendingOllamaModel = null;
        } else {
            alert(`Erro ao remover: ${data.error}`);
        }
    } catch (e) {
        alert(`Erro: ${e.message}`);
    }
}

// ── Salvar configuração ───────────────────────────────────
async function saveSettings() {
    const payload = { provider: pendingProvider };

    if (pendingProvider === 'groq') {
        if (!pendingGroqModel) {
            alert('Selecione um modelo Groq.');
            return;
        }
        payload.groq_model = pendingGroqModel;
    } else {
        if (!pendingOllamaModel) {
            alert('Selecione um modelo local instalado.');
            return;
        }
        payload.ollama_model = pendingOllamaModel;
    }

    btnSave.disabled = true;
    btnSave.textContent = '⏳ Aplicando...';

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.ok) {
            currentConfig = data.config;
            updateModelBadge(currentConfig);
            closeSettings();
            playSound('saved');
        } else {
            alert(`Erro ao salvar: ${data.error}`);
        }
    } catch (e) {
        alert(`Erro de rede: ${e.message}`);
    } finally {
        btnSave.disabled = false;
        btnSave.textContent = '✓ Aplicar Configuração';
    }
}

// ============================================================
// EVENTOS
// ============================================================
sendBtn.addEventListener('click', () => handleSend());

input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
});

stopBtn.addEventListener('click', async () => {
    try { await fetch('/api/cancel', { method: 'POST' }); } catch (e) { }
});

document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        input.value = chip.dataset.prompt;
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
    });
});

// Settings
btnSettings.addEventListener('click', openSettings);
btnCloseSettings.addEventListener('click', closeSettings);
settingsOverlay.addEventListener('click', closeSettings);
btnCloud.addEventListener('click', () => switchTab('groq'));
btnLocal.addEventListener('click', () => switchTab('ollama'));
btnSave.addEventListener('click', saveSettings);

window.addEventListener('focus', () => { if (!isProcessing) input.focus(); });

// ============================================================
// START
// ============================================================
init();