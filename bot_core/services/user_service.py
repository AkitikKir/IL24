"""
Модуль для управления данными пользователей.
Обеспечивает регистрацию, смену языка интерфейса, проверку баланса и сохранение отзывов.
Взаимодействует с таблицами 'users' и 'feedback' в MySQL.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from ..database import Database


class UserService:
    """
    Класс-сервис для выполнения CRUD операций (создание, чтение, обновление, удаление) 
    над данными пользователей бота.
    Служит единственной точкой доступа к профилю пользователя из других частей системы.
    """

    def __init__(self, db: Database):
        """
        Инициализация сервиса с подключением к БД.
        Принимает экземпляр класса Database для выполнения SQL-запросов.
        """
        self.db = db
        # Настройка логгера для фиксации ошибок взаимодействия с базой данных
        self.logger = logging.getLogger(self.__class__.__name__)
        # Резервное хранилище настроек в оперативной памяти.
        # Используется только тогда, когда база данных временно недоступна, 
        # чтобы бот мог продолжать функционировать для текущих сессий.
        self._language_fallback: Dict[int, str] = {}

    def register_user(self, user_id: int, username: str) -> None:
        """
        Регистрирует нового пользователя в системе.
        - Если пользователь уже есть (проверка по PRIMARY KEY user_id), запрос игнорируется.
        - При успешной вставке устанавливается стартовый баланс 100 токенов и язык 'ru'.
        """
        if not self.db.connection:
            # Если БД недоступна, запоминаем пользователя хотя бы в ОЗУ (на время жизни процесса)
            self._language_fallback[user_id] = "ru"
            return
        try:
            with self.db.connection.cursor() as cursor:
                # INSERT IGNORE предотвращает ошибку 'Duplicate entry', если юзер уже в базе
                cursor.execute(
                    "INSERT IGNORE INTO users (user_id, username, language, tokens) VALUES (%s, %s, %s, %s)",
                    (user_id, username, "ru", 100),
                )
        except Exception:
            # Логируем детали ошибки (напр. таймаут или синтаксис SQL)
            self.logger.exception("Ошибка при регистрации пользователя в MySQL.")

    def update_language(self, user_id: int, language: str) -> None:
        """
        Изменяет выбранный язык интерфейса пользователя в базе данных.
        Вызывается, когда пользователь нажимает кнопки смены языка в настройках бота.
        """
        if not self.db.connection:
            self._language_fallback[user_id] = language
            return
        try:
            with self.db.connection.cursor() as cursor:
                # Обновляем поле language для конкретного ID
                cursor.execute("UPDATE users SET language = %s WHERE user_id = %s", (language, user_id))
        except Exception:
            self.logger.exception("Ошибка при обновлении языка пользователя.")

    def get_language(self, user_id: int) -> str:
        """
        Возвращает код языка (ru/en), который предпочитает пользователь.
        Используется для локализации всех исходящих текстовых сообщений.
        """
        if not self.db.connection:
            # Сначала проверяем ОЗУ, если БД лежит
            return self._language_fallback.get(user_id, "ru")
        try:
            with self.db.connection.cursor() as cursor:
                # Пытаемся достать язык из таблицы профилей
                cursor.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                if not row:
                    # Если юзер еще не зарегистрирован, возвращаем стандарт
                    return "ru"
                # Обработка возможного разного регистра ключей в зависимости от настроек MySQL драйвера
                return row.get("language") or row.get("Language") or row.get("LANGUAGE") or "ru"
        except Exception:
            self.logger.exception("Ошибка при получении языка пользователя.")
            return "ru"

    def get_balance(self, user_id: int) -> int:
        """
        Получает текущее количество токенов на счету пользователя.
        Токены могут списываться за сложные запросы к мощным ИИ моделям.
        """
        if not self.db.connection:
            # Возвращаем 100 как 'безопасное' значение, чтобы не блокировать функции при сбое БД
            return 100 
        try:
            with self.db.connection.cursor() as cursor:
                cursor.execute("SELECT tokens FROM users WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                if not row:
                    return 0
                # Извлекаем значение из словаря результата запроса
                return row.get("tokens") or row.get("Tokens") or row.get("TOKENS") or 0
        except Exception:
            self.logger.exception("Ошибка при получении баланса пользователя.")
            return 0

    def save_feedback(self, user_id: int, message_id: int, is_positive: bool) -> bool:
        """
        Сохраняет фидбек (лайк/дизлайк) к конкретному сообщению ИИ.
        Помогает администраторам видеть, какие ответы нравятся пользователям.
        Возвращает True при успехе и False при ошибке.
        """
        if not self.db.connection:
            return False
        try:
            with self.db.connection.cursor() as cursor:
                # Добавляем новую запись в таблицу отзывов
                cursor.execute(
                    "INSERT INTO feedback (user_id, message_id, is_positive) VALUES (%s, %s, %s)",
                    (user_id, message_id, is_positive),
                )
            return True
        except Exception:
            self.logger.exception("Ошибка при сохранении отзыва пользователя.")
            return False
