"""
main.py — Servidor Flask do SwitchBot

Rotas:
  / e /ui/*           → Serve os arquivos da UI
  /api/send           → Envia prompt ao JarvisCore
  /api/cancel         → Cancela tarefa em andamento
  /api/events         → SSE: feedback em tempo real
  /api/settings       → GET/POST configuração do modelo
  /api/models/groq    → Lista modelos disponíveis no Groq
  /api/models/ollama  → Status + instalados + catálogo
  /api/models/pull    → SSE: download de modelo Ollama
  /api/models/delete  → Remove modelo Ollama
"""

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
import model_manager

# ======================== FLASK + CORE ========================
app = Flask(__name__)
core = JarvisCore()
sse_queue = queue.Queue()

UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui')

@app.route('/')
def index():
    return send_from_directory(UI_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(UI_DIR, path)

# ======================== CHAT ========================
@app.route('/api/send', methods=['POST'])
def send_prompt():
    data = request.get_json()
    user_text = data.get('text', '').strip()
    if not user_text:
        return jsonify({"ok": False, "error": "Texto vazio"}), 400

    def progress(msg_type, text):
        sse_queue.put(json.dumps(
            {"type": "feedback", "msg_type": msg_type, "text": text},
            ensure_ascii=False
        ))

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
    """SSE: stream de feedback em tempo real para a UI."""
    def generate():
        while True:
            try:
                data = sse_queue.get(timeout=25)
                yield f"data: {data}\n\n"
            except queue.Empty:
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

# ======================== SETTINGS ========================
@app.route('/api/settings', methods=['GET'])
def get_settings():
    config = model_manager.load_config()
    return jsonify(config)

@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.get_json()
    config = model_manager.load_config()
    
    if 'provider' in data:
        config['provider'] = data['provider']
    if 'groq_model' in data:
        config['groq_model'] = data['groq_model']
    if 'ollama_model' in data:
        config['ollama_model'] = data['ollama_model']
    
    model_manager.save_config(config)
    
    # Recarrega o core com o novo provedor sem reiniciar
    try:
        core.reload_config()
        return jsonify({"ok": True, "config": config})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ======================== MODELOS GROQ ========================
@app.route('/api/models/groq', methods=['GET'])
def list_groq_models():
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return jsonify({"error": "GROQ_API_KEY não configurada"}), 500

    models = model_manager.get_groq_models(api_key)
    return jsonify({"models": models})

# ======================== MODELOS OLLAMA ========================
@app.route('/api/models/ollama', methods=['GET'])
def list_ollama_models():
    status = model_manager.get_ollama_full_status()
    return jsonify(status)

@app.route('/api/models/pull')
def pull_model():
    """SSE: stream de progresso do download de um modelo Ollama."""
    model_name = request.args.get('model', '')
    if not model_name:
        return jsonify({"error": "Parâmetro 'model' obrigatório"}), 400

    def generate():
        for progress in model_manager.pull_model_stream(model_name):
            yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
        # Confirma fim do stream
        yield f"data: {json.dumps({'done': True, 'status': 'success'})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/api/models/delete', methods=['POST'])
def delete_model():
    data = request.get_json()
    model_name = data.get('model', '')
    if not model_name:
        return jsonify({"error": "Parâmetro 'model' obrigatório"}), 400

    result = model_manager.delete_ollama_model(model_name)
    return jsonify(result)

# ======================== WINDOW CONTROL ========================
WINDOW_TITLE = "Jarvis Command Center"

def find_window():
    return ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)

def toggle_overlay():
    hwnd = find_window()
    if hwnd:
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            ctypes.windll.user32.ShowWindow(hwnd, 0)   # SW_HIDE
        else:
            ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)

def set_always_on_top(hwnd):
    HWND_TOPMOST = ctypes.wintypes.HWND(-1)
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

def open_app_window(port):
    url = f'http://localhost:{port}'
    edge_paths = [
        os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
        os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
    ]
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
        subprocess.Popen([browser, f'--app={url}', '--window-size=700,580', '--disable-extensions'])
    else:
        import webbrowser
        webbrowser.open(url)

    def apply_on_top():
        for _ in range(30):
            time.sleep(0.5)
            hwnd = find_window()
            if hwnd:
                set_always_on_top(hwnd)
                break

    threading.Thread(target=apply_on_top, daemon=True).start()

# ======================== MAIN ========================
if __name__ == '__main__':
    PORT = 5789
    config = model_manager.load_config()

    print("=" * 52)
    print("  🤖 SWITCHBOT — Command Center")
    print("=" * 52)
    print(f"  Provedor : {config['provider'].upper()}")
    if config['provider'] == 'groq':
        print(f"  Modelo   : {config['groq_model']}")
    else:
        print(f"  Modelo   : {config.get('ollama_model', 'não configurado')}")
    print(f"  UI       : http://localhost:{PORT}")
    print("  Atalho   : Alt+O (mostrar/esconder)")
    print("=" * 52)

    keyboard.add_hotkey('alt+o', toggle_overlay)
    threading.Timer(1.5, lambda: open_app_window(PORT)).start()

    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)