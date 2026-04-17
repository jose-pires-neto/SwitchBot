import re
import os

# Lista de comandos de terminal perigosos
FORBIDDEN_COMMANDS = [
    r"rmdir\s+/s",
    r"del\s+/f",
    r"format\s+",
    r"reg\s+delete",
    r"diskpart",
    r"net\s+user",
    r"shutdown",
    r"mkfs"
]

def check_security(code_string: str) -> bool:
    """
    Analisa o código gerado pela IA em busca de padrões perigosos.
    Retorna True se for seguro, False se contiver ameaças.
    """
    code_lower = code_string.lower()
            
    # Verifica comandos perigosos
    for cmd in FORBIDDEN_COMMANDS:
        if re.search(cmd, code_lower):
            print(f"\n[ALERTA DE SEGURANÇA] Comando destrutivo detectado: {cmd}")
            return False
            
    return True