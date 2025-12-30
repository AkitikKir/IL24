
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
# Это необходимо для получения ключей API и настроек базы данных
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

# Проверка загрузки настроек БД из окружения
if os.environ.get("DB_USER"):
    print(f"Пользователь базы данных из окружения: {os.environ.get('DB_USER')}")
else:
    print("ПРЕДУПРЕЖДЕНИЕ: DB_USER не найден в окружении после load_dotenv")

# Установка временного токена Telegram, если он отсутствует
# Это позволяет загрузить BotConfig для нужд API без ошибок валидации
if not os.environ.get("TELEGRAM_TOKEN"):
    os.environ["TELEGRAM_TOKEN"] = "dummy_token_for_api"

from bot_core.config import BotConfig, setup_logging
from bot_core.database import Database
from bot_core.services.chat_service import ChatService
from bot_core.services.user_service import UserService
from bot_core.storage.history import history_storage_factory
from bot_core.services.model_clients import AVAILABLE_MODELS

# Настройка системы логирования для API сервера
# Позволяет отслеживать входящие запросы и возникающие ошибки в консоли
setup_logging(logging.INFO)
logger = logging.getLogger("APIServer")

# Загрузка конфигурации бота из переменных окружения
# Содержит API ключи для моделей и настройки подключения к базе данных
config = BotConfig.load()

# Инициализация базы данных и необходимых сервисов
# База данных используется для хранения истории чатов и метаданных пользователей
db = Database(config.db)
# Устанавливаем соединение с сервером MySQL
db.connect()
# Проверяем наличие всех таблиц, создаем их при необходимости
db.ensure_tables()

# Фабрика для создания хранилища истории сообщений.
# Позволяет прозрачно работать с сохранением и получением логов переписки.
history_storage = history_storage_factory(db)
# Сервис для управления данными пользователей: регистрация, проверка баланса, роли.
user_service = UserService(db)
# Сервис для обработки логики чатов и взаимодействия с различными ИИ моделями (OpenAI, Anthropic и др.)
chat_service = ChatService(config, history_storage, user_service)

# Создание основного экземпляра приложения FastAPI
# Этот объект будет обрабатывать все HTTP запросы от фронтенда Mini App
app = FastAPI()

# Настройка CORS (Cross-Origin Resource Sharing)
# Необходима для того, чтобы браузер разрешал запросы к API с другого домена/порта (фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Разрешаем доступ со всех источников
    allow_credentials=True,
    allow_methods=["*"], # Разрешаем любые HTTP методы (GET, POST и т.д.)
    allow_headers=["*"], # Разрешаем любые HTTP заголовки
)

# Подключение статических файлов для фронтенда мини-приложения
# Позволяет раздавать HTML/JS/CSS файлы прямо через API сервер по пути /mini-app
static_path = os.path.join(os.path.dirname(__file__), "experimental", "mini-app")
if os.path.exists(static_path):
    # Монтируем директорию со статикой к приложению FastAPI
    app.mount("/mini-app", StaticFiles(directory=static_path, html=True), name="mini-app")

# Схема данных для запроса на отправку сообщения в чат (Pydantic модель)
class ChatRequest(BaseModel):
    user_id: int   # Telegram ID пользователя
    prompt: str    # Текст сообщения
    model_id: str  # Идентификатор выбранной ИИ модели (например, 'gpt-4')
    chat_id: Optional[int] = None # ID существующего чата или None для нового

# Схема данных для ответа на сообщение (Pydantic модель)
class ChatResponse(BaseModel):
    response: str  # Текст ответа от ИИ
    success: bool  # Флаг успешного выполнения операции

# Схема данных для создания нового чата
class CreateChatRequest(BaseModel):
    user_id: int   # Telegram ID владельца чата
    title: Optional[str] = "Новый чат" # Опциональное название чата

# Схема данных для переименования чата
class RenameChatRequest(BaseModel):
    user_id: int   # Telegram ID пользователя
    chat_id: int   # Внутренний ID чата в БД
    title: str     # Новое название

# Эндпоинт для получения списка доступных ИИ моделей
@app.get("/api/models")
async def get_models():
    """Возвращает список ID и названий всех доступных моделей."""
    return [{"id": k, "label": v} for k, v in AVAILABLE_MODELS.items()]

# Эндпоинт для получения списка чатов пользователя
@app.get("/api/chats")
async def get_chats(user_id: int):
    """Возвращает историю всех чатов для конкретного пользователя."""
    try:
        chats = history_storage.get_chats(user_id)
        return chats
    except Exception as e:
        logger.exception("Ошибка в эндпоинте get_chats")
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для создания нового чата
@app.post("/api/chats/create")
async def create_chat(request: CreateChatRequest):
    """Создает новую запись чата в базе данных и возвращает его ID."""
    try:
        chat_id = history_storage.create_chat(request.user_id, request.title)
        if chat_id > 0:
            return {"success": True, "chat_id": chat_id}
        return {"success": False, "error": "Не удалось создать чат"}
    except Exception as e:
        logger.exception("Ошибка в эндпоинте create_chat")
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для удаления чата
@app.post("/api/chats/delete")
async def delete_chat(user_id: int, chat_id: int):
    """Удаляет чат и все связанные с ним сообщения."""
    try:
        success = history_storage.delete_chat(user_id, chat_id)
        return {"success": success}
    except Exception as e:
        logger.exception("Ошибка в эндпоинте delete_chat")
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для изменения названия чата
@app.post("/api/chats/rename")
async def rename_chat(request: RenameChatRequest):
    """Обновляет заголовок существующего чата."""
    try:
        success = history_storage.rename_chat(request.user_id, request.chat_id, request.title)
        return {"success": success}
    except Exception as e:
        logger.exception("Ошибка в эндпоинте rename_chat")
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для получения истории сообщений в конкретном чате
@app.get("/api/history")
async def get_history(user_id: int, chat_id: Optional[int] = None):
    """Загружает последние сообщения из базы данных для отображения в UI."""
    try:
        history = chat_service.load_history(user_id, 100, chat_id)
        return [{"role": h[0], "content": h[1]} for h in history]
    except Exception as e:
        logger.exception("Ошибка в эндпоинте history")
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для очистки истории сообщений
@app.post("/api/history/clear")
async def clear_history(user_id: int, chat_id: Optional[int] = None):
    """Удаляет все сообщения из чата, но сохраняет саму запись чата."""
    try:
        chat_service.clear_history(user_id, chat_id)
        return {"success": True}
    except Exception as e:
        logger.exception("Ошибка в эндпоинте clear history")
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для отправки промпта и получения ответа от ИИ
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Обрабатывает запрос пользователя:
    1. Устанавливает выбранную модель.
    2. Отправляет запрос в chat_service.
    3. Возвращает текстовый ответ от ИИ.
    """
    try:
        # Сохранение выбора модели пользователем
        chat_service.user_model_choice[request.user_id] = request.model_id
        
        # Процесс генерации ответа
        final_text, ok, parse_mode = chat_service.process_query(
            user_id=request.user_id,
            prompt=request.prompt,
            raw_response=True,
            chat_id=request.chat_id
        )
        
        return ChatResponse(response=final_text, success=ok)
    except Exception as e:
        logger.exception("Ошибка в эндпоинте chat")
        raise HTTPException(status_code=500, detail=str(e))

# Запуск сервера uvicorn
if __name__ == "__main__":
    import uvicorn
    # Используем порт 8392 для работы API
    port = 8392
    print(f"Запуск сервера на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
