"""
Главный класс приложения Telegram-бота.
Этот модуль объединяет все компоненты: конфигурацию, сервисы, базу данных и UI.
Здесь происходит регистрация обработчиков сообщений и запуск цикла получения обновлений.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
from typing import Dict, Optional

import telebot
from telebot import apihelper
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

from .config import BotConfig
from .services.chat_service import ChatService
from .services.telethon_service import TelethonService
from .services.user_service import UserService
from .storage.history import BaseHistoryStorage
from .storage.tickets import BaseTicketStorage
from .ui.messages import MESSAGES, REFUSAL_PHRASES
from .ui.keyboards import KeyboardFactory
from .utils.text import escape_md_v2


class BotApplication:
    """
    Инкапсулирует создание экземпляра TeleBot и регистрацию всех хендлеров.
    Отвечает за логику взаимодействия пользователя с ботом через интерфейс Telegram.
    """

    def __init__(
        self,
        config: BotConfig,
        chat_service: ChatService,
        history_storage: BaseHistoryStorage,
        ticket_storage: BaseTicketStorage,
        user_service: UserService,
        telethon_service: TelethonService,
    ):
        """Инициализация приложения с внедрением всех необходимых зависимостей."""
        self.config = config
        # Инициализация библиотеки pyTelegramBotAPI
        self.bot = telebot.TeleBot(config.telegram_token, parse_mode="HTML")
        self.chat_service = chat_service
        self.history_storage = history_storage
        self.ticket_storage = ticket_storage
        self.user_service = user_service
        self.telethon_service = telethon_service

        self.logger = logging.getLogger(self.__class__.__name__)
        # Состояние ответа администратора на тикеты
        self.admin_reply_state: Dict[int, int] = {}
        # Фабрика для создания клавиатур интерфейса
        self.keyboard_factory = KeyboardFactory(
            self.chat_service.get_language,
            self.chat_service.get_message,
            self.chat_service.get_current_model_label,
            self.chat_service.load_history,
            self.config.webapp_url,
        )

        # Проверка работоспособности токена при запуске
        self._validate_telegram_token()
        # Регистрация команд в меню Telegram
        self._setup_commands()
        # Регистрация обработчиков входящих сообщений и нажатий кнопок
        self._register_handlers()

    # ---------- Внутренние утилиты ----------
    def _setup_commands(self) -> None:
        """
        Регистрирует список команд (/start, /help, /settings) и описания бота.
        Данные берутся из словаря MESSAGES.
        """
        from telebot.types import BotCommand
        commands = [
            BotCommand("start", "Запустить бота / Главное меню"),
            BotCommand("help", "Показать справку"),
            BotCommand("settings", "Настройки и FAQ"),
        ]
        try:
            self.bot.set_my_commands(commands)
            
            # Установка расширенных описаний для страницы профиля бота
            desc_ru = MESSAGES["ru"]["bot_description"]
            short_ru = MESSAGES["ru"]["bot_short_description"]
            
            self.bot.set_my_description(desc_ru, language_code="ru")
            self.bot.set_my_short_description(short_ru, language_code="ru")
            
            # Настройки по умолчанию
            self.bot.set_my_description(desc_ru)
            self.bot.set_my_short_description(short_ru)
            
            self.logger.info("Команды и описания бота успешно зарегистрированы.")
        except Exception as e:
            self.logger.error("Ошибка при регистрации команд/описаний: %s", e)

    def _validate_telegram_token(self) -> None:
        """
        Проверяет валидность токена, вызывая метод get_me().
        Если токен неверный, приложение завершает работу с ошибкой.
        """
        try:
            info = self.bot.get_me()
            self.logger.info("Бот успешно авторизован: @%s", info.username)
        except apihelper.ApiTelegramException as e:
            self.logger.error("Ошибка Telegram API: %s", getattr(e, "result_json", e))
            sys.exit(1)
        except Exception as e:
            self.logger.exception("Непредвиденная ошибка валидации токена: %s", e)
            sys.exit(1)

    def _set_state(self, user_id: int, state: Optional[str]) -> None:
        """Сохраняет текущее состояние пользователя (например, 'chat' или 'creating_ticket')."""
        self.chat_service.user_states[user_id] = state

    def _get_state(self, user_id: int) -> Optional[str]:
        """Возвращает текущее состояние пользователя."""
        return self.chat_service.user_states.get(user_id)

    def _notify_admins_about_ticket(self, ticket_id: int, user_id: int, username: str, message_text: str) -> None:
        """
        Отправляет уведомление о новом тикете в административную группу.
        Добавляет кнопку для быстрого ответа администратора.
        """
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("Ответить на тикет", callback_data=f"reply_ticket_{ticket_id}"))
        text = f"📩 Новый тикет #{ticket_id}\nПользователь: @{username or user_id}\n\n{message_text[:800]}"

        try:
            msg = self.bot.send_message(self.config.admin_group_id, text, reply_markup=markup)
            self.logger.info("Отправлено уведомление в админ-группу (ID сообщения: %s).", getattr(msg, "message_id", None))
            return
        except Exception as e:
            self.logger.exception("Не удалось отправить тикет в группу: %s", e)

        # Резервный вариант отправки без кнопок, если возникла ошибка
        try:
            self.bot.send_message(self.config.admin_group_id, text)
        except Exception:
            self.logger.exception("Полный провал отправки уведомления администраторам.")

    def _edit_message_helper(self, text: str, chat_id: int, message_id: int, reply_markup=None, parse_mode: str = "HTML"):
        """
        Вспомогательный метод для универсального редактирования сообщений.
        Автоматически определяет, нужно ли редактировать текст сообщения или описание фото.
        """
        try:
            return self.bot.edit_message_text(
                text=text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception as e:
            error_msg = str(e).lower()
            
            # Обработка случая, когда сообщение — это изображение с подписью
            if "there is no text in the message to edit" in error_msg:
                try:
                    return self.bot.edit_message_caption(
                        caption=text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup, parse_mode=parse_mode
                    )
                except Exception as e2:
                    if "message is not modified" in str(e2).lower():
                        return
                    self.logger.error("Ошибка редактирования подписи фото: %s", e2)
                    return self.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            
            # Если текст не изменился — просто игнорируем ошибку
            if "message is not modified" in error_msg:
                return
                
            # Если сообщение не найдено — отправляем новое
            if "message to edit not found" in error_msg:
                return self.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)

            self.logger.error("Ошибка в _edit_message_helper: %s", e)
            try:
                return self.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception:
                raise e

    # ---------- Регистрация хендлеров ----------
    def _register_handlers(self) -> None:
        """
        Регистрирует все функции-обработчики событий.
        Разделено на обработку команд, нажатий кнопок (callback) и текстовых сообщений.
        """

        @self.bot.message_handler(commands=["start"])
        def start_handler(message, edit_id=None):
            """Обработка команды /start: регистрация и показ главного меню."""
            user_id = message.chat.id
            username = message.chat.username or (message.from_user.first_name if message.from_user else "User")
            # Регистрация пользователя в БД
            self.user_service.register_user(user_id, username)
            
            # Формирование кнопок и текста приветствия
            kb_inline, header = self.keyboard_factory.main_menu(user_id)
            lang = self.chat_service.get_language(user_id)
            welcome = MESSAGES.get(lang, MESSAGES["ru"])["start_long"]
            text = f"{MESSAGES.get(lang, MESSAGES['ru'])['start_header']}\n\n{welcome}\n\n{header}"
            
            # Попытка найти локальный файл баннера
            local_banner = None
            import os
            for ext in [".png", ".jpg", ".jpeg"]:
                path = f"assets/header{ext}"
                if os.path.exists(path):
                    local_banner = path
                    break
            
            # Если перешли назад из другого меню, пробуем отредактировать текущее сообщение
            if edit_id:
                try:
                    self._edit_message_helper(text, user_id, edit_id, reply_markup=kb_inline)
                    return
                except Exception:
                    # Если редактирование невозможно (например, нужно сменить тип сообщения), удаляем старое
                    try: self.bot.delete_message(user_id, edit_id)
                    except Exception: pass

            try:
                # Отправка приветственного баннера
                banner_url = "https://img.freepik.com/free-vector/artificial-intelligence-ai-robot-bot-concept-illustration_107791-23583.jpg"
                photo = open(local_banner, "rb") if local_banner else banner_url
                self.bot.send_photo(user_id, photo, caption=text, reply_markup=kb_inline)
                if local_banner: photo.close()
            except Exception:
                # Резервный вариант — текстовое сообщение
                self.bot.send_message(user_id, text, reply_markup=kb_inline)

        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            """Обработка всех нажатий на Inline-кнопки."""
            user_id = call.message.chat.id
            data = call.data or ""
            
            # Убираем "часики" загрузки на кнопке
            try: self.bot.answer_callback_query(call.id)
            except Exception: pass

            # Логика входа в режим чата
            if data == "start_chat":
                self._set_state(user_id, "chat")
                markup = InlineKeyboardMarkup(row_width=1)
                markup.add(InlineKeyboardButton(self.chat_service.get_message(user_id, "stop_chat"), callback_data="stop_chat"))
                self._edit_message_helper(
                    self.chat_service.get_message(user_id, "chat_started"),
                    user_id,
                    call.message.message_id,
                    reply_markup=markup,
                )
                return

            # Выход из режима чата
            if data == "stop_chat":
                self._set_state(user_id, None)
                start_handler(call.message, edit_id=call.message.message_id)
                return

            # Выбор ИИ модели
            if data == "choose_model":
                markup = InlineKeyboardMarkup(row_width=2)
                for safe_key, meta in self.chat_service.model_buttons.items():
                    markup.add(InlineKeyboardButton(meta["label"], callback_data=f"model_{safe_key}"))
                markup.add(InlineKeyboardButton(self.chat_service.get_message(user_id, "back"), callback_data="back"))
                self._edit_message_helper(
                    self.chat_service.get_message(user_id, "choose_model"), user_id, call.message.message_id, reply_markup=markup
                )
                return

            # Сохранение выбора модели
            if data.startswith("model_"):
                safe_key = data[len("model_") :]
                self.chat_service.clear_history(user_id) # Очистка истории при смене модели для корректного контекста

                meta = self.chat_service.model_buttons.get(safe_key)
                if not meta:
                    return

                self.chat_service.user_model_choice[user_id] = meta["model_id"]
                
                # Обновление меню выбора с отметкой текущей модели
                kb_models = InlineKeyboardMarkup(row_width=2)
                cur = self.chat_service.user_model_choice.get(user_id)
                for sk, m in self.chat_service.model_buttons.items():
                    label = ("✅ " if m["model_id"] == cur else "") + m["label"]
                    kb_models.add(InlineKeyboardButton(label, callback_data=f"model_{sk}"))
                kb_models.add(InlineKeyboardButton(self.chat_service.get_message(user_id, "back"), callback_data="back"))
                self._edit_message_helper(
                    "Выберите модель (текущая помечена ✅):", user_id, call.message.message_id, reply_markup=kb_models
                )
                return

            # Смена языка интерфейса
            if data == "choose_language":
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    InlineKeyboardButton("Русский", callback_data="lang_ru"),
                    InlineKeyboardButton("English", callback_data="lang_en"),
                )
                self._edit_message_helper(
                    self.chat_service.get_message(user_id, "choose_language_prompt"),
                    user_id,
                    call.message.message_id,
                    reply_markup=markup,
                )
                return

            if data.startswith("lang_"):
                language = data.split("_", 1)[1]
                self.user_service.update_language(user_id, language)
                try: self.bot.delete_message(user_id, call.message.message_id)
                except Exception: pass
                self.bot.send_message(user_id, self.chat_service.get_message(user_id, "language_changed"))
                start_handler(call.message)
                return

            # Навигация: Назад в главное меню
            if data == "back":
                self._set_state(user_id, None)
                start_handler(call.message, edit_id=call.message.message_id)
                return

            # Раздел настроек
            if data == "settings":
                kb, text = self.keyboard_factory.settings_menu(user_id)
                self._edit_message_helper(text, user_id, call.message.message_id, reply_markup=kb)
                return

            # Раздел помощи
            if data == "help":
                kb, title, desc = self.keyboard_factory.help_menu(user_id)
                self._edit_message_helper(f"{title}\n\n{desc}", user_id, call.message.message_id, reply_markup=kb)
                return

            # Раздел FAQ
            if data == "faq":
                lang = self.chat_service.get_language(user_id)
                text = MESSAGES.get(lang, MESSAGES["ru"])["faq_text"]
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(self.chat_service.get_message(user_id, "back"), callback_data="settings"))
                self._edit_message_helper(
                    f"<b>{self.chat_service.get_message(user_id, 'faq_title')}</b>\n\n{text}",
                    user_id,
                    call.message.message_id,
                    reply_markup=kb,
                )
                return

            # Очистка истории сообщений
            if data == "clear_history":
                self.chat_service.clear_history(user_id)
                self.bot.answer_callback_query(call.id, self.chat_service.get_message(user_id, "history_cleared"))
                kb, text = self.keyboard_factory.settings_menu(user_id)
                self._edit_message_helper(text, user_id, call.message.message_id, reply_markup=kb)
                return

            # Оценки качества ответа ИИ
            if data == "feedback_pos":
                self.user_service.save_feedback(user_id, call.message.message_id, True)
                try:
                    self.bot.answer_callback_query(call.id, "Спасибо! 😊")
                    self.bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
                except Exception: pass
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(self.chat_service.get_message(user_id, "stop_chat"), callback_data="stop_chat"))
                self.bot.send_message(user_id, self.chat_service.get_message(user_id, "feedback_positive"), reply_markup=markup)
                return

            if data == "feedback_neg":
                self.user_service.save_feedback(user_id, call.message.message_id, False)
                try:
                    self.bot.answer_callback_query(call.id, "Жаль... 😔")
                    self.bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
                except Exception: pass
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(self.chat_service.get_message(user_id, "stop_chat"), callback_data="stop_chat"))
                self.bot.send_message(user_id, self.chat_service.get_message(user_id, "feedback_negative"), reply_markup=markup)
                return

            # Связь с поддержкой (создание тикета)
            if data == "contact_support":
                lang = self.chat_service.get_language(user_id)
                self.bot.send_message(user_id, MESSAGES[lang]["ticket_prompt"])
                self._set_state(user_id, "creating_ticket")
                return

            # Обработка кнопки ответа администратора
            if data.startswith("reply_ticket_"):
                try: ticket_id = int(data.split("_")[-1])
                except Exception: return

                caller_id = call.from_user.id
                # Проверка прав (админ группы или главный админ)
                is_admin = (str(caller_id) == str(self.config.admin_user_id)) or (call.message.chat.id == self.config.admin_group_id)
                
                if not is_admin:
                    self.bot.answer_callback_query(call.id, "Недостаточно прав.")
                    return

                self.admin_reply_state[caller_id] = ticket_id
                self.bot.send_message(caller_id, f"Вы отвечаете на тикет #{ticket_id}. Отправьте текст ответа следующим сообщением.")
                return

        @self.bot.message_handler(func=lambda message: self._get_state(message.chat.id) == "creating_ticket")
        def create_ticket_handler(message):
            """Обработка текста обращения в поддержку."""
            user_id = message.chat.id
            username = message.from_user.username or str(user_id)
            ticket_text = message.text or ""
            ticket_id = self.ticket_storage.create_ticket(user_id, username, ticket_text)

            self._notify_admins_about_ticket(ticket_id or 0, user_id, username, ticket_text)
            
            lang = self.chat_service.get_language(user_id)
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton(self.chat_service.get_message(user_id, "back"), callback_data="back"))
            self.bot.send_message(user_id, MESSAGES[lang]["ticket_created"].format(ticket_id=ticket_id or "?"), reply_markup=markup)
            self._set_state(user_id, None)

        @self.bot.message_handler(func=lambda message: self._get_state(message.chat.id) == "chat")
        def text_handler(message):
            """Основной обработчик общения пользователя с ИИ."""
            user_id = message.chat.id
            prompt = (message.text or "").strip()
            
            if not prompt: return

            # Сообщение о начале генерации
            thinking = self.bot.send_message(user_id, "⏳ Обрабатываю ваш запрос…")
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton(self.chat_service.get_message(user_id, "stop_chat"), callback_data="stop_chat"))

            def progress_cb(partial_text, _parse_mode):
                """Функция обратного вызова для постепенного вывода текста (стриминг)."""
                try:
                    self.bot.send_chat_action(user_id, "typing")
                    # Экранируем сырой текст от ИИ для корректного отображения в MarkdownV2
                    escaped = escape_md_v2(partial_text or "(…)")
                    self._edit_message_helper(escaped, user_id, thinking.message_id, reply_markup=markup, parse_mode="MarkdownV2")
                except Exception: pass

            # Запрос к сервису чата для генерации ответа
            final_text, valid, _ = self.chat_service.process_query(user_id, prompt, progress_callback=progress_cb)
            
            if not valid:
                # Сообщение об ошибке/отказе также экранируем для MarkdownV2
                err_text = escape_md_v2(self.chat_service.get_message(user_id, "invalid_query"))
                self._edit_message_helper(err_text, user_id, thinking.message_id, reply_markup=markup, parse_mode="MarkdownV2")
                return

            # Добавление кнопок оценки к итоговому ответу
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(InlineKeyboardButton("👍", callback_data="feedback_pos"), InlineKeyboardButton("👎", callback_data="feedback_neg"))
            markup.add(InlineKeyboardButton(self.chat_service.get_message(user_id, "stop_chat"), callback_data="stop_chat"))

            final_escaped = escape_md_v2(final_text)
            try:
                self._edit_message_helper(final_escaped, user_id, thinking.message_id, reply_markup=markup, parse_mode="MarkdownV2")
            except Exception:
                self.bot.send_message(user_id, final_escaped, reply_markup=markup, parse_mode="MarkdownV2")

    # ---------- Запуск ----------
    def run(self) -> None:
        """
        Запускает бесконечный цикл получения обновлений (polling).
        Предусмотрена автоматическая обработка ошибок сети и перезапуск цикла.
        """
        while True:
            try:
                self.logger.info("Бот запущен и начинает прослушивание сообщений...")
                self.bot.polling(non_stop=True)
            except Exception as e:
                self.logger.exception("Ошибка в цикле polling. Перезапуск через 5 секунд...")
                time.sleep(5)
