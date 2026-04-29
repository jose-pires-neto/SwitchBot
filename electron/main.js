/**
 * main.js — SwitchBot Electron Desktop Pet
 *
 * Janela transparente, sem frame, sempre no topo.
 * Arraste pelo mascote para mover.
 * Redimensione pelas bordas da janela.
 * Alt+Space → mostra/oculta o input de texto
 * Alt+H     → oculta tudo (mascote some)
 */

const { app, BrowserWindow, globalShortcut, ipcMain, screen } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// Flags obrigatórias para transparência real no Windows
app.commandLine.appendSwitch('enable-transparent-visuals');
app.commandLine.appendSwitch('disable-gpu-compositing');

const FLASK_URL  = 'http://localhost:5789';
const WIN_W      = 400;
const WIN_H      = 500;

let win;
let pythonProcess = null;

function startPythonBackend() {
    const isPackaged = app.isPackaged;
    
    let pythonPath;
    let args = [];

    if (isPackaged) {
        // No Electron empacotado, recursos extras ficam na pasta 'resources'
        pythonPath = path.join(process.resourcesPath, 'backend.exe');
    } else {
        // Modo desenvolvimento: roda o script direto
        pythonPath = 'python';
        args = [path.join(__dirname, '..', 'main.py')];
    }

    console.log(`[Electron] Iniciando backend: ${pythonPath} ${args.join(' ')}`);

    pythonProcess = spawn(pythonPath, args, {
        cwd: isPackaged ? process.resourcesPath : path.join(__dirname, '..'),
        shell: true
    });

    pythonProcess.stdout.on('data', (data) => console.log(`[Python] ${data}`));
    pythonProcess.stderr.on('data', (data) => console.error(`[Python Error] ${data}`));

    pythonProcess.on('close', (code) => {
        console.log(`[Electron] Backend encerrado com código ${code}`);
        pythonProcess = null;
    });
}

function createWindow() {
    const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;

    win = new BrowserWindow({
        width:  WIN_W,
        height: WIN_H,
        x: sw - WIN_W - 30,
        y: Math.round((sh - WIN_H) / 2),

        // Transparência total — sem frame, sem sombra, sem fundo
        transparent:              true,
        frame:                    false,
        backgroundColor:          '#00000000',
        hasShadow:                false,
        // Começa oculto para evitar flash do background antes do conteúdo
        show:                     false,
        paintWhenInitiallyHidden: false,

        alwaysOnTop: true,
        resizable:   true,
        movable:     true,
        skipTaskbar: false,

        webPreferences: {
            preload:          path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration:  false,
        }
    });

    win.setAlwaysOnTop(true, 'screen-saver', 1);

    // Só exibe depois que a página estiver pintada — elimina flash
    win.once('ready-to-show', () => {
        win.setBackgroundColor('#00000000');
        win.show();
    });

    win.loadURL(FLASK_URL);

    win.webContents.on('did-fail-load', () => {
        setTimeout(() => win.loadURL(FLASK_URL), 1000);
    });

    // Envia a posição global do mouse para o mascote
    setInterval(() => {
        if (win && win.isVisible()) {
            const point = screen.getCursorScreenPoint();
            const bounds = win.getBounds();
            // Converte para coordenadas relativas à janela do mascote
            const relativeX = point.x - bounds.x;
            const relativeY = point.y - bounds.y;
            win.webContents.send('global-mouse-move', { 
                x: relativeX, 
                y: relativeY,
                windowWidth: bounds.width,
                windowHeight: bounds.height
            });
        }
    }, 30); // ~33fps para suavidade
}


// ── IPC handlers (chamados pelo renderer via preload) ──────────────────
ipcMain.on('hide-window', () => win && win.hide());

ipcMain.on('set-ignore-mouse', (_e, ignore) => {
    if (win) win.setIgnoreMouseEvents(ignore, { forward: true });
});

// ── App lifecycle ──────────────────────────────────────────────────────
app.whenReady().then(() => {
    // Inicia o backend Python
    startPythonBackend();

    // Aguarda o Flask subir antes de abrir a janela
    setTimeout(createWindow, 2500);

    // Alt+Space → toggle input de texto
    globalShortcut.register('Alt+Space', () => {
        if (!win) return;
        if (!win.isVisible()) win.show();
        win.webContents.send('toggle-input');
    });

    // Alt+H → ocultar tudo
    globalShortcut.register('Alt+H', () => {
        if (win) win.hide();
    });

    // Alt+M → mostrar (se oculto)
    globalShortcut.register('Alt+M', () => {
        if (win) { win.show(); win.focus(); }
    });
});

app.on('will-quit', () => {
    globalShortcut.unregisterAll();
    if (pythonProcess) {
        console.log('[Electron] Finalizando backend Python...');
        pythonProcess.kill();
    }
});
app.on('window-all-closed', () => app.quit());
