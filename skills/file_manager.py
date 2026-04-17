"""
Gerencia arquivos e pastas: ler, escrever, mover, copiar, listar, deletar e processar CSVs.
Suporta TXT, MD, JSON, CSV, LOG, PY e outros arquivos de texto.
OBRIGATÓRIO: Fornecer a key 'operation' dentro de 'args'.

Operações disponíveis:
  read        → lê um arquivo   | args: path
  write       → escreve arquivo | args: path, content, mode (w|a, padrão w)
  list        → lista diretório | args: path (opcional, padrão Desktop)
  move        → move arquivo    | args: src, dst
  copy        → copia arquivo   | args: src, dst
  delete      → apaga arquivo   | args: path
  mkdir       → cria pasta      | args: path
  csv_read    → lê CSV          | args: path, max_rows (padrão 20)
  csv_write   → escreve CSV     | args: path, data (lista de dicts ou lista de listas), headers
  find        → busca arquivos  | args: path, pattern (ex: '*.py')
  info        → info do arquivo | args: path
"""
import os
import json
import shutil
import fnmatch
from pathlib import Path
from datetime import datetime

# Pasta base do usuário para caminhos relativos
USER_HOME    = Path.home()
DESKTOP      = USER_HOME / "Desktop"
DOCUMENTS    = USER_HOME / "Documents"
DOWNLOADS    = USER_HOME / "Downloads"

# Extensões permitidas para leitura de texto
TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json',
                   '.csv', '.log', '.ini', '.cfg', '.yaml', '.yml', '.xml',
                   '.bat', '.ps1', '.sh', '.env', '.toml', '.gitignore'}

def _resolve_path(raw_path: str) -> Path:
    """Resolve atalhos amigáveis para caminhos absolutos."""
    p = raw_path.strip()
    aliases = {
        'desktop': str(DESKTOP),
        'documentos': str(DOCUMENTS),
        'documents': str(DOCUMENTS),
        'downloads': str(DOWNLOADS),
        'home': str(USER_HOME),
    }
    for alias, real in aliases.items():
        if p.lower().startswith(alias):
            p = real + p[len(alias):]
            break
    return Path(os.path.expandvars(p))

def _safe_read(path: Path, max_chars: int = 8000) -> str:
    """Lê arquivo de texto com limite de caracteres e encoding robusto."""
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return f"⚠️ Leitura de '{path.suffix}' não suportada. Apenas: {', '.join(sorted(TEXT_EXTENSIONS))}"
    if not path.exists():
        return f"❌ Arquivo não encontrado: {path}"
    if path.stat().st_size > 5_000_000:  # 5MB limit
        return f"❌ Arquivo muito grande ({path.stat().st_size // 1024}KB). Máximo: 5MB."
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            content = path.read_text(encoding=enc)
            if len(content) > max_chars:
                return content[:max_chars] + f"\n\n[... Texto truncado. Total: {len(content)} chars]"
            return content
        except UnicodeDecodeError:
            continue
    return "❌ Não foi possível decodificar o arquivo."

def run(**kwargs):
    operation = kwargs.get('operation', '').lower().strip()
    
    if not operation:
        return ("❌ Parâmetro 'operation' obrigatório.\n"
                "Opções: read, write, list, move, copy, delete, mkdir, csv_read, csv_write, find, info")
    
    try:
        # ── READ ──────────────────────────────────────────
        if operation == 'read':
            path = _resolve_path(kwargs.get('path', ''))
            return _safe_read(path)
        
        # ── WRITE ─────────────────────────────────────────
        elif operation == 'write':
            path    = _resolve_path(kwargs.get('path', ''))
            content = kwargs.get('content', '')
            mode    = kwargs.get('mode', 'w')
            if mode not in ('w', 'a'):
                mode = 'w'
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, mode, encoding='utf-8') as f:
                f.write(content)
            action = 'Arquivo escrito' if mode == 'w' else 'Conteúdo anexado'
            return f"✅ {action} com sucesso: {path}\n({len(content)} caracteres)"
        
        # ── LIST ──────────────────────────────────────────
        elif operation == 'list':
            raw = kwargs.get('path', str(DESKTOP))
            path = _resolve_path(raw)
            if not path.exists():
                return f"❌ Diretório não encontrado: {path}"
            if not path.is_dir():
                return f"❌ '{path}' não é um diretório."
            
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            if not items:
                return f"📂 Diretório vazio: {path}"
            
            lines = [f"📂 {path}\n"]
            for item in items[:100]:  # Limita a 100 itens
                if item.is_dir():
                    lines.append(f"  📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    size_str = f"{size // 1024}KB" if size >= 1024 else f"{size}B"
                    lines.append(f"  📄 {item.name} ({size_str})")
            if len(list(path.iterdir())) > 100:
                lines.append("  ... (mais itens não mostrados)")
            return "\n".join(lines)
        
        # ── MOVE ──────────────────────────────────────────
        elif operation == 'move':
            src = _resolve_path(kwargs.get('src', ''))
            dst = _resolve_path(kwargs.get('dst', ''))
            if not src.exists():
                return f"❌ Origem não encontrada: {src}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"✅ Movido: {src.name} → {dst}"
        
        # ── COPY ──────────────────────────────────────────
        elif operation == 'copy':
            src = _resolve_path(kwargs.get('src', ''))
            dst = _resolve_path(kwargs.get('dst', ''))
            if not src.exists():
                return f"❌ Origem não encontrada: {src}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
            return f"✅ Copiado: {src.name} → {dst}"
        
        # ── DELETE ────────────────────────────────────────
        elif operation == 'delete':
            path = _resolve_path(kwargs.get('path', ''))
            if not path.exists():
                return f"❌ Não encontrado: {path}"
            if path.is_dir():
                shutil.rmtree(str(path))
                return f"✅ Pasta removida: {path}"
            else:
                path.unlink()
                return f"✅ Arquivo removido: {path}"
        
        # ── MKDIR ─────────────────────────────────────────
        elif operation == 'mkdir':
            path = _resolve_path(kwargs.get('path', ''))
            path.mkdir(parents=True, exist_ok=True)
            return f"✅ Pasta criada: {path}"
        
        # ── CSV_READ ──────────────────────────────────────
        elif operation == 'csv_read':
            import csv
            path     = _resolve_path(kwargs.get('path', ''))
            max_rows = int(kwargs.get('max_rows', 20))
            if not path.exists():
                return f"❌ CSV não encontrado: {path}"
            rows = []
            with open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    rows.append(dict(row))
            result = f"📊 CSV: {path.name}\nColunas: {', '.join(headers)}\n\n"
            result += json.dumps(rows, indent=2, ensure_ascii=False)
            return result
        
        # ── CSV_WRITE ─────────────────────────────────────
        elif operation == 'csv_write':
            import csv
            path    = _resolve_path(kwargs.get('path', ''))
            data    = kwargs.get('data', [])
            headers = kwargs.get('headers', [])
            if not data:
                return "❌ Parâmetro 'data' vazio."
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='') as f:
                if isinstance(data[0], dict):
                    headers = headers or list(data[0].keys())
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(data)
                else:
                    writer = csv.writer(f)
                    if headers:
                        writer.writerow(headers)
                    writer.writerows(data)
            return f"✅ CSV salvo: {path} ({len(data)} linhas)"
        
        # ── FIND ──────────────────────────────────────────
        elif operation == 'find':
            path    = _resolve_path(kwargs.get('path', str(USER_HOME)))
            pattern = kwargs.get('pattern', '*')
            if not path.exists():
                return f"❌ Caminho não encontrado: {path}"
            matches = []
            for fpath in path.rglob(pattern):
                matches.append(str(fpath))
                if len(matches) >= 50:
                    break
            if not matches:
                return f"🔍 Nenhum arquivo encontrado com padrão '{pattern}' em {path}"
            return f"🔍 {len(matches)} resultado(s) para '{pattern}':\n" + "\n".join(matches)
        
        # ── INFO ──────────────────────────────────────────
        elif operation == 'info':
            path = _resolve_path(kwargs.get('path', ''))
            if not path.exists():
                return f"❌ Não encontrado: {path}"
            stat = path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            size_kb  = stat.st_size // 1024
            return (f"📄 {path.name}\n"
                    f"Caminho: {path}\n"
                    f"Tipo: {'Pasta' if path.is_dir() else 'Arquivo'}\n"
                    f"Tamanho: {size_kb}KB\n"
                    f"Modificado: {modified}")
        
        else:
            return f"❌ Operação desconhecida: '{operation}'\nOpções: read, write, list, move, copy, delete, mkdir, csv_read, csv_write, find, info"
    
    except PermissionError:
        return f"❌ Permissão negada para acessar o caminho."
    except Exception as e:
        return f"❌ Erro em '{operation}': {type(e).__name__}: {str(e)}"
