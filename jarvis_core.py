"""
jarvis_core.py — Motor de IA do SwitchBot

Suporta dois provedores:
  - Groq (Cloud): llama, deepseek, etc.
  - Ollama (Local): qualquer modelo instalado
  
Lê o config.json para saber qual provedor/modelo usar.
Pode fazer reload sem reiniciar o processo.
"""

import os
import json
import re
import threading
from dotenv import load_dotenv
import skill_manager
import model_manager

class JarvisCore:
    def __init__(self):
        load_dotenv()
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()  # Protege o client durante reload
        self._load_provider()

    def _load_provider(self):
        """Instancia o client correto baseado no config.json."""
        config = model_manager.load_config()
        self._provider = config.get('provider', 'groq')
        self._groq_model = config.get('groq_model', 'llama-3.3-70b-versatile')
        self._ollama_model = config.get('ollama_model', 'llama3.1:8b')

        if self._provider == 'groq':
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY não encontrada no .env!")
            from groq import Groq
            self._client = Groq(api_key=api_key)
        else:  # ollama
            # Ollama usa a API HTTP diretamente (sem biblioteca especial para chat)
            self._client = None

        # Reseta histórico sempre que troca de provedor/modelo
        self._messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ]

    def reload_config(self):
        """Recarrega o provedor sem reiniciar o processo. Chamado após salvar settings."""
        with self._lock:
            self._load_provider()

    def _chat_completion(self, messages: list) -> str:
        """Abstração única de chamada de chat para Groq ou Ollama."""
        if self._provider == 'groq':
            response = self._client.chat.completions.create(
                model=self._groq_model,
                messages=messages,
                temperature=0.1
            )
            return response.choices[0].message.content

        else:  # ollama via HTTP (compatível com OpenAI)
            import requests as req
            payload = {
                "model": self._ollama_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.1}
            }
            r = req.post('http://localhost:11434/api/chat', json=payload, timeout=120)
            r.raise_for_status()
            return r.json()['message']['content']

    def _get_system_prompt(self):
        skills = skill_manager.get_available_skills()
        skills_json = json.dumps(skills, indent=2, ensure_ascii=False)
        provider_hint = f"Provedor atual: {'Groq Cloud (' + self._groq_model + ')' if self._provider == 'groq' else 'Ollama Local (' + str(self._ollama_model) + ')'}"
        
        return f"""Você é uma IA autônoma rodando localmente no Windows. {provider_hint}
Seu objetivo é ajudar o usuário interagindo com o PC através de scripts Python ("skills").

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

3. Criar uma nova skill (somente se não existir alternativa no catálogo):
{{
  "thought": "Justificativa forte de porque criar essa nova skill...",
  "action": "create_skill",
  "skill_name": "nome_da_nova_skill",
  "code": "\\\"\\\"\\\"DOCSTRING OBRIGATÓRIA\\\"\\\"\\\"\\nimport os\\n\\ndef run(**kwargs):\\n    return '...'"
}}

LEMBRE-SE: Retorne APENAS um objeto JSON. Nenhuma explicação verbal solta."""

    def _parse_json_response(self, response_text):
        try:
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {"action": "error", "message": "O LLM não retornou um JSON válido."}

    def cancel(self):
        """Sinaliza para o loop do agente parar imediatamente."""
        self._cancel_event.set()

    def is_cancelled(self):
        return self._cancel_event.is_set()

    def process_input(self, user_input: str, progress_callback=None) -> str:
        """
        Processa a entrada do usuário com Chain of Thought.
        progress_callback(type, text) para feedback em tempo real.
        Respeita cancel() para abortar.
        """
        self._cancel_event.clear()
        self._messages[0]["content"] = self._get_system_prompt()
        self._messages.append({"role": "user", "content": user_input})

        max_iterations = 8

        for iteration in range(max_iterations):
            if self.is_cancelled():
                self._messages.append({"role": "user", "content": "Sistema: Tarefa cancelada pelo usuário."})
                return "⏹️ Tarefa cancelada."

            try:
                with self._lock:
                    ai_text = self._chat_completion(self._messages)

                if self.is_cancelled():
                    return "⏹️ Tarefa cancelada."

                self._messages.append({"role": "assistant", "content": ai_text})
                data = self._parse_json_response(ai_text)

                thought = data.get("thought")
                if thought and progress_callback:
                    progress_callback("thought", thought)

                action = data.get("action")

                if action == "message":
                    return data.get("text", "")

                elif action == "execute_skill":
                    skill_name = data.get("skill_name")
                    args = data.get("args", {})
                    if progress_callback:
                        progress_callback("executing", f"Skill: {skill_name}")

                    result = skill_manager.execute_skill(skill_name, args)

                    if self.is_cancelled():
                        return "⏹️ Tarefa cancelada."

                    self._messages.append({
                        "role": "user",
                        "content": f"Resultado da skill '{skill_name}':\n{result}\nO que você diz/faz agora?"
                    })

                elif action == "create_skill":
                    skill_name = data.get("skill_name")
                    code = data.get("code")
                    if progress_callback:
                        progress_callback("executing", f"Criando skill: {skill_name}")

                    result = skill_manager.create_skill(skill_name, code)
                    self._messages.append({
                        "role": "user",
                        "content": f"Sistema: {result}. Se foi um sucesso, execute-a ou responda."
                    })

                else:
                    self._messages.append({
                        "role": "user",
                        "content": "Ação desconhecida ou JSON inválido. Corrija o formato."
                    })

            except Exception as e:
                return f"Erro de comunicação: {str(e)}"

        return "⚠️ Limite de iterações atingido. O agente foi interrompido para evitar loop."
