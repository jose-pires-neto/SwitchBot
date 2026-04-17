const input = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const timeline = document.getElementById('timeline');
const statusDot = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');
const stopBar = document.getElementById('stopBar');
const stopBtn = document.getElementById('stopBtn');

let isProcessing = false;
let currentExecutingCard = null;

// ======================== SSE (REAL-TIME FROM SERVER) ========================
const evtSource = new EventSource('/api/events');

evtSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'ping') return; // heartbeat, ignorar
    
    if (data.type === 'feedback') {
        const { msg_type, text } = data;
        
        if (msg_type === 'thought') {
            setStatus('thinking', 'Pensando...');
            timeline.querySelectorAll('.card-thought.active').forEach(t => t.classList.remove('active'));
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
    
    if (data.type === 'response') {
        handleResponse(data.text);
    }
};

evtSource.onerror = function() {
    setStatus('error', 'Desconectado');
    setTimeout(() => setStatus('', 'Reconectando...'), 2000);
};

// ======================== AUDIO ENGINE ========================
function playSound(type) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        switch(type) {
            case 'success':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(523, ctx.currentTime);
                osc.frequency.setValueAtTime(659, ctx.currentTime + 0.1);
                osc.frequency.setValueAtTime(784, ctx.currentTime + 0.2);
                gain.gain.setValueAtTime(0.12, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.45);
                break;

            case 'error':
                osc.type = 'square';
                osc.frequency.setValueAtTime(330, ctx.currentTime);
                osc.frequency.setValueAtTime(220, ctx.currentTime + 0.15);
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.3);
                break;

            case 'cancel':
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(440, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.2);
                gain.gain.setValueAtTime(0.1, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.25);
                break;

            case 'send':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(1200, ctx.currentTime);
                gain.gain.setValueAtTime(0.06, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.08);
                break;
        }
    } catch(e) {}
}

// ======================== STATUS ========================
function setStatus(state, label) {
    statusDot.className = 'status-dot ' + state;
    statusLabel.textContent = label;
}

// ======================== CARDS ========================
function clearWelcome() {
    const welcome = timeline.querySelector('.welcome-msg');
    if (welcome) {
        welcome.style.transition = 'opacity 0.3s, transform 0.3s';
        welcome.style.opacity = '0';
        welcome.style.transform = 'scale(0.95)';
        setTimeout(() => welcome.remove(), 300);
    }
}

function createCard(type, content) {
    clearWelcome();
    const card = document.createElement('div');
    
    switch(type) {
        case 'user':
            card.className = 'card card-user';
            card.textContent = content;
            break;
            
        case 'thought':
            card.className = 'card card-thought active';
            card.innerHTML = `
                <div class="card-header"><span class="card-icon">💭</span> Pensamento</div>
                <div class="card-body">${escapeHtml(content)}</div>
            `;
            break;
            
        case 'executing':
            card.className = 'card card-executing';
            card.innerHTML = `
                <div class="spinner-sm"></div>
                <div>
                    <div class="card-header"><span class="card-icon">⚙️</span> Executando</div>
                    <div class="card-body">${escapeHtml(content)}</div>
                </div>
            `;
            currentExecutingCard = card;
            break;
            
        case 'result':
            card.className = 'card card-result';
            card.innerHTML = `
                <div class="card-header"><span class="card-icon">✅</span> Resultado</div>
                <div class="card-body"><span class="typing-text"></span><span class="typing-cursor"></span></div>
            `;
            timeline.appendChild(card);
            timeline.scrollTop = timeline.scrollHeight;
            typeText(card.querySelector('.typing-text'), content, card.querySelector('.typing-cursor'));
            return card;
            
        case 'error':
            card.className = 'card card-error';
            card.innerHTML = `
                <div class="card-header"><span class="card-icon">❌</span> Erro</div>
                <div class="card-body">${formatResponse(content)}</div>
            `;
            break;

        case 'cancelled':
            card.className = 'card card-cancelled';
            card.innerHTML = `
                <div class="card-header"><span class="card-icon">⏹️</span> Cancelada</div>
                <div class="card-body">Tarefa interrompida pelo usuário.</div>
            `;
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

// ======================== TYPING EFFECT ========================
function typeText(element, text, cursor) {
    const formatted = formatResponse(text);
    const speed = text.length > 200 ? 5 : text.length > 80 ? 12 : 20;
    
    if (text.length > 500) {
        element.innerHTML = formatted;
        if (cursor) cursor.remove();
        return;
    }
    
    let i = 0;
    function type() {
        if (i < formatted.length) {
            if (formatted[i] === '<') {
                const closeTag = formatted.indexOf('>', i);
                if (closeTag !== -1) {
                    element.innerHTML += formatted.substring(i, closeTag + 1);
                    i = closeTag + 1;
                } else {
                    element.innerHTML += formatted[i];
                    i++;
                }
            } else {
                element.innerHTML += formatted[i];
                i++;
            }
            timeline.scrollTop = timeline.scrollHeight;
            setTimeout(type, speed);
        } else {
            if (cursor) cursor.remove();
        }
    }
    type();
}

// ======================== HELPERS ========================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatResponse(text) {
    return escapeHtml(text).replace(/\\n/g, '<br>').replace(/\n/g, '<br>');
}

// ======================== RESPONSE HANDLER ========================
function handleResponse(text) {
    removeExecutingCard();
    hideStopBar();
    
    timeline.querySelectorAll('.card-thought.active').forEach(t => t.classList.remove('active'));
    
    const isCancelled = text.includes('cancelada') || text.includes('Cancelada');
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

// ======================== STOP BAR ========================
function showStopBar() { stopBar.classList.remove('hidden'); }
function hideStopBar() { stopBar.classList.add('hidden'); }

// ======================== SEND ========================
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

// ======================== EVENTS ========================
sendBtn.addEventListener('click', () => handleSend());

input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

// Quick Actions
document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        const prompt = chip.dataset.prompt;
        input.value = prompt;
        input.focus();
        input.setSelectionRange(prompt.length, prompt.length);
    });
});

// STOP button
stopBtn.addEventListener('click', async () => {
    try {
        await fetch('/api/cancel', { method: 'POST' });
    } catch(e) {}
});

// Auto-focus
window.addEventListener('focus', () => {
    if (!isProcessing) input.focus();
});
