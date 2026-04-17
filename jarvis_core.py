import os
import json
import re
import threading
from dotenv import load_dotenv
from groq import Groq
import skill_manager

class JarvisCore:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY não encontrada no arquivo .env!")
        
        self.client = Groq(api_key=api_key)
        self.messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        # Flag de cancelamento acessível por qualquer thread
        self._cancel_event = threading.Event()

    def cancel(self):
        """Sinaliza para o loop do agente parar imediatamente."""
        self._cancel_event.set()

    def is_cancelled(self):
        return self._cancel_event.is_set()

    def get_system_prompt(self):
        skills = skill_manager.get_available_skills()
        skills_json = json.dumps(skills, indent=2, ensure_ascii=False)
        prompt = f"""Você é uma IA autônoma rodando localmente no Windows. Seu objetivo é ajudar o usuário interagindo com o PC através de scripts Python ("skills").

CATÁLOGO DE SKILLS DISPONÍVEIS:
Consulte a lista abaixo. Se o usuário pedir algo que já exista aqui, USE EXATAMENTE A SKILL EXISTENTE com a ação "execute_skill". NÃO CRIE skills duplicadas!
{skills_json}

REGRAS DE RESPOSTA (ESTRITAMENTE OBRIGATÓRIO):
Você DEVE responder SEMPRE através de UM ÚNICO bloco JSON válido. 
Em hipótese alguma adicione textos ou markdown de conversa fora do bloco de JSON!

Escolha e retorne exatamente UM destes formatos:

1. Falar com o usuário:
{{
  "thought": "Breve racionalização.",
  "action": "message",
  "text": "Sua resposta direta."
}}

2. Executar uma skill do Catálogo Acima:
{{
  "thought": "Raciocínio de porquê vou chamar e com quais argumentos...",
  "action": "execute_skill",
  "skill_name": "nome_da_skill_que_ja_existe",
  "args": {{"param": "valor"}}
}}

3. Criar uma nova skill (somente se não existir alternativa no catálogo MESTRE e não puder ser resolvida via shell_executor):
ATENÇÃO:
- O código DEVE conter `def run(**kwargs):`
- A 1ª linha DEVE OBRIGATORIAMENTE ser uma docstring explicando o que ela faz.
- CUIDADO COM SINTAXE PYTHON.
- Como você agora possui um executor de terminal local (`shell_executor`), dificilmente precisará criar um wrapper Python para comandos simples.
{{
  "thought": "Justificativa forte de porque criar essa nova skill...",
  "action": "create_skill",
  "skill_name": "nome_da_nova_skill",
  "code": "\\\"\\\"\\\"DOCSTRING OBRIGATORIA EXPLICANDO O QUE A FERRAMENTA FAZ\\\"\\\"\\\"\\nimport os\\n\\ndef run(**kwargs):\\n    import subprocess\\n    return '...'"
}}

LEMBRE-SE: Retorne APENAS um objeto JSON. Nenhuma explicação verbal solta."""
        return prompt

    def parse_json_response(self, response_text):
        try:
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {"action": "error", "message": "O LLM não retornou um JSON válido."}

    def process_input(self, user_input, progress_callback=None):
        """
        Processa a entrada do usuário e retorna a msg final.
        progress_callback permite notificar thoughts em tempo real.
        Respeita self._cancel_event para abortar o loop.
        """
        # Reseta o flag de cancelamento para esta nova tarefa
        self._cancel_event.clear()
        
        self.messages.append({"role": "user", "content": user_input})
        
        max_iterations = 8  # Limite duro para evitar loops infinitos
        iteration = 0
        
        while iteration < max_iterations:
            # Checagem de cancelamento ANTES de chamar a API
            if self.is_cancelled():
                self.messages.append({"role": "user", "content": "Sistema: Tarefa cancelada pelo usuário."})
                return "⏹️ Tarefa cancelada."
            
            iteration += 1
            
            try:
                self.messages[0]["content"] = self.get_system_prompt()
                
                response = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=self.messages,
                    temperature=0.1
                )
                
                # Checagem de cancelamento APÓS receber a resposta
                if self.is_cancelled():
                    return "⏹️ Tarefa cancelada."
                
                ai_text = response.choices[0].message.content
                self.messages.append({"role": "assistant", "content": ai_text})
                
                data = self.parse_json_response(ai_text)
                
                thought = data.get("thought")
                if thought and progress_callback:
                    progress_callback("thought", thought)
                    
                action = data.get("action")
                
                if action == "message":
                    return data.get("text", "")
                    
                elif action == "execute_skill":
                    skill_name = data.get("skill_name")
                    args = data.get("args", {})
                    if progress_callback: progress_callback("executing", f"Skill: {skill_name}")
                    
                    result = skill_manager.execute_skill(skill_name, args)
                    
                    if self.is_cancelled():
                        return "⏹️ Tarefa cancelada."
                    
                    self.messages.append({"role": "user", "content": f"Resultado da execução da skill '{skill_name}':\n{result}\nO que você diz/faz agora?"})
                    
                elif action == "create_skill":
                    skill_name = data.get("skill_name")
                    code = data.get("code")
                    if progress_callback: progress_callback("executing", f"Criando skill: {skill_name}")
                    
                    result = skill_manager.create_skill(skill_name, code)
                    self.messages.append({"role": "user", "content": f"Sistema: {result}. Se foi um sucesso, você já pode executá-la ou responder."})
                    
                else:
                    self.messages.append({"role": "user", "content": "Ação desconhecida ou erro no JSON. Corrija o formato."})
                    
            except Exception as e:
                return f"Erro de comunicação: {str(e)}"
        
        # Se chegou aqui, excedeu o limite de iterações
        return "⚠️ Limite de iterações atingido. O agente foi interrompido automaticamente para evitar loop."
