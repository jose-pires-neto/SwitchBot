import os
import importlib.util
import traceback
import ast
from security import check_security

SKILLS_DIR = "skills"

if not os.path.exists(SKILLS_DIR):
    os.makedirs(SKILLS_DIR)

def get_available_skills():
    """
    Retorna nome, descrição e os PARÂMETROS que a skill aceita.
    Isso é crucial para a IA saber o que mandar no dict 'args'.
    """
    skills = {}
    for filename in os.listdir(SKILLS_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            skill_name = filename.replace(".py", "")
            filepath = os.path.join(SKILLS_DIR, filename)
            
            description = "Nenhuma docstring."
            expected_args = []
            
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
                parsed = ast.parse(source)
                
                # Extrai a docstring
                doc = ast.get_docstring(parsed)
                if doc:
                    description = doc.strip().split('\n')[0]
                    
                # Extrai os argumentos da função run()
                for node in ast.walk(parsed):
                    if isinstance(node, ast.FunctionDef) and node.name == 'run':
                        for arg in node.args.args:
                            expected_args.append(arg.arg)
                        if node.args.kwarg: # Aceita **kwargs genérico
                            expected_args.append("**kwargs")
                            
            except Exception:
                pass
                
            skills[skill_name] = {
                "descricao": description,
                "parametros_esperados": expected_args if expected_args else "Nenhum"
            }
    return skills

def create_skill(skill_name: str, code: str) -> str:
    if not check_security(code):
        return "ERRO DE SEGURANÇA: O código contém comandos proibidos. Ação bloqueada."
    
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        return f"ERRO DE SINTAXE: O código gerado é inválido. Detalhes: {str(e)}"
        
    safe_name = "".join(c for c in skill_name if c.isalnum() or c == "_")
    filepath = os.path.join(SKILLS_DIR, f"{safe_name}.py")
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        return f"Sucesso! Skill '{safe_name}' criada em {filepath}."
    except Exception as e:
        return f"Erro ao salvar a skill: {str(e)}"

def execute_skill(skill_name: str, kwargs: dict) -> str:
    safe_name = "".join(c for c in skill_name if c.isalnum() or c == "_")
    filepath = os.path.join(SKILLS_DIR, f"{safe_name}.py")
    
    if not os.path.exists(filepath):
        return f"Erro: Skill '{safe_name}' não encontrada."
        
    try:
        spec = importlib.util.spec_from_file_location(safe_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "run"):
            return f"Erro: A skill {safe_name}.py não possui a função 'run(**kwargs)'."
            
        result = module.run(**kwargs)
        return str(result)
        
    except Exception as e:
        return f"Erro ao executar a skill '{safe_name}':\n{traceback.format_exc()}"