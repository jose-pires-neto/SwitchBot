"""
jarvis_core.py — Motor de IA do SwitchBot

Suporta dois provedores:
  - Groq (Cloud): modelos llama, deepseek, etc.
  - Ollama (Local): qualquer modelo instalado

Memória persistente via SQLite (memory.py):
  - Cada sessão de uso é salva com histórico de mensagens
  - Fatos e preferências do usuário sobrevivem entre sessões
  - Contexto resumido é injetado no system prompt automaticamente
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
        
        # Inicia nova sessão de memória
        self._session_id = memory.create_session()
        
        self._load_provider()

    def _load_provider(self):
        """Instancia o client correto baseado no config.json."""
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
            self._client = None  # Ollama via HTTP

        # Reconstrói o histórico em memória com o system prompt atualizado
        self._messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]

    def reload_config(self):
        """Recarrega provedor/modelo sem reiniciar o processo."""
        with self._lock:
            self._load_provider()

    def _build_system_prompt(self) -> str:
        """Monta o system prompt com skills + contexto de memória persistente."""
        skills = skill_manager.get_available_skills()
        skills_json = json.dumps(skills, indent=2, ensure_ascii=False)
        provider_hint = (
            f"Groq Cloud ({self._groq_model})"
            if self._provider == 'groq'
            else f"Ollama Local ({self._ollama_model})"
        )
        
        # Injeta contexto de memória (fatos + resumo da última sessão)
        memory_context = memory.get_context_summary()
        memory_block = ""
        if memory_context:
            memory_block = f"\n\n{memory_context}\n"

        return f"""Você é uma IA autônoma rodando localmente no Windows. Provedor: {provider_hint}.
Seu objetivo é ajudar o usuário interagindo com o PC através de skills Python.
{memory_block}
CATÁLOGO DE SKILLS DISPONÍVEIS:
Use skills existentes sempre que possível. NÃO crie skills duplicadas!
{skills_json}

REGRAS DE RESPOSTA (ESTRITAMENTE OBRIGATÓRIO):
Responda SEMPRE com UM ÚNICO bloco JSON válido. Nenhum texto fora do JSON!

Formatos aceitos:

1. Mensagem ao usuário:
{{
  "thought": "Raciocínio rápido.",
  "action": "message",
  "text": "Sua resposta."
}}

2. Executar skill existente:
{{
  "thought": "Por que uso esta skill e com quais argumentos.",
  "action": "execute_skill",
  "skill_name": "nome_exato_da_skill",
  "args": {{"param": "valor"}}
}}

3. Criar nova skill (somente se não houver alternativa):
{{
  "thought": "Justificativa forte.",
  "action": "create_skill",
  "skill_name": "nome_unico",
  "code": "\\\"\\\"\\\"Docstring obrigatória\\\"\\\"\\\"\\nimport os\\n\\ndef run(**kwargs):\\n    return 'resultado'"
}}

4. Salvar fato/preferência do usuário na memória permanente:
{{
  "thought": "O usuário mencionou algo importante para lembrar.",
  "action": "save_fact",
  "key": "chave_descritiva",
  "value": "valor a lembrar"
}}

LEMBRE-SE: Retorne apenas JSON. Sem markdown ou texto livre."""

    def _chat_completion(self, messages: list) -> str:
        """Abstração única de chat para Groq ou Ollama."""
        if self._provider == 'groq':
            response = self._client.chat.completions.create(
                model=self._groq_model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"} # Força o modo JSON no Groq
            )
            return response.choices[0].message.content
        else:
            import requests as req
            payload = {
                "model": self._ollama_model,
                "messages": messages,
                "stream": False,
                "format": "json", # Força o modo JSON no Ollama
                "options": {"temperature": 0.1}
            }
            r = req.post('http://localhost:11434/api/chat', json=payload, timeout=120)
            r.raise_for_status()
            return r.json()['message']['content']

    def _parse_json_response(self, text: str) -> dict:
        try:
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(text)
        except json.JSONDecodeError:
            return {"action": "error", "message": "JSON inválido na resposta da IA."}

    def cancel(self):
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def process_input(self, user_input: str, progress_callback=None) -> str:
        """
        Processa entrada do usuário com Chain of Thought.
        Persiste todas as mensagens no SQLite automaticamente.
        """
        self._cancel_event.clear()
        
        # Atualiza system prompt com memória mais recente
        self._messages[0]["content"] = self._build_system_prompt()
        
        # Adiciona e persiste a mensagem do usuário
        self._messages.append({"role": "user", "content": user_input})
        memory.save_message(self._session_id, "user", user_input)

        max_iterations = 8

        for _ in range(max_iterations):
            if self.is_cancelled():
                memory.save_message(self._session_id, "system", "Tarefa cancelada pelo usuário.")
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

                # ── MESSAGE ───────────────────────────────
                if action == "message":
                    result_text = data.get("text", "")
                    memory.save_message(self._session_id, "assistant", result_text)
                    return result_text

                # ── EXECUTE SKILL ─────────────────────────
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

                # ── CREATE SKILL ──────────────────────────
                elif action == "create_skill":
                    skill_name = data.get("skill_name")
                    code = data.get("code")
                    if progress_callback:
                        progress_callback("executing", f"Criando skill: {skill_name}")

                    result = skill_manager.create_skill(skill_name, code)
                    self._messages.append({
                        "role": "user",
                        "content": f"Sistema: {result}. Se sucesso, execute-a ou responda."
                    })

                # ── SAVE FACT (memória permanente) ─────────
                elif action == "save_fact":
                    key   = data.get("key", "")
                    value = data.get("value", "")
                    if key and value:
                        memory.set_fact(key, value)
                        if progress_callback:
                            progress_callback("executing", f"Memorizando: {key}")
                        self._messages.append({
                            "role": "user",
                            "content": f"Sistema: Fato '{key}' memorizado com sucesso. Confirme ao usuário."
                        })
                    else:
                        self._messages.append({
                            "role": "user",
                            "content": "Erro: save_fact requer 'key' e 'value'. Corrija e tente novamente."
                        })

                else:
                    self._messages.append({
                        "role": "user",
                        "content": "Ação desconhecida ou JSON inválido. Corrija o formato."
                    })

            except Exception as e:
                error_msg = f"Erro de comunicação: {str(e)}"
                memory.save_message(self._session_id, "system", error_msg)
                return error_msg

        return "⚠️ Limite de iterações atingido. O agente foi interrompido para evitar loop."