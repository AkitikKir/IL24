"""
Модуль для создания клавиатур интерфейса Telegram бота.
Использует библиотеку telebot для формирования Inline-кнопок и меню.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..ui.messages import MESSAGES
from ..utils.text import truncate


class KeyboardFactory:
    """
    Фабрика для генерации клавиатур различных экранов бота.
    Реализует паттерн 'Фабрика' для централизованного управления UI-элементами.
    """

    def __init__(self, get_language, get_message, get_current_model_label, load_history, webapp_url: str = ""):
        """
        Инициализация фабрики с внедрением необходимых функций-зависимостей.
        Это позволяет клавиатурам динамически подстраиваться под язык и выбор модели пользователя.
        """
        self.get_language = get_language
        self.get_message = get_message
        self.get_current_model_label = get_current_model_label
        self.load_history = load_history
        self.webapp_url = webapp_url

    def main_menu(self, user_id: int) -> Tuple[InlineKeyboardMarkup, str]:
        """
        Собирает главное меню бота и формирует информационный заголовок.
        В заголовке отображается текущая выбранная модель и название сервиса.
        """
        # Инициализируем Inline-клавиатуру с шириной в 2 кнопки в ряд
        kb = InlineKeyboardMarkup(row_width=2)
        
        # Получаем актуальные данные для отображения в интерфейсе
        model_label = self.get_current_model_label(user_id)
        lang = self.get_language(user_id) or "ru"
        header = f"Модель: {model_label}  •  ИЛ24 💡"
        
        # Добавляем кнопки управления чатом и выбора модели
        kb.add(
            InlineKeyboardButton(self.get_message(user_id, "start_chat"), callback_data="start_chat"),
            InlineKeyboardButton(self.get_message(user_id, "choose_model"), callback_data="choose_model"),
        )
        # Добавляем кнопки выбора языка и раздела помощи
        kb.add(
            InlineKeyboardButton(self.get_message(user_id, "choose_language"), callback_data="choose_language"),
            InlineKeyboardButton(self.get_message(user_id, "help_title"), callback_data="help"),
        )
        # Добавляем кнопки связи с поддержкой и настроек профиля
        kb.add(
            InlineKeyboardButton(self.get_message(user_id, "gethelp"), callback_data="contact_support"),
            InlineKeyboardButton(self.get_message(user_id, "settbut"), callback_data="settings"),
        )
        return kb, header

    def help_menu(self, user_id: int) -> Tuple[InlineKeyboardMarkup, str, str]:
        """
        Формирует меню раздела помощи.
        Возвращает клавиатуру с кнопкой 'Назад' и тексты заголовка и описания.
        """
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(self.get_message(user_id, "back"), callback_data="back"))
        
        # Получаем локализованные тексты помощи
        title = self.get_message(user_id, "help_title")
        desc = self.get_message(user_id, "help_text")
        return kb, title, desc

    def settings_menu(self, user_id: int) -> Tuple[InlineKeyboardMarkup, str]:
        """
        Собирает меню настроек пользователя.
        Позволяет просматривать FAQ, очищать историю диалогов и возвращаться назад.
        """
        kb = InlineKeyboardMarkup(row_width=1)
        # Кнопки для перехода к FAQ и полной очистки контекста ИИ
        kb.add(
            InlineKeyboardButton(self.get_message(user_id, "faq_title"), callback_data="faq"),
            InlineKeyboardButton(self.get_message(user_id, "history_cleared"), callback_data="clear_history"),
            InlineKeyboardButton(self.get_message(user_id, "back"), callback_data="back"),
        )
        
        # Формируем заголовок и описание раздела настроек
        title = self.get_message(user_id, "settings_title")
        desc = self.get_message(user_id, "settings_description")
        return kb, f"<b>{title}</b>\n\n{desc}"

    @staticmethod
    def single_back(user_id: int, get_message) -> InlineKeyboardMarkup:
        """
        Универсальный статический метод для создания одиночной кнопки возврата.
        Используется на экранах, где не требуется сложная навигация.
        """
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(get_message(user_id, "back"), callback_data="back"))
        return kb
