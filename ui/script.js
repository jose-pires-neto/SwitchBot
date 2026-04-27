// ============================================================
// script.js — SwitchBot UI (Mascot & Chat Modes)
// ============================================================

const input = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const stopBar = document.getElementById('stopBar');
const stopBtn = document.getElementById('stopBtn');

// Visual Modes
const bodyElement = document.body;
const btnToggleMode = document.getElementById('btnToggleMode');
const mascotView = document.getElementById('mascotView');
const chatView = document.getElementById('chatView');

// Mascot DOM
const mascotWrapper = document.getElementById('mascotWrapper');
const mBtnChat = document.getElementById('mBtnChat');
const mascotSpeech = document.getElementById('mascotSpeechBubble');
const mascotText = document.getElementById('mascotText');
const mascotTyping = document.getElementById('mascotTyping');

// Chat DOM
const timeline = document.getElementById('timeline');
const statusDot = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');
const modelBadge = document.getElementById('modelBadge');

// Settings DOM
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

let isProcessing = false;
let currentExecutingCard = null;
let currentMode = 'mascot';
let mascotSpeechTimeout = null;

// ── Detecção de modo Electron (Desktop Pet) ──────────────────────────
const IS_ELECTRON = !!window.electronAPI;
if (IS_ELECTRON) document.body.classList.add('electron-pet-mode');

// Configurações Globais
let pendingProvider = null;
let pendingGroqModel = null;
let pendingOllamaModel = null;
let currentConfig = { provider: 'groq', groq_model: '', ollama_model: null };

// ============================================================
// INICIALIZAÇÃO
// ============================================================
async function init() {
    await loadCurrentConfig();
    applyMode();
    connectSSE();
    setupElectron();
}

// ── Integração Electron ───────────────────────────────────────────────
function setupElectron() {
    if (!IS_ELECTRON) return;

    // Input começa oculto — aparece via Alt+Space
    const inputArea = document.getElementById('inputArea');
    inputArea.style.display = 'none';

    // Alt+Space → toggle input (enviado pelo main.js via IPC)
    window.electronAPI.onToggleInput(() => {
        const visible = inputArea.style.display !== 'none';
        inputArea.style.display = visible ? 'none' : 'flex';
        if (!visible) input.focus();
    });

    // Botão ✕ oculta a janela
    const btnHide = document.getElementById('btnHidePet');
    if (btnHide) btnHide.addEventListener('click', () => window.electronAPI.hideWindow());

    // Esconde o botão "Abrir Chat" — em pet mode o chat fica oculto
    if (mBtnChat) mBtnChat.style.display = 'none';
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
    if (!modelBadge) return;
    if (config.provider === 'groq') {
        const short = (config.groq_model || '').replace('llama-', 'L').replace('-versatile', '').replace('-instant', '');
        modelBadge.textContent = '☁️ ' + short;
    } else {
        modelBadge.textContent = '🖥️ ' + (config.ollama_model || 'local');
    }
}

// ============================================================
// MUDANÇA DE MODOS E POSIÇÕES
// ============================================================
function applyMode() {
    const canvas3d = document.getElementById('canvas-container');
    const bgGlow   = document.getElementById('bg-glow');

    if (currentMode === 'mascot') {
        bodyElement.classList.add('mascot-active');
        mascotView.classList.remove('hidden');
        chatView.classList.add('hidden');
        document.getElementById('inputArea').style.display = 'flex';
        if (canvas3d) canvas3d.style.display = 'block';
        if (bgGlow)   bgGlow.style.display   = 'block';
    } else {
        bodyElement.classList.remove('mascot-active');
        mascotView.classList.add('hidden');
        chatView.classList.remove('hidden');
        if (canvas3d) canvas3d.style.display = 'none';
        if (bgGlow)   bgGlow.style.display   = 'none';

        setTimeout(() => {
            timeline.scrollTop = timeline.scrollHeight;
            const lastCard = timeline.lastElementChild;
            if (lastCard) lastCard.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }, 50);
    }
}

btnToggleMode.addEventListener('click', () => {
    currentMode = currentMode === 'mascot' ? 'chat' : 'mascot';
    applyMode();
});

mBtnChat.addEventListener('click', () => {
    currentMode = 'chat';
    applyMode();
});

// Posicionamento do mascote gerenciado pela engine 3D (basePosX)

// ============================================================
// LÓGICA DO MASCOTE (ESTADOS → ENGINE 3D)
// ============================================================
function setMascotState(state, text = '') {
    // Mapeia estado → emoção 3D
    if (window.botEngine) {
        const { setEmotion, engineState } = window.botEngine;
        switch (state) {
            case 'idle':
                engineState.isThinking = false;
                setEmotion('NEUTRAL', 1.0);
                break;
            case 'thinking':
                engineState.isThinking = true;
                setEmotion('NEUTRAL', 1.0);
                break;
            case 'executing':
                engineState.isThinking = true;
                setEmotion('SURPRISE', 0.6);
                break;
            case 'success':
                engineState.isThinking = false;
                setEmotion('JOY', 0.9);
                setTimeout(() => setEmotion('NEUTRAL', 1.0), 3000);
                break;
            case 'error':
                engineState.isThinking = false;
                setEmotion('SAD', 0.8);
                setTimeout(() => setEmotion('NEUTRAL', 1.0), 3000);
                break;
        }
    }

    clearTimeout(mascotSpeechTimeout);

    if (text === '...typing...') {
        mascotSpeech.classList.remove('hidden');
        mascotText.classList.add('hidden');
        mascotTyping.classList.remove('hidden');
    } else if (text) {
        mascotSpeech.classList.remove('hidden');
        mascotTyping.classList.add('hidden');
        mascotText.classList.remove('hidden');

        // Exibe o texto completo, sem corte
        mascotText.textContent = text.replace(/<[^>]*>?/gm, '');

        if (state === 'success' || state === 'error') {
            mascotSpeechTimeout = setTimeout(() => {
                mascotSpeech.classList.add('hidden');
            }, 6000);
        }
    } else {
        mascotSpeech.classList.add('hidden');
    }
}

// ============================================================
// SSE E FEEDBACKS
// ============================================================
function connectSSE() {
    const es = new EventSource('/api/events');
    es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'ping') return;
        if (data.type === 'feedback') handleFeedback(data.msg_type, data.text);
        else if (data.type === 'response') handleResponse(data.text);
    };
    es.onerror = () => {
        statusLabel.textContent = 'Desconectado';
        setMascotState('error', 'Ops, sem conexão!');
        setTimeout(() => { connectSSE(); }, 3000);
    };
}

function handleFeedback(msg_type, text) {
    if (msg_type === 'thought') {
        setMascotState('thinking', '...typing...');
        timeline.querySelectorAll('.card-thought.active').forEach(c => c.classList.remove('active'));
        createCard('thought', text);
    } else if (msg_type === 'executing' || msg_type === 'system') {
        setMascotState('executing', `⚙️ Executando tarefa...`);
        removeExecutingCard();
        createCard('executing', text);
    }
}

function handleResponse(text) {
    removeExecutingCard();
    stopBar.classList.add('hidden');
    timeline.querySelectorAll('.card-thought.active').forEach(c => c.classList.remove('active'));

    if (text.includes('cancelada') || text.includes('⏹️')) {
        createCard('cancelled', text);
        setMascotState('idle', 'Parei!');
    } else if (text.startsWith('Erro') || text.includes('⚠️')) {
        createCard('error', text);
        setMascotState('error', 'Xii, deu erro na tarefa.');
    } else {
        createCard('result', text);
        setMascotState('success', text);
    }

    isProcessing = false;
    sendBtn.disabled = false;
    input.focus();
}

// ============================================================
// CARDS NO MODO CHAT
// ============================================================
function createCard(type, content) {
    const w = document.getElementById('welcomeMsg');
    if (w) w.style.display = 'none';

    const card = document.createElement('div');
    switch (type) {
        case 'user':
            card.className = 'card card-user';
            card.textContent = content;
            break;
        case 'thought':
            card.className = 'card card-thought active';
            card.innerHTML = `<div class="card-header"><span>💭</span> Pensando...</div><div>${escapeHtml(content)}</div>`;
            break;
        case 'executing':
            card.className = 'card card-executing';
            card.innerHTML = `<div class="spinner-sm"></div><div><div class="card-header"><span>⚙️</span> Executando</div><div>${escapeHtml(content)}</div></div>`;
            currentExecutingCard = card;
            break;
        case 'result':
            card.className = 'card card-result';
            card.innerHTML = `<div class="card-header"><span>✅</span> Resultado</div><div><span class="typing-text"></span><span class="typing-cursor"></span></div>`;
            timeline.appendChild(card);

            // Inicia o efeito de digitação
            typeText(card.querySelector('.typing-text'), content, card.querySelector('.typing-cursor'));
            return card;
        case 'error':
            card.className = 'card card-error';
            card.innerHTML = `<div class="card-header"><span>❌</span> Erro</div><div>${formatResponse(content)}</div>`;
            break;
        case 'cancelled':
            card.className = 'card card-cancelled';
            card.innerHTML = `<div class="card-header"><span>⏹️</span> Cancelada</div><div>Tarefa interrompida.</div>`;
            break;
    }

    timeline.appendChild(card);

    // Força o scroll sempre que criar um card normal
    setTimeout(() => {
        timeline.scrollTop = timeline.scrollHeight;
        card.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, 50);

    return card;
}

function removeExecutingCard() {
    if (currentExecutingCard) { currentExecutingCard.remove(); currentExecutingCard = null; }
}

function formatResponse(t) {
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true });
        return marked.parse(t);
    }
    return escapeHtml(t).replace(/\\n/g, '<br>').replace(/\n/g, '<br>');
}

function escapeHtml(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
}

// ============================================================
// TYPING EFFECT (Traz de volta a animação + auto scroll)
// ============================================================
function typeText(element, text, cursor) {
    const formatted = formatResponse(text);
    // Se o texto for gigante, joga na tela direto pra não demorar
    if (text.length > 800) {
        element.innerHTML = formatted;
        cursor?.remove();
        timeline.scrollTop = timeline.scrollHeight;
        return;
    }

    const speed = text.length > 200 ? 5 : text.length > 80 ? 10 : 20;
    let i = 0;

    function type() {
        if (i < formatted.length) {
            if (formatted[i] === '<') {
                const end = formatted.indexOf('>', i);
                if (end !== -1) {
                    element.innerHTML += formatted.substring(i, end + 1);
                    i = end + 1;
                } else {
                    element.innerHTML += formatted[i++];
                }
            } else {
                element.innerHTML += formatted[i++];
            }
            // Força o scroll para baixo a cada letra
            timeline.scrollTop = timeline.scrollHeight;
            element.scrollIntoView({ block: 'end' });
            setTimeout(type, speed);
        } else {
            cursor?.remove();
        }
    }
    type();
}

// ============================================================
// ENVIAR
// ============================================================
async function handleSend(promptText) {
    const val = (promptText || input.value).trim();
    if (!val || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;
    input.value = '';

    createCard('user', val);
    setMascotState('thinking', '...typing...');
    stopBar.classList.remove('hidden');

    try {
        await fetch('/api/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: val }) });
    } catch (e) {
        stopBar.classList.add('hidden');
        setMascotState('error', 'Falha ao contatar o cérebro!');
        createCard('error', e.message);
        isProcessing = false; sendBtn.disabled = false;
    }
}

sendBtn.addEventListener('click', () => handleSend());
input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } });
stopBtn.addEventListener('click', async () => { try { await fetch('/api/cancel', { method: 'POST' }); } catch (e) { } });

document.querySelectorAll('.chip').forEach(chip => { chip.addEventListener('click', () => { input.value = chip.dataset.prompt; input.focus(); }); });

// ============================================================
// PAINEL DE CONFIGURAÇÕES (CORRIGIDO)
// ============================================================

function openSettings() {
    settingsPanel.classList.remove('hidden');
    settingsOverlay.classList.remove('hidden');

    // Copia config atual para os pendentes ao abrir
    pendingProvider = currentConfig.provider;
    pendingGroqModel = currentConfig.groq_model;
    pendingOllamaModel = currentConfig.ollama_model;

    switchTab(pendingProvider);
}

function closeSettings() {
    settingsPanel.classList.add('hidden');
    settingsOverlay.classList.add('hidden');
}

function switchTab(provider) {
    pendingProvider = provider;

    // Atualiza botões
    btnCloud.classList.toggle('active', provider === 'groq');
    btnLocal.classList.toggle('active', provider === 'ollama');

    // Atualiza seções visíveis
    sectionCloud.classList.toggle('hidden', provider !== 'groq');
    sectionLocal.classList.toggle('hidden', provider !== 'ollama');

    // Carrega dados se necessário
    if (provider === 'groq') {
        loadGroqModels();
    } else {
        loadOllamaModels();
    }
}

// Lógica Groq
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
            // Marca o selecionado se for o modelo pendente
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

// Lógica Ollama
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
                    <a class="install-link" href="https://ollama.com/download" target="_blank">⬇️ Baixar Ollama para Windows</a><br>
                    <span style="color:#888">Após instalar, reinicie o SwitchBot.</span>
                </div>`;
            return;
        }

        ollamaStatus.className = 'ollama-status online';
        ollamaStatus.innerHTML = '✅ Ollama Online e pronto';

        if (data.installed && data.installed.length > 0) {
            installedSection.classList.remove('hidden');
            installedList.innerHTML = '';
            data.installed.forEach(m => renderInstalledModel(m));
        }

        if (data.catalog) {
            catalogSection.classList.remove('hidden');
            catalogList.innerHTML = '';
            data.catalog.forEach(m => renderCatalogModel(m));
        }
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
        <div class="model-card-actions" style="display:flex;gap:6px;margin-top:8px;">
            <button class="btn-use${isActive ? ' active-model' : ''}" data-model="${m.name}" style="flex:1;padding:5px;border-radius:6px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.3);color:#80e6b0;cursor:pointer;">
                ${isActive ? '✓ Em uso' : '▶ Usar'}
            </button>
            <button class="btn-delete" data-model="${m.name}" style="padding:5px 10px;border-radius:6px;background:transparent;border:1px solid rgba(255,82,82,0.2);color:#c06060;cursor:pointer;">🗑️</button>
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
    if (m.installed) return;

    const safeId = m.name.replace(/[:. ]/g, '-');
    const card = document.createElement('div');
    card.className = 'model-card';
    card.id = `catalog-${safeId}`;
    const isRec = m.tags && m.tags.includes('recomendado');

    card.innerHTML = `
        <div class="model-card-name">${m.label}</div>
        <div class="model-card-meta">
            <span class="model-tag size">${m.size}</span>
            <span class="model-tag speed">${m.speed}</span>
            ${isRec ? '<span class="model-tag rec">⭐ Recomendado</span>' : ''}
        </div>
        <div class="model-card-desc" style="font-size:11px;color:#777;margin-top:4px;">${m.desc}</div>
        <button class="btn-download" id="dl-${safeId}" style="width:100%;padding:6px;border-radius:6px;background:rgba(68,138,255,0.1);border:1px solid rgba(68,138,255,0.3);color:#82b1ff;cursor:pointer;margin-top:8px;">⬇️ Baixar</button>
        <div class="progress-wrap hidden" id="prog-${safeId}" style="margin-top:8px;">
            <div class="progress-bar-track" style="height:5px;background:rgba(255,255,255,0.1);border-radius:10px;">
                <div class="progress-bar-fill" id="fill-${safeId}" style="height:100%;background:#448aff;width:0%;border-radius:10px;"></div>
            </div>
            <div class="progress-label" style="display:flex;justify-content:space-between;font-size:10px;color:#888;">
                <span id="prog-status-${safeId}">Iniciando...</span>
                <span id="prog-pct-${safeId}">0%</span>
            </div>
        </div>`;

    card.querySelector('.btn-download').addEventListener('click', () => downloadModel(m.name));
    catalogList.appendChild(card);
}

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
            setTimeout(() => {
                cardElement.remove();
                loadOllamaModels();
            }, 300);
            if (pendingOllamaModel === modelName) pendingOllamaModel = null;
        } else {
            alert(`Erro ao remover: ${data.error}`);
        }
    } catch (e) {
        alert(`Erro: ${e.message}`);
    }
}

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

// Listeners de Configuração
btnSettings.addEventListener('click', openSettings);
btnCloseSettings.addEventListener('click', closeSettings);
settingsOverlay.addEventListener('click', closeSettings);
btnCloud.addEventListener('click', () => switchTab('groq'));
btnLocal.addEventListener('click', () => switchTab('ollama'));
btnSave.addEventListener('click', saveSettings);

// ============================================================
// INICIA O APP
// ============================================================
init();