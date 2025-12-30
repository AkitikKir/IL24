"""
Модуль для загрузки конфигурации из переменных окружения и настройки логирования.
Здесь определены структуры данных для всех настроек бота: API ключи, БД, Telethon и др.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional


def setup_logging(level: int = logging.INFO) -> None:
    """
    Единая точка настройки логирования для всего проекта.
    Устанавливает формат вывода: время [уровень] имя_модуля: сообщение.
    Это помогает в отладке и мониторинге состояния бота в реальном времени.
    """
    # Конфигурируем базовый логгер с заданным уровнем и человекочитаемым форматом
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@dataclass
class TelethonSettings:
    """
    Настройки для библиотеки Telethon (Telegram Client API).
    Telethon используется для расширенных функций, которые недоступны обычному Bot API,
    например, программная смена темы чата или работа от лица пользователя.
    """

    api_id: Optional[str]     # Уникальный идентификатор приложения (получается на my.telegram.org)
    api_hash: Optional[str]   # Секретный хеш приложения (получается на my.telegram.org)
    session_name: str         # Имя файла .session, где хранится состояние авторизации клиента

    @property
    def is_configured(self) -> bool:
        """
        Проверяет, заполнены ли все необходимые поля для инициализации Telethon.
        Возвращает True, если api_id и api_hash заданы, иначе False.
        """
        return bool(self.api_id and self.api_hash)


@dataclass
class DbSettings:
    """
    Объект-контейнер для хранения параметров подключения к базе данных MySQL.
    Используется классом Database для установки сетевого соединения.
    """

    host: str      # IP-адрес или доменное имя сервера базы данных
    user: str      # Имя пользователя для аутентификации в MySQL
    password: str  # Пароль пользователя для доступа к таблицам
    database: str  # Имя конкретной схемы (базы данных), в которой лежат таблицы бота


@dataclass
class BotConfig:
    """
    Глобальный класс конфигурации, объединяющий все настройки приложения.
    Использует паттерн Singleton (через метод load) для доступа к настройкам из любой части кода.
    """

    telegram_token: str       # Токен бота, выданный @BotFather, для работы через aiogram
    openrouter_key: str       # Ключ для доступа к API OpenRouter (агрегатор нейросетей)
    openrouter_base_url: str  # URL адрес API OpenRouter (обычно стандартный)
    yandex_folder_id: str     # Идентификатор каталога в Yandex Cloud (для работы с YandexGPT)
    yandex_auth: str          # Токен или API ключ для авторизации в сервисах Yandex Cloud
    admin_group_id: int       # ID группы в Telegram, куда бот пересылает важные уведомления
    admin_user_id: Optional[str] # ID пользователя-владельца бота для административного доступа
    service_name: str         # Текстовое название бота, используемое в сообщениях и заголовках
    max_history_messages: int # Лимит на количество хранимых сообщений для контекста ИИ
    webapp_url: str           # Базовая ссылка на Mini App фронтенд для генерации кнопок
    telethon: TelethonSettings # Вложенный объект с настройками Telethon клиента
    db: DbSettings            # Вложенный объект с настройками подключения к MySQL

    @classmethod
    def load(cls) -> "BotConfig":
        """
        Загружает все параметры из переменных окружения (Environment Variables).
        Это позволяет безопасно хранить секреты вне исходного кода (например, в .env файле).
        Если критически важный параметр TELEGRAM_TOKEN не найден, программа прекращает работу.
        """
        # Извлекаем токен из окружения и очищаем его от случайных пробелов
        telegram_token = os.environ.get("TELEGRAM_TOKEN", "").strip()
        if not telegram_token:
            # Логируем фатальную ошибку, если без токена запуск невозможен
            logging.error("TELEGRAM_TOKEN не задан. Установите переменную окружения и перезапустите бот.")
            sys.exit(1)

        # Собираем настройки для Telethon клиента
        telethon_settings = TelethonSettings(
            api_id=os.environ.get("TELETHON_API_ID"),
            api_hash=os.environ.get("TELETHON_API_HASH"),
            session_name=os.environ.get("TELETHON_SESSION", "telethon_session"),
        )

        # Собираем настройки для подключения к базе данных MySQL
        db_settings = DbSettings(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "tg_bot"),
        )

        # Создаем и возвращаем итоговый объект конфигурации со всеми полями
        return cls(
            telegram_token=telegram_token,
            openrouter_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
            openrouter_base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
            yandex_folder_id=os.environ.get("YANDEX_FOLDER_ID", "").strip(),
            yandex_auth=os.environ.get("YANDEX_AUTH", "").strip(),
            admin_group_id=int(os.environ.get("ADMIN_GROUP_ID", "-1002983110493")),
            admin_user_id=os.environ.get("ADMIN_USER_ID"),
            service_name=os.environ.get("SERVICE_NAME", "").strip(),
            max_history_messages=int(os.environ.get("MAX_HISTORY_MESSAGES", "20")),
            webapp_url=os.environ.get("WEBAPP_URL", "http://localhost:8392/mini-app").strip(),
            telethon=telethon_settings,
            db=db_settings,
        )
