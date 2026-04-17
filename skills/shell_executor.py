"""Executa comandos limpos direto no Terminal local (PowerShell/CMD). Retorna o output da tela. Use para buscar arquivos no Windows, dar pings, rodar scripts ou matar processos. OBRIGATÓRIO: Fornecer a key 'command' dentro do 'args' com a invocação/código."""
import subprocess

def run(**kwargs):
    command = kwargs.get("command", "")
    if not command:
        return "Erro: Parâmetro 'command' não fornecido."
    try:
        resultado = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        if resultado.returncode == 0:
            return resultado.stdout if resultado.stdout else "Comando executado com sucesso (sem output em tela)."
        else:
            return f"Erro do sistema ao rodar:\\n{resultado.stderr}"
    except Exception as e:
        return f"Exceção ao rodar comando: {str(e)}"
