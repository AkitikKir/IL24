#!/usr/bin/env python3
"""
Точка входа в приложение. 
Здесь происходит инициализация конфигурации, установка соединения с базой данных, 
создание необходимых сервисов и запуск бота.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Импорт основных компонентов бота
from bot_core.bot_app import BotApplication
from bot_core.config import BotConfig, setup_logging
from bot_core.database import Database
from bot_core.services.chat_service import ChatService
from bot_core.services.telethon_service import TelethonService
from bot_core.services.user_service import UserService
from bot_core.storage.history import history_storage_factory
from bot_core.storage.tickets import ticket_storage_factory


def main() -> None:
    """
    Основная функция запуска.
    Создаёт все зависимости и запускает процесс получения обновлений (polling).
    """
    # Устанавливаем уровень логирования INFO для отслеживания хода выполнения программы
    setup_logging(logging.INFO)

    # Определяем абсолютный путь к исполняемому файлу API сервера
    # Это позволяет запускать его независимо от текущей рабочей директории
    api_server_path = os.path.join(os.path.dirname(__file__), "api_server.py")
    
    # Запускаем API сервер в фоновом режиме как отдельный процесс ОС
    # Он необходим для обработки запросов от Telegram Mini App
    subprocess.Popen([sys.executable, api_server_path])
    logging.info("API сервер запущен как подпроцесс (api_server.py)")

    # Загружаем настройки из окружения через класс BotConfig
    # Сюда входят токены, ключи API и параметры подключения к БД
    config = BotConfig.load()

    # Инициализируем объект Database, передавая ему параметры подключения
    db = Database(config.db)
    # Выполняем физическое подключение к MySQL серверу
    db.connect()
    # Проверяем наличие всех необходимых таблиц (users, chat_history, tickets и др.)
    # Если таблиц нет, они будут созданы автоматически
    db.ensure_tables()

    # Инициализируем хранилища, используя абстракцию фабрики для работы с БД
    # Это отделяет логику хранения данных от логики бизнес-процессов
    history_storage = history_storage_factory(db)
    ticket_storage = ticket_storage_factory(db)
    
    # Создаем сервисы, которые будут управлять бизнес-логикой приложения
    # UserService управляет данными о пользователях (регистрация, баланс)
    user_service = UserService(db)
    # TelethonService используется для взаимодействия с Telegram API через клиентский протокол
    telethon_service = TelethonService(config)
    # ChatService координирует общение с ИИ моделями и сохранение истории
    chat_service = ChatService(config, history_storage, user_service)

    # Инициализируем главный класс приложения, который связывает все компоненты воедино
    # Сюда передаются все созданные ранее сервисы и хранилища (Dependency Injection)
    app = BotApplication(
        config=config,
        chat_service=chat_service,
        history_storage=history_storage,
        ticket_storage=ticket_storage,
        user_service=user_service,
        telethon_service=telethon_service,
    )
    
    # Запускаем основной цикл обработки сообщений Telegram (Polling)
    # Теперь бот начинает слушать входящие сообщения от пользователей
    logging.info("Бот запущен и готов к работе")
    app.run()


if __name__ == "__main__":
    # Вызов главной функции при прямом запуске скрипта
    main()
