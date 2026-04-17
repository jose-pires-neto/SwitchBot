import os
import sys
import json
import queue
import ctypes
import ctypes.wintypes
import threading
import subprocess
import time
from flask import Flask, send_from_directory, request, Response, jsonify
import keyboard
from jarvis_core import JarvisCore

# ======================== FLASK SERVER ========================
app = Flask(__name__)
core = JarvisCore()

# Fila global de eventos SSE (um único usuário local)
sse_queue = queue.Queue()

@app.route('/')
def index():
    ui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui')
    return send_from_directory(ui_dir, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    ui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui')
    return send_from_directory(ui_dir, path)

@app.route('/api/send', methods=['POST'])
def send_prompt():
    data = request.get_json()
    user_text = data.get('text', '')
    
    def progress(msg_type, text):
        sse_queue.put(json.dumps({"type": "feedback", "msg_type": msg_type, "text": text}, ensure_ascii=False))
    
    def process():
        try:
            result = core.process_input(user_text, progress_callback=progress)
            sse_queue.put(json.dumps({"type": "response", "text": result}, ensure_ascii=False))
        except Exception as e:
            sse_queue.put(json.dumps({"type": "response", "text": f"Erro: {str(e)}"}, ensure_ascii=False))
    
    threading.Thread(target=process, daemon=True).start()
    return jsonify({"ok": True})

@app.route('/api/cancel', methods=['POST'])
def cancel_task():
    core.cancel()
    return jsonify({"ok": True})

@app.route('/api/events')
def events():
    """Server-Sent Events stream para feedback em tempo real."""
    def generate():
        while True:
            try:
                data = sse_queue.get(timeout=25)
                yield f"data: {data}\n\n"
            except queue.Empty:
                # Heartbeat para manter a conexão viva
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    
    return Response(
        generate(), 
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

# ======================== WINDOW CONTROL (Win32 API) ========================
WINDOW_TITLE = "Jarvis Command Center"

def find_window():
    """Encontra o handle da janela do Edge em modo app pelo título."""
    return ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)

def toggle_overlay():
    """Alt+O: esconde ou mostra a janela do Jarvis."""
    hwnd = find_window()
    if hwnd:
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
        else:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)

def set_always_on_top(hwnd):
    """Coloca a janela sempre no topo."""
    HWND_TOPMOST = ctypes.wintypes.HWND(-1)
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

def open_app_window(port):
    """Abre Edge ou Chrome em modo --app (frameless, sem barra de URL)."""
    url = f'http://localhost:{port}'
    
    # Tenta Edge primeiro (vem com Windows 10/11)
    edge_paths = [
        os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
        os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
    ]
    
    # Fallback para Chrome
    chrome_paths = [
        os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
    ]
    
    browser = None
    for p in edge_paths + chrome_paths:
        if os.path.exists(p):
            browser = p
            break
    
    if browser:
        subprocess.Popen([browser, f'--app={url}', '--window-size=650,520', '--disable-extensions'])
    else:
        # Último recurso: abre no navegador padrão
        import webbrowser
        webbrowser.open(url)
    
    # Espera a janela aparecer e aplica always-on-top
    def apply_on_top():
        for _ in range(30):  # Tenta por 15 segundos
            time.sleep(0.5)
            hwnd = find_window()
            if hwnd:
                set_always_on_top(hwnd)
                print("✅ Janela detectada e fixada como always-on-top.")
                break
    
    threading.Thread(target=apply_on_top, daemon=True).start()

# ======================== MAIN ========================
if __name__ == '__main__':
    PORT = 5789
    
    print("=" * 50)
    print("  🤖 JARVIS COMMAND CENTER")
    print("=" * 50)
    print(f"  Servidor local: http://localhost:{PORT}")
    print("  Atalho global:  Alt+O (mostrar/esconder)")
    print("  Para encerrar:  Ctrl+C no terminal")
    print("=" * 50)
    
    # Registra hotkey global
    keyboard.add_hotkey('alt+o', toggle_overlay)
    
    # Abre a janela do navegador em modo app após o servidor subir
    threading.Timer(1.5, lambda: open_app_window(PORT)).start()
    
    # Inicia o Flask (sem logs poluindo o terminal)
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)