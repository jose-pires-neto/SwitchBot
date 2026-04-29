"""
model_manager.py — Gerencia provedores de IA (Groq Cloud + Ollama Local)
"""

import os
import sys
import json
import requests

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

DEFAULT_CONFIG = {
    "provider": "groq",
    "groq_model": "llama-3.3-70b-versatile",
    "ollama_model": None
}

# Catálogo curado para dar nomes bonitos e descrições na UI aos modelos Groq
GROQ_CATALOG_INFO = {
    "llama-3.3-70b-versatile": {
        "label": "Llama 3.3 · 70B",
        "desc": "Modelo extremamente capaz e inteligente. Ideal como cérebro principal do agente.",
        "tags": ["recomendado", "avançado"]
    },
    "llama-3.1-8b-instant": {
        "label": "Llama 3.1 · 8B",
        "desc": "Muito rápido. Bom para respostas curtas, mas pode falhar em automações complexas.",
        "tags": ["rápido"]
    },
    "deepseek-r1-distill-llama-70b": {
        "label": "DeepSeek R1 · 70B",
        "desc": "Focado em raciocínio lógico profundo e criação de código.",
        "tags": ["raciocínio", "código"]
    },
    "mixtral-8x7b-32768": {
        "label": "Mixtral 8x7B",
        "desc": "Poderoso modelo MoE da Mistral. Ótimo contexto longo.",
        "tags": ["contexto amplo"]
    },
    "gemma2-9b-it": {
        "label": "Gemma 2 · 9B",
        "desc": "Modelo leve e eficiente do Google.",
        "tags": ["google"]
    }
}

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(data: dict):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ======================== GROQ ========================

_GROQ_SKIP_PREFIXES = ('whisper', 'distil-whisper', 'playai', 'llama-guard')

def get_groq_models(api_key: str) -> list[dict]:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        result = client.models.list()
        models = []
        for m in result.data:
            mid = m.id.lower()
            if any(mid.startswith(p) for p in _GROQ_SKIP_PREFIXES):
                continue
            
            # Pega infos do catálogo interno se existir
            info = GROQ_CATALOG_INFO.get(m.id, {})
            
            models.append({
                "id": m.id,
                "label": info.get("label", m.id),
                "desc": info.get("desc", "Modelo de linguagem padrão."),
                "tags": info.get("tags", ["128k ctx"]),
                "owned_by": getattr(m, 'owned_by', 'Desconhecido')
            })
            
        models.sort(key=lambda x: (
            '70b' not in x['id'],
            '8b' not in x['id'],
            x['id']
        ))
        return models
    except Exception as e:
        return [{"error": str(e)}]

# ======================== OLLAMA ========================

OLLAMA_BASE = 'http://localhost:11434'

# Catálogo curado de modelos recomendados para download
OLLAMA_CATALOG = [
    {
        "name": "llama3.2:3b",
        "label": "Llama 3.2 · 3B",
        "size": "~2 GB",
        "speed": "⚡ Ultra Rápido",
        "desc": "Leve e eficiente. Ideal para PCs com menos de 8GB de RAM.",
        "tags": ["leve", "rápido"]
    },
    {
        "name": "llama3.2:1b",
        "label": "Llama 3.2 · 1B",
        "size": "~0.9 GB",
        "speed": "⚡⚡ Extremo",
        "desc": "O menor modelo disponível. Hardware muito limitado.",
        "tags": ["mínimo"]
    },
    {
        "name": "llama3.1:8b",
        "label": "Llama 3.1 · 8B",
        "size": "~5 GB",
        "speed": "🚀 Rápido",
        "desc": "Equilíbrio perfeito entre qualidade e velocidade. Recomendado.",
        "tags": ["recomendado", "equilibrado"]
    },
    {
        "name": "mistral:7b",
        "label": "Mistral · 7B",
        "size": "~4.1 GB",
        "speed": "🚀 Rápido",
        "desc": "Excelente para raciocínio e tarefas técnicas em inglês.",
        "tags": ["técnico", "inglês"]
    },
    {
        "name": "qwen2.5-coder:7b",
        "label": "Qwen 2.5 Coder · 7B",
        "size": "~5 GB",
        "speed": "🚀 Rápido",
        "desc": "Especialista em código. Melhor para automação e programação.",
        "tags": ["código", "automação"]
    },
    {
        "name": "phi4:14b",
        "label": "Phi-4 · 14B",
        "size": "~8.9 GB",
        "speed": "🐢 Moderado",
        "desc": "Modelo avançado da Microsoft. Exige GPU ou 16GB+ RAM.",
        "tags": ["avançado", "potente"]
    },
    {
        "name": "gemma2:9b",
        "label": "Gemma 2 · 9B",
        "size": "~5.5 GB",
        "speed": "🚀 Rápido",
        "desc": "Modelo do Google. Bom para tarefas gerais em múltiplos idiomas.",
        "tags": ["google", "multilíngue"]
    },
]

def get_ollama_status() -> dict:
    """Verifica se o Ollama está rodando e acessível."""
    try:
        r = requests.get(f'{OLLAMA_BASE}/api/tags', timeout=2)
        if r.status_code == 200:
            return {"running": True}
    except Exception:
        pass
    return {"running": False}

def get_ollama_installed() -> list[dict]:
    """Retorna lista de modelos instalados no Ollama."""
    try:
        r = requests.get(f'{OLLAMA_BASE}/api/tags', timeout=3)
        if r.status_code == 200:
            models = r.json().get('models', [])
            return [
                {
                    "name": m['name'],
                    # Usa "or 0" para evitar erro se "size" vier como None
                    "size_gb": round((m.get('size') or 0) / (1024**3), 1)
                }
                for m in models
            ]
    except Exception:
        pass
    return []

def pull_model_stream(model_name: str):
    """
    Generator que faz o download de um modelo Ollama via streaming.
    Yields: dict com {status, percent, layer}
    """
    try:
        import ollama
        
        for progress in ollama.pull(model_name, stream=True):
            status = progress.get('status', '')
            
            # Correção principal:
            # Substitui 'None' por '0' caso o Ollama retorne um status vazio
            total = progress.get('total') or 0
            completed = progress.get('completed') or 0
            
            percent = 0
            if total > 0:
                percent = round((completed / total) * 100, 1)
            
            yield {
                "status": status,
                "percent": percent,
                "completed_gb": round(completed / (1024**3), 2),
                "total_gb": round(total / (1024**3), 2),
                "done": status == 'success'
            }
    except Exception as e:
        yield {"status": f"Erro: {str(e)}", "percent": 0, "done": True, "error": True}

def delete_ollama_model(model_name: str) -> dict:
    """Remove um modelo instalado do Ollama."""
    try:
        import ollama
        ollama.delete(model_name)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_ollama_full_status() -> dict:
    """Retorna status completo: running, installed, catalog."""
    status = get_ollama_status()
    installed = get_ollama_installed() if status["running"] else []
    installed_names = {m["name"] for m in installed}
    
    # Marca no catálogo quais já estão instalados
    catalog = []
    for item in OLLAMA_CATALOG:
        entry = item.copy()
        entry["installed"] = item["name"] in installed_names
        catalog.append(entry)
    
    return {
        "running": status["running"],
        "installed": installed,
        "catalog": catalog
    }