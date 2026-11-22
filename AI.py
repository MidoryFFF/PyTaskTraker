"""
Модуль ИИ: интеграция с локальными моделями через Ollama + решения проблемы
маленького окна контекста.

Интеграция с Ollama (http://localhost:11434):
  - /api/chat со схемой инструментов (нативный tool-calling);
  - /api/generate и /api/tags;
  - поддержка OpenAI-совместимого API (/v1) как запасной вариант.

Стратегии работы с маленьким контекстным окном:
  1. Токенизация и усечение отдельных сообщений (trim_messages).
  2. Скользящее окно истории: старые сообщения вытесняются, суммаризируются
     моделью и передаются как компактное "сжатое воспоминание" (rolling summary).
  3. Retrieval (RAG): вместо загрузки всей базы событий в промпт ИИ получает
     только релевантные фрагменты через инструменты search/list/free_slots.
  4. Сжатие длинных текстов описаний (compress_text) — сокращение без модели.
  5. Настройка num_ctx Ollama — увеличение окна контекста на стороне сервера.
"""
import json
import re

import requests

from Instruments import get_tool_schemas, call_tool

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1"

SYSTEM_PROMPT = (
    "Ты — ассистент планировщика. У тебя есть инструменты для работы с базой данных "
    "событий (SQLite). Отвечай кратко по-русски. Для действий с календарём обязательно "
    "используй инструменты, а не выдумывай данные. Текущая дата передана в системном сообщении."
)


# ==================== Ollama client ====================
class OllamaClient:
    def __init__(self, base_url=OLLAMA_URL, model=DEFAULT_MODEL, num_ctx=4096):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx  # решение №5: размер окна контекста задаётся параметром

    def is_available(self):
        try:
            requests.get(f"{self.base_url}/api/tags", timeout=2)
            return True
        except requests.RequestException:
            return False

    def list_models(self):
        r = requests.get(f"{self.base_url}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]

    def chat(self, messages, tools=None):
        """Запрос к /api/chat. Возвращает dict ответа Ollama."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": self.num_ctx},
        }
        if tools:
            payload["tools"] = tools
        r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()

    def generate(self, prompt, system=""):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"num_ctx": self.num_ctx},
        }
        r = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["response"]


# ==================== работа с контекстом ====================
def rough_token_count(text):
    """Эвристическая оценка числа токенов (~4 символа на токен)."""
    return max(1, len(str(text)) // 4)


def trim_message(text, max_tokens=800):
    """Решение №1: усечение слишком длинного сообщения/результата."""
    limit = max_tokens * 4
    s = str(text)
    return s if len(s) <= limit else s[:limit] + "…[усечено]"


def compress_text(text, max_words=40):
    """Решение №4: дешёвое сжатие текста — первые предложения до лимита слов."""
    sentences = re.split(r"(?<=[.!?])\s+", str(text))
    out, words = [], 0
    for sent in sentences:
        w = len(sent.split())
        if words + w > max_words and out:
            break
        out.append(sent)
        words += w
    return " ".join(out)


class ContextManager:
    """
    Решение №2: скользящее окно + свёртка истории.

    history хранит сообщения чата. Когда суммарные "токены" превышают budget,
    самые старые сообщения выносятся в old_messages и суммаризируются
    (через модель, если доступна, иначе механически). В каждый запрос попадает:
    системный промпт + компактная сводка + последние N сообщений.
    """

    def __init__(self, client: OllamaClient, token_budget=2500, keep_recent=6):
        self.client = client
        self.token_budget = token_budget
        self.keep_recent = keep_recent
        self.history = []          # [{"role":..., "content":...}]
        self.summary = ""          # сжатое воспоминание о старых ходах

    def add(self, role, content):
        self.history.append({"role": role, "content": trim_message(content)})

    def _fold_old(self):
        old, recent = self.history[:-self.keep_recent], self.history[-self.keep_recent:]
        if not old:
            return
        text_block = "\n".join(f"{m['role']}: {m['content']}" for m in old)
        try:
            if self.client.is_available():
                new_part = self.client.generate(
                    "Сожми этот диалог с планировщиком в 2-3 предложения, "
                    "сохранив ключевые факты (даты, события, id):\n" + text_block)
            else:
                raise requests.RequestException("ollama offline")
        except requests.RequestException:
            new_part = compress_text(text_block.replace("\n", " "), 30)
        self.summary = trim_message((self.summary + " | " if self.summary else "") + new_part, 300)
        self.history = recent

    def build_messages(self, extra_system=""):
        """Собирает финальный список сообщений в рамках бюджета токенов."""
        while sum(rough_token_count(m["content"]) for m in self.history) > self.token_budget:
            before = len(self.history)
            self._fold_old()
            if len(self.history) == before:
                break
        msgs = []
        sys = SYSTEM_PROMPT + (f"\n{extra_system}" if extra_system else "")
        if self.summary:
            sys += f"\nКраткая память о предыдущих репликах: {self.summary}"
        msgs.append({"role": "system", "content": sys})
        msgs.extend(self.history)
        return msgs

    # ---------- агентный цикл с инструментами ----------
    def ask(self, user_text, use_tools=True, max_tool_steps=5):
        from datetime import date
        self.add("user", user_text)
        messages = self.build_messages(extra_system=f"Текущая дата: {date.today().isoformat()} "
                                                    "(понедельник=0 ... воскресенье=6).")
        tools = get_tool_schemas() if use_tools else None
        trace = []
        for _ in range(max_tool_steps):
            reply = self.client.chat(messages, tools=tools)
            msg = reply.get("message", {})
            calls = msg.get("tool_calls")
            if not calls:
                content = msg.get("content", "")
                self.add("assistant", content)
                return {"answer": content, "trace": trace}
            messages.append(msg)
            for tc in calls:
                fn = tc["function"]
                result = call_tool(fn["name"], fn.get("arguments", {}))
                result_str = trim_message(json.dumps(result, ensure_ascii=False), 600)
                trace.append({"tool": fn["name"], "args": fn.get("arguments"), "result": result_str})
                messages.append({"role": "tool", "content": result_str})
            # решение №3 (RAG): в контекст попадают только результаты инструментов,
            # а не вся база событий целиком
        self.add("assistant", messages[-1]["content"])
        return {"answer": "Превышен лимит шагов инструментов.", "trace": trace}
