"""
Бизнес-логика чата: управление выбором ИИ моделей, построение контекста диалога (промптов) 
и обработка ответов в режиме реального времени (стриминг).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from ..config import BotConfig
from ..storage.history import BaseHistoryStorage
from ..ui.messages import MESSAGES, REFUSAL_PHRASES, SYSTEM_INSTRUCTIONS
from ..utils.text import escape_md_v2, make_safe_key
from .model_clients import AizaModel, AVAILABLE_MODELS
from .user_service import UserService


class ChatService:
    """
    Класс-сервис, который инкапсулирует всю логику работы с AI-моделями и историей чатов.
    Отвечает за формирование запросов к провайдерам ИИ, управление контекстом и сохранение переписки.
    Является связующим звеном между пользовательским интерфейсом и алгоритмами ИИ.
    """

    def __init__(
        self,
        config: BotConfig,
        history_storage: BaseHistoryStorage,
        user_service: UserService,
    ):
        """
        Инициализация сервиса с внедрением необходимых зависимостей.
        Сохраняет ссылки на конфигурацию, хранилище истории и сервис пользователей.
        """
        self.config = config
        self.history_storage = history_storage
        self.user_service = user_service
        # Инициализируем стандартный логгер для отслеживания процессов внутри сервиса
        self.logger = logging.getLogger(self.__class__.__name__)
        # Инициализация клиента для взаимодействия с API ИЛ24 (OpenRouter/YandexGPT)
        self.aiza_model = AizaModel(config)

        # Словари для хранения временных данных текущей сессии в оперативной памяти (кэширование)
        self.user_states: Dict[int, Optional[str]] = {} # Текущее состояние диалога (напр., ввод промпта)
        self.user_model_choice: Dict[int, str] = {}     # Выбранная конкретным пользователем ИИ модель

        # Динамическая подготовка кнопок выбора моделей для клавиатуры Telegram
        # Это позволяет добавлять новые модели через конфиг без правок в коде UI
        self.model_buttons: Dict[str, Dict[str, str]] = {}
        for model_id, label in AVAILABLE_MODELS.items():
            # Генерируем "чистый" ключ для callback_data, убирая спецсимволы
            self.model_buttons[make_safe_key(label)] = {"label": label, "model_id": model_id}

        # Какая модель будет использоваться, если пользователь еще не сделал осознанный выбор
        self.default_model = "yandexgpt"

    def get_message(self, user_id: int, key: str) -> str:
        """
        Извлекает текст сообщения по ключу с учетом текущего языка пользователя.
        Если перевод на выбранный язык отсутствует, возвращается английская версия или сам ключ.
        """
        language = self.user_service.get_language(user_id)
        # Ищем в словаре MESSAGES сначала язык пользователя, потом английский по умолчанию
        return MESSAGES.get(language, MESSAGES["en"]).get(key, key)

    def get_language(self, user_id: int) -> str:
        """
        Определяет, на каком языке бот должен общаться с данным пользователем.
        Данные берутся из профиля пользователя в базе данных.
        """
        return self.user_service.get_language(user_id)

    def get_current_model_label(self, user_id: int) -> str:
        """
        Возвращает красивое отображаемое название (например, 'GPT-4 Turbo') 
        текущей выбранной пользователем модели.
        """
        chosen = self.user_model_choice.get(user_id, self.default_model)
        for meta in self.model_buttons.values():
            if meta["model_id"] == chosen:
                return meta["label"]
        # Если в кнопках не нашли, берем из общего списка доступных моделей
        return AVAILABLE_MODELS.get(chosen, str(chosen))

    def load_history(self, user_id: int, limit: int, chat_id: Optional[int] = None) -> List[Tuple[str, str]]:
        """
        Запрашивает из базы данных последние N сообщений диалога.
        Поддерживает разделение по chat_id для корректной работы в Mini App (несколько чатов).
        """
        return self.history_storage.load_history(user_id, limit, chat_id)

    def clear_history(self, user_id: int, chat_id: Optional[int] = None) -> None:
        """
        Полностью очищает историю переписки для пользователя или конкретного чата.
        Обычно вызывается командой /clear или кнопкой в интерфейсе.
        """
        self.history_storage.clear_history(user_id, chat_id)

    def build_messages(self, user_id: int, system_msg: str, prompt: str, chat_id: Optional[int] = None) -> List[dict]:
        """
        Собирает полный массив сообщений для отправки в ИИ (System + History + User Prompt).
        Соблюдает лимит max_history_messages из конфигурации для экономии токенов.
        """
        # Загружаем сообщения из БД
        hist = self.load_history(user_id, self.config.max_history_messages, chat_id)
        # Первым всегда идет системное сообщение (личность и правила поведения ИИ)
        messages = [{"role": "system", "content": system_msg}]
        
        # Добавляем историю, фильтруя только сообщения пользователя и ассистента
        for role, content in hist:
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": content})
            
        # Последним добавляем текущий запрос пользователя
        messages.append({"role": "user", "content": prompt})
        return messages

    def process_query(
        self,
        user_id: int,
        prompt: str,
        progress_callback=None,
        system_prompt: Optional[str] = None,
        raw_response: bool = False,
        chat_id: Optional[int] = None,
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Главный конвейер обработки запроса:
        1. Определение языка и системных правил.
        2. Проверка работоспособности API.
        3. Сборка контекста из истории.
        4. Сохранение вопроса пользователя в БД.
        5. Получение ответа от ИИ (с поддержкой стриминга).
        6. Проверка на этические ограничения (отказы).
        7. Сохранение финального ответа в БД.
        """
        language = self.get_language(user_id)
        
        # Выбор системной инструкции. Если не передана явно — берем стандартную по языку.
        if system_prompt:
            system_msg = system_prompt
        else:
            system_instruction = SYSTEM_INSTRUCTIONS[language]
            # Добавляем требование краткости, чтобы ИИ не писал слишком длинные тексты
            system_msg = (
                system_instruction
                + "\n\n"
                + "Provide a concise final answer (1-3 sentences). "
                "If the question is outside allowed topics, output the refusal sentence exactly as instructed and nothing else."
            )

        # Выясняем, какую модель использовать для этого запроса
        chosen = self.user_model_choice.get(user_id, self.default_model)

        # Базовая проверка конфигурации ключей
        if not self.aiza_model.is_ready():
            return ("API ИИ не настроено. Обратитесь к администратору.", False, None)

        # Формируем итоговый список сообщений для отправки в API
        messages = self.build_messages(user_id, system_msg, prompt, chat_id)

        # Фиксируем запрос пользователя в базе данных прямо сейчас
        self.history_storage.save_message(user_id, "user", prompt, chat_id)
        
        # Запускаем генерацию. final_text будет накапливаться по мере поступления чанков.
        final_text, ok, parse_mode = self.aiza_model.stream_completion(
            model_id=chosen,
            messages=messages,
            progress_callback=progress_callback,
            raw_response=raw_response,
        )

        # Если ИИ выдал фразу отказа (не по теме), помечаем запрос как неуспешный
        if not system_prompt and REFUSAL_PHRASES[language] in (final_text or ""):
            self.history_storage.save_message(user_id, "assistant", REFUSAL_PHRASES[language], chat_id)
            return REFUSAL_PHRASES[language], False, None

        # Сохраняем успешный ответ ассистента для будущей истории
        self.history_storage.save_message(user_id, "assistant", final_text, chat_id)
        return final_text, ok, parse_mode
