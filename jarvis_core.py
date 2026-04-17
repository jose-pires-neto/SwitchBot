"""
jarvis_core.py — Motor de IA do SwitchBot
"""

import os
import json
import re
import threading
from dotenv import load_dotenv
import skill_manager
import model_manager
import memory

class JarvisCore:
    def __init__(self):
        load_dotenv()
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._session_id = memory.create_session()
        self._load_provider()

    def _load_provider(self):
        config = model_manager.load_config()
        self._provider   = config.get('provider', 'groq')
        self._groq_model = config.get('groq_model', 'llama-3.3-70b-versatile')
        self._ollama_model = config.get('ollama_model', 'llama3.1:8b')

        if self._provider == 'groq':
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY não encontrada no .env!")
            from groq import Groq
            self._client = Groq(api_key=api_key)
        else:
            self._client = None

        self._messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]

    def reload_config(self):
        with self._lock:
            self._load_provider()

    def _build_system_prompt(self) -> str:
        skills = skill_manager.get_available_skills()
        skills_json = json.dumps(skills, indent=2, ensure_ascii=False)
        provider_hint = (
            f"Groq Cloud ({self._groq_model})"
            if self._provider == 'groq'
            else f"Ollama Local ({self._ollama_model})"
        )
        
        memory_context = memory.get_context_summary()
        memory_block = f"\n\n{memory_context}\n" if memory_context else ""

        return f"""Você é uma IA autônoma rodando localmente no Windows. Provedor: {provider_hint}.
Seu objetivo é ajudar o usuário interagindo com o PC através de skills Python.
{memory_block}
CATÁLOGO DE SKILLS DISPONÍVEIS:
Use skills existentes sempre que possível. Preste atenção aos 'parametros_esperados' de cada skill e passe-os no objeto 'args'.
{skills_json}

REGRAS DE RESPOSTA (ESTRITAMENTE OBRIGATÓRIO):
Responda SEMPRE com UM ÚNICO bloco JSON válido. NENHUM texto antes ou depois do JSON.

Formatos aceitos:

1. Mensagem ao usuário:
{{
  "thought": "O que vou dizer e porquê.",
  "action": "message",
  "text": "Sua resposta formatada."
}}

2. Executar skill existente:
{{
  "thought": "Vou usar a skill X porque...",
  "action": "execute_skill",
  "skill_name": "nome_exato",
  "args": {{"parametro1": "valor"}}
}}

3. Criar nova skill (apenas se for estritamente necessário):
{{
  "thought": "Preciso de uma nova skill para...",
  "action": "create_skill",
  "skill_name": "nome_sem_espacos",
  "code": "import os\\n\\ndef run(**kwargs):\\n    return 'resultado'"
}}

4. Salvar fato na memória (preferências, senhas, etc):
{{
  "thought": "Usuário quer que eu lembre disso.",
  "action": "save_fact",
  "key": "assunto",
  "value": "detalhe"
}}"""

    def _chat_completion(self, messages: list) -> str:
        if self._provider == 'groq':
            response = self._client.chat.completions.create(
                model=self._groq_model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        else:
            import requests as req
            payload = {
                "model": self._ollama_model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1}
            }
            r = req.post('http://localhost:11434/api/chat', json=payload, timeout=120)
            r.raise_for_status()
            return r.json()['message']['content']

    def _parse_json_response(self, text: str) -> dict:
        """
        Extrator de JSON à prova de balas.
        Ignora textos antes e depois, buscando a raiz do objeto JSON.
        """
        try:
            # Tenta encontrar o primeiro { e o último }
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = text[start_idx:end_idx+1]
                return json.loads(json_str)
            
            # Fallback direto
            return json.loads(text)
        except json.JSONDecodeError as e:
            return {"action": "error", "message": f"Falha ao interpretar resposta da IA como JSON. Resposta bruta: {text[:100]}..."}

    def cancel(self):
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def process_input(self, user_input: str, progress_callback=None) -> str:
        self._cancel_event.clear()
        self._messages[0]["content"] = self._build_system_prompt()
        self._messages.append({"role": "user", "content": user_input})
        memory.save_message(self._session_id, "user", user_input)

        max_iterations = 8

        for _ in range(max_iterations):
            if self.is_cancelled():
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
                    result_text = data.get("text", "")
                    memory.save_message(self._session_id, "assistant", result_text)
                    return result_text

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
                        "content": f"Resultado de '{skill_name}':\n{result}\nO que você responde agora?"
                    })

                elif action == "create_skill":
                    skill_name = data.get("skill_name")
                    code = data.get("code")
                    if progress_callback:
                        progress_callback("executing", f"Criando skill: {skill_name}")

                    result = skill_manager.create_skill(skill_name, code)
                    self._messages.append({
                        "role": "user",
                        "content": f"Sistema: {result}. Se sucesso, execute-a. Se houver erro de sintaxe, corrija e crie novamente."
                    })

                elif action == "save_fact":
                    key   = data.get("key", "")
                    value = data.get("value", "")
                    if key and value:
                        memory.set_fact(key, value)
                        if progress_callback:
                            progress_callback("executing", f"Memorizando: {key}")
                        self._messages.append({
                            "role": "user",
                            "content": f"Sistema: Fato '{key}' memorizado."
                        })
                    else:
                        self._messages.append({"role": "user", "content": "Erro: save_fact requer 'key' e 'value'."})

                else:
                    self._messages.append({"role": "user", "content": "Ação desconhecida ou erro no JSON. Certifique-se de usar apenas as actions permitidas."})

            except Exception as e:
                return f"Erro de comunicação: {str(e)}"

        return "⚠️ Limite de iterações atingido. O agente parou para evitar loop infinito."