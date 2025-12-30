"""
Модуль для работы с базой данных MySQL.
Обеспечивает подключение, создание таблиц и управление соединениями.
"""

from __future__ import annotations

import atexit
import logging
from typing import Optional

import pymysql

from .config import DbSettings


class Database:
    """
    Класс-обертка для управления соединением с MySQL через библиотеку PyMySQL.
    Реализует ленивое подключение и автоматическое переподключение при обрыве связи.
    Это гарантирует стабильную работу бота даже при временных сбоях сети с БД.
    """

    def __init__(self, settings: DbSettings):
        """
        Инициализация объекта базы данных.
        Сохраняет настройки и подготавливает внутренние переменные для будущего подключения.
        """
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        # По умолчанию соединение отсутствует (None)
        self._connection: Optional[pymysql.Connection] = None

    @property
    def connection(self) -> Optional[pymysql.Connection]:
        """
        Умное свойство для получения активного объекта соединения.
        1. Если соединения еще не было — вызывает connect().
        2. Если соединение было — проверяет его "живучесть" через ping().
        3. Если ping не прошел — переподключается.
        """
        if self._connection is None:
            self.connect()
        else:
            try:
                # Проверка активности соединения (ping). Параметр reconnect=True 
                # заставляет библиотеку попробовать восстановить связь внутри метода.
                self._connection.ping(reconnect=True)
            except Exception:
                self.logger.warning("Потеряно соединение с MySQL. Пробуем переподключиться...")
                self._connection = None
                self.connect()
        return self._connection

    def connect(self) -> None:
        """
        Устанавливает физическое соединение с MySQL сервером.
        - Использует кодировку utf8mb4 (обязательно для хранения эмодзи из Telegram).
        - Использует DictCursor (результаты запросов будут словарями, а не кортежами).
        - Включает autocommit для немедленного сохранения изменений без явного conn.commit().
        """
        if self._connection:
            return
        try:
            # Пытаемся подключиться к серверу с заданными параметрами из конфига
            self._connection = pymysql.connect(
                host=self.settings.host,
                user=self.settings.user,
                password=self.settings.password,
                database=self.settings.database,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True, # Каждая SQL операция будет автоматически зафиксирована в БД
            )
            self.logger.info("Соединение с MySQL успешно установлено.")
            # Регистрация обработчика завершения работы. 
            # Функция self.close будет вызвана Python'ом автоматически при выходе из процесса.
            atexit.register(self.close)
        except Exception:
            self.logger.exception("КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к MySQL серверу.")
            self._connection = None

    def close(self) -> None:
        """
        Безопасно закрывает соединение с базой данных.
        Вызывается при завершении работы программы или при необходимости принудительного разрыва.
        """
        if not self._connection:
            return
        try:
            self._connection.close()
            self.logger.info("Соединение с MySQL успешно закрыто.")
        except Exception:
            self.logger.exception("Ошибка при попытке закрытия соединения с MySQL.")
        finally:
            # В любом случае сбрасываем ссылку на объект соединения
            self._connection = None

    def ensure_tables(self) -> None:
        """
        Метод инициализации схемы данных.
        Выполняет серию запросов 'CREATE TABLE IF NOT EXISTS'.
        Это позволяет запускать бот на "чистой" базе без ручного создания таблиц.
        """
        # Если подключиться не удалось, мы не можем создавать таблицы
        if not self.connection:
            self.logger.info("База данных недоступна — создание таблиц пропущено.")
            return
        try:
            # Открываем курсор для выполнения SQL команд
            with self.connection.cursor() as cursor:
                # 1. Таблица истории сообщений (логи диалогов)
                # user_id - BIGINT для поддержки длинных Telegram ID
                # role - роль автора (user, assistant, system)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        role VARCHAR(16) NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) CHARACTER SET utf8mb4;
                    """
                )
                
                # 2. Таблица профилей пользователей
                # tokens - количество доступных токенов для ИИ запросов
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        language VARCHAR(8) DEFAULT 'ru',
                        tokens INT DEFAULT 100
                    ) CHARACTER SET utf8mb4;
                    """
                )
                
                # 3. Таблица тикетов (обращения в поддержку)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tickets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT,
                        username VARCHAR(255),
                        message TEXT,
                        status VARCHAR(32) DEFAULT 'open',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) CHARACTER SET utf8mb4;
                    """
                )
                
                # 4. Таблица фидбека (лайки/дизлайки ответов)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT,
                        message_id INT,
                        is_positive BOOLEAN,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) CHARACTER SET utf8mb4;
                    """
                )
                
                # 5. Таблица чатов (группировка для Mini App)
                # Позволяет пользователю иметь несколько независимых диалогов
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chats (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        title VARCHAR(255) DEFAULT 'Новый чат',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_user_id (user_id)
                    ) CHARACTER SET utf8mb4;
                    """
                )
                
                # 6. Миграция: добавляем chat_id в историю сообщений
                # Это необходимо для связки сообщений с конкретным чатом из таблицы chats
                cursor.execute(
                    """
                    ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS chat_id INT DEFAULT NULL;
                    """
                )
                self.logger.info("Все необходимые таблицы БД успешно проинициализированы.")
        except Exception:
            self.logger.exception("ФАТАЛЬНАЯ ОШИБКА: Не удалось инициализировать структуру таблиц.")
