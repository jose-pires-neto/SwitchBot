import os
import importlib.util
import traceback
import ast
from security import check_security

SKILLS_DIR = "skills"

# Cria a pasta de skills se não existir
if not os.path.exists(SKILLS_DIR):
    os.makedirs(SKILLS_DIR)

def get_available_skills():
    """Retorna um dicionário com o nome de todas as skills disponíveis e suas descrições."""
    skills = {}
    for filename in os.listdir(SKILLS_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            skill_name = filename.replace(".py", "")
            filepath = os.path.join(SKILLS_DIR, filename)
            description = "Nenhuma docstring encontrada."
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
                parsed = ast.parse(source)
                doc = ast.get_docstring(parsed)
                if doc:
                    description = doc.strip().split('\n')[0]
            except Exception:
                pass
            skills[skill_name] = description
    return skills

def create_skill(skill_name: str, code: str) -> str:
    """
    Salva um novo código gerado pela IA na pasta de skills.
    Inclui verificação de segurança antes de salvar.
    """
    if not check_security(code):
        return "ERRO DE SEGURANÇA: O código gerado contém comandos ou acessos a pastas proibidas do Windows (ex: System32). Ação bloqueada."
    
    # Validação Sintática Antecipada (Syntax Check)
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        return f"ERRO DE SINTAXE: O código gerado é inválido e falhou antes mesmo de rodar. Verifique se não deixou strings ou parênteses abertos. Detalhes: {str(e)}"
        
    # Força a extensão .py e protege contra injeção de caminhos (../)
    safe_name = "".join(c for c in skill_name if c.isalnum() or c == "_")
    filepath = os.path.join(SKILLS_DIR, f"{safe_name}.py")
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        return f"Sucesso! Skill '{safe_name}' criada e salva com sucesso em {filepath}."
    except Exception as e:
        return f"Erro ao salvar a skill: {str(e)}"

def execute_skill(skill_name: str, kwargs: dict) -> str:
    """
    Importa dinamicamente a skill e executa a função run().
    Captura erros de compilação ou execução para a IA poder consertar.
    """
    safe_name = "".join(c for c in skill_name if c.isalnum() or c == "_")
    filepath = os.path.join(SKILLS_DIR, f"{safe_name}.py")
    
    if not os.path.exists(filepath):
        return f"Erro: Skill '{safe_name}' não encontrada."
        
    try:
        # Carregamento dinâmico do módulo em tempo de execução
        spec = importlib.util.spec_from_file_location(safe_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Todas as skills geradas DEVEM ter uma função run()
        if not hasattr(module, "run"):
            return f"Erro: O arquivo {safe_name}.py não possui uma função 'run(**kwargs)'."
            
        # Executa a função e pega o resultado
        result = module.run(**kwargs)
        return str(result)
        
    except Exception as e:
        # Se o código der erro (ex: sintaxe ou biblioteca faltando), retorna o Traceback para a IA consertar
        error_msg = f"Erro ao executar a skill '{safe_name}':\n{traceback.format_exc()}"
        return error_msg