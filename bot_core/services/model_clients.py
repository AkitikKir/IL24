"""
Модуль для взаимодействия с ИИ-платформой ИЛ24 (Aiza AI).
Обеспечивает отправку запросов к различным языковым моделям через OpenAI-совместимый интерфейс.
"""

from __future__ import annotations

import logging
import re
import httpx
import os
from typing import Dict, List, Optional, Tuple

from ..config import BotConfig
from ..ui.messages import SYSTEM_INSTRUCTIONS, REFUSAL_PHRASES
from ..utils.text import escape_md_v2

# URL для доступа к API чат-завершений Aiza AI (интеграционная шина для множества ИИ моделей)
AIZA_API_URL = "https://api.aiza-ai.ru/v1/chat/completions"
# Ключ API считывается из переменных окружения (Environment Variables) для безопасности
AIZA_API_KEY = os.getenv("AIZA_API_KEY")

# Словарь доступных моделей и их человекочитаемых названий.
# Ключ - технический ID в API, значение - то, что увидит пользователь в меню.
AVAILABLE_MODELS = {
    "yandexgpt/rc": "YandexGPT 5.1 Pro",
    "yandexgpt-lite/latest": "YandexGPT 5 Lite",
    "yandexgpt/latest": "YandexGPT 5 Pro",
    "aliceai-llm/latest": "Алиса AI",
    "gpt-oss-120b/latest": "GPT OSS 120B",
    "gemma-3-27b-it/latest": "Gemma 3 27B",
    "qwen3-235b-a22b-fp8/latest": "Qwen3 235B",
    "llama-3.1-8b-instant": "Llama 3.1 8B",
    "llama-3.3-70b-versatile": "Llama 3.3 70B",
    "moonshotai/kimi-k2-instruct": "Moonshot Kimi K2",
    "meta-llama/llama-4-scout-17b-16e-instruct": "Llama 4 Scout 17B",
    "groq/compound-mini": "Groq Compound Mini",
    "groq/compound": "Groq Compound",
    "deepseek-reasoner": "DeepSeek Reasoner",
}


class AizaModel:
    """
    Класс-клиент для взаимодействия с API ИЛ24 (Aiza AI).
    Использует библиотеку httpx для выполнения сетевых запросов.
    Реализует стандартный интерфейс отправки сообщений и получения ответов от нейросетей.
    """

    def __init__(self, config: BotConfig):
        """
        Инициализация клиента. 
        Настраивает URL эндпоинта и сохраняет логгер для отладки сетевых соединений.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.api_url = AIZA_API_URL
        self.api_key = AIZA_API_KEY
        self.default_model = "yandexgpt"
        self.logger.info("Сетевой клиент ИЛ24 успешно инициализирован.")

    def is_ready(self) -> bool:
        """
        Проверяет техническую готовность клиента.
        Возвращает True, если API ключ найден, иначе False (запросы будут невозможны).
        """
        return bool(self.api_key)

    def stream_completion(
        self,
        model_id: str,
        messages: List[Dict],
        progress_callback=None,
        raw_response: bool = False,
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Основной метод выполнения запроса к нейросети.
        
        Параметры:
            model_id: Техническое имя модели (напр. 'deepseek-reasoner').
            messages: Список словарей в формате OpenAI (роль, контент).
            progress_callback: Необязательная функция для обработки потоковых данных.
            raw_response: Флаг отключения экранирования Markdown (нужен для веб-интерфейса).
            
        Результат:
            Тройка значений: (текст_ответа, флаг_успеха, режим_разметки).
        """
        if not self.api_key:
            return "Критическая ошибка: Ключ API ИЛ24 отсутствует в .env файле.", False, None

        # Формируем стандартные HTTP заголовки для авторизации по токену
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # Конфигурируем параметры запроса к модели
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,   # Уровень "креативности" (от 0 до 1)
            "max_tokens": 1000,    # Максимальное количество слов/токенов в ответе
        }

        content_buf = "" # Буфер для накопления текста ответа

        try:
            # Используем синхронный httpx.Client с увеличенным таймаутом (ИИ может думать долго)
            with httpx.Client(timeout=60.0) as client:
                response = client.post(self.api_url, headers=headers, json=payload)
                # Если сервер вернул ошибку (4xx или 5xx), генерируем исключение HTTPStatusError
                response.raise_for_status()
                data = response.json()

            # Пытаемся безопасно извлечь текст из JSON-ответа
            try:
                # Стандартная структура OpenAI: choices[0].message.content
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                content_buf = msg.get("content", "") or msg.get("text", "") or ""
            except Exception:
                # Если формат ответа нестандартный, сохраняем весь JSON для отладки
                self.logger.warning("Неожиданный формат JSON от API: %s", data)
                content_buf = str(data)

            # Очищаем ответ от технических тегов 'рассуждения' (<think>...</think>), 
            # которые выдают некоторые современные модели перед основным текстом.
            content_buf = re.sub(r"<think>.*?</think>", "", content_buf, flags=re.S | re.I).strip()
            
            # Если запрос пришел от веб-сервера (Mini App), возвращаем текст "как есть" (без Markdown экранирования)
            if raw_response:
                return content_buf or "(ИИ вернул пустой ответ)", True, None
            
            # Если запрос для Telegram бота, экранируем служебные символы для MarkdownV2
            # (точки, дефисы и т.д.), чтобы избежать ошибок рендеринга.
            escaped_answer = escape_md_v2(content_buf or "(ИИ вернул пустой ответ)")
            return escaped_answer, True, "MarkdownV2"

        except httpx.HTTPStatusError as e:
            # Ошибка на стороне сервера API или неверный ключ
            self.logger.exception("Сервер ИЛ24 вернул ошибку: %s", e)
            return f"Ошибка API (код {e.response.status_code}). Попробуйте позже.", False, None
        except Exception as e:
            # Ошибки сети, таймауты или проблемы парсинга JSON
            self.logger.exception("Сетевая ошибка при запросе к ИЛ24: %s", e)
            return f"Сбой сетевого соединения: {e}", False, None

    def run(self, full_prompt: str, model_id: str = "yandexgpt") -> Tuple[str, bool]:
        """
        Упрощенный метод для быстрой отправки одного сообщения без истории диалога.
        """
        messages = [{"role": "user", "content": full_prompt}]
        result, ok, _ = self.stream_completion(model_id, messages, raw_response=True)
        return result, ok
