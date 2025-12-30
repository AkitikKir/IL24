"""
Модуль для управления историей диалогов и чатами.
Обеспечивает сохранение сообщений в базу данных (MySQL) или оперативную память (Memory).
Поддерживает функционал Mini App через управление списком чатов.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from ..database import Database

# Определение типа для строки истории: кортеж (роль, содержание)
HistoryRow = Tuple[str, str]  # (role, content)


class BaseHistoryStorage:
    """
    Абстрактный интерфейс для работы с историей сообщений.
    Определяет методы, которые должны реализовать конкретные хранилища (БД или RAM).
    """

    def save_message(self, user_id: int, role: str, content: str, chat_id: Optional[int] = None) -> None:
        """Сохраняет новое сообщение в историю."""
        raise NotImplementedError

    def load_history(self, user_id: int, limit: int, chat_id: Optional[int] = None) -> List[HistoryRow]:
        """Загружает последние N сообщений диалога."""
        raise NotImplementedError

    def clear_history(self, user_id: int, chat_id: Optional[int] = None) -> None:
        """Удаляет все сообщения для пользователя или конкретного чата."""
        raise NotImplementedError

    def get_chats(self, user_id: int) -> List[dict]:
        """Возвращает список всех чатов пользователя (для Mini App)."""
        raise NotImplementedError

    def create_chat(self, user_id: int, title: str = "Новый чат") -> int:
        """Создает новую запись чата в системе."""
        raise NotImplementedError

    def delete_chat(self, user_id: int, chat_id: int) -> bool:
        """Удаляет чат и всю связанную с ним историю."""
        raise NotImplementedError

    def rename_chat(self, user_id: int, chat_id: int, title: str) -> bool:
        """Меняет заголовок существующего чата."""
        raise NotImplementedError


class DbHistoryStorage(BaseHistoryStorage):
    """
    Реализация хранилища истории в базе данных MySQL.
    Обеспечивает персистентность данных между перезапусками бота.
    """

    def __init__(self, db: Database):
        """Инициализация с внедрением объекта базы данных."""
        self.db = db
        self.logger = logging.getLogger(self.__class__.__name__)

    def save_message(self, user_id: int, role: str, content: str, chat_id: Optional[int] = None) -> None:
        """
        Сохраняет сообщение в таблицу chat_history.
        Если указан chat_id, также обновляет время последнего изменения этого чата.
        """
        if not self.db.connection:
            return
        try:
            with self.db.connection.cursor() as cursor:
                # Вставка записи о новом сообщении
                cursor.execute(
                    "INSERT INTO chat_history (user_id, role, content, chat_id) VALUES (%s, %s, %s, %s)",
                    (user_id, role, content, chat_id),
                )
                # Если это сообщение относится к конкретному чату в Mini App, обновляем дату его активности
                if chat_id:
                    cursor.execute(
                        "UPDATE chats SET updated_at = NOW() WHERE id = %s AND user_id = %s",
                        (chat_id, user_id),
                    )
        except Exception:
            self.logger.exception("Критическая ошибка: не удалось сохранить историю в БД.")

    def load_history(self, user_id: int, limit: int, chat_id: Optional[int] = None) -> List[HistoryRow]:
        """
        Загружает последние сообщения из БД.
        Сортирует по дате создания, чтобы ИИ получал сообщения в правильном порядке.
        """
        if not self.db.connection:
            return []
        try:
            with self.db.connection.cursor() as cursor:
                # Сложный запрос с подзапросом для получения последних N строк и их последующей сортировки
                if chat_id:
                    cursor.execute(
                        "SELECT role, content FROM (SELECT role, content, created_at FROM chat_history WHERE user_id = %s AND chat_id = %s ORDER BY created_at DESC LIMIT %s) as sub ORDER BY created_at ASC",
                        (user_id, chat_id, limit),
                    )
                else:
                    cursor.execute(
                        "SELECT role, content FROM (SELECT role, content, created_at FROM chat_history WHERE user_id = %s AND chat_id IS NULL ORDER BY created_at DESC LIMIT %s) as sub ORDER BY created_at ASC",
                        (user_id, limit),
                    )
                rows = cursor.fetchall()
                if not rows:
                    return []
                
                # Приведение результатов к стандартному списку кортежей
                result = []
                for r in rows:
                    role = r.get("role") or r.get("Role") or r.get("ROLE") or ""
                    content = r.get("content") or r.get("Content") or r.get("CONTENT") or ""
                    result.append((role, content))
                return result
        except Exception:
            self.logger.exception("Ошибка загрузки истории из БД.")
            return []

    def clear_history(self, user_id: int, chat_id: Optional[int] = None) -> None:
        """Удаляет записи из таблицы chat_history для освобождения места или сброса контекста ИИ."""
        if not self.db.connection:
            return
        try:
            with self.db.connection.cursor() as cursor:
                if chat_id:
                    cursor.execute("DELETE FROM chat_history WHERE user_id = %s AND chat_id = %s", (user_id, chat_id))
                else:
                    cursor.execute("DELETE FROM chat_history WHERE user_id = %s AND chat_id IS NULL", (user_id,))
        except Exception:
            self.logger.exception("Ошибка очистки истории в БД.")

    def get_chats(self, user_id: int) -> List[dict]:
        """
        Получает список всех доступных чатов пользователя.
        Всегда добавляет виртуальный 'Telegram Bot' чат, если он не существует в БД.
        """
        if not self.db.connection:
            return []
        try:
            with self.db.connection.cursor() as cursor:
                # Получаем список созданных пользователем чатов
                cursor.execute(
                    "SELECT id, title, created_at, updated_at FROM chats WHERE user_id = %s ORDER BY updated_at DESC",
                    (user_id,),
                )
                rows = cursor.fetchall()
                chats = [{"id": r["id"], "title": r["title"], "created_at": str(r["created_at"]), "updated_at": str(r["updated_at"])} for r in rows]
                
                # Формируем объект главного чата (тот, что идет напрямую через Telegram бота)
                main_chat = {
                    "id": None, 
                    "title": "Telegram Bot (Main)", 
                    "created_at": "", 
                    "updated_at": "",
                    "is_main": True
                }
                
                return [main_chat] + chats
        except Exception:
            self.logger.exception("Ошибка при получении списка чатов.")
            return []

    def create_chat(self, user_id: int, title: str = "Новый чат") -> int:
        """Создает новую запись в таблице chats и возвращает её ID."""
        if not self.db.connection:
            return -1
        try:
            with self.db.connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO chats (user_id, title) VALUES (%s, %s)",
                    (user_id, title),
                )
                return cursor.lastrowid # Возвращаем AUTO_INCREMENT идентификатор
        except Exception:
            self.logger.exception("Ошибка создания нового чата.")
            return -1

    def delete_chat(self, user_id: int, chat_id: int) -> bool:
        """Удаляет чат и очищает все сообщения, привязанные к нему."""
        if not self.db.connection:
            return False
        try:
            with self.db.connection.cursor() as cursor:
                # Сначала удаляем сообщения (внешние ключи обычно настроены, но делаем явно)
                cursor.execute("DELETE FROM chat_history WHERE user_id = %s AND chat_id = %s", (user_id, chat_id))
                # Затем удаляем сам чат
                cursor.execute("DELETE FROM chats WHERE id = %s AND user_id = %s", (chat_id, user_id))
                return True
        except Exception:
            self.logger.exception("Ошибка при удалении чата.")
            return False

    def rename_chat(self, user_id: int, chat_id: int, title: str) -> bool:
        """Обновляет заголовок чата по его ID."""
        if not self.db.connection:
            return False
        try:
            with self.db.connection.cursor() as cursor:
                cursor.execute("UPDATE chats SET title = %s WHERE id = %s AND user_id = %s", (title, chat_id, user_id))
                return True
        except Exception:
            self.logger.exception("Ошибка переименования чата.")
            return False


class MemoryHistoryStorage(BaseHistoryStorage):
    """
    Запасное хранилище в оперативной памяти (RAM).
    Используется как fallback, если база данных MySQL недоступна.
    Данные будут потеряны при перезагрузке сервера.
    """

    def __init__(self):
        """Инициализация словарей для хранения данных в ОЗУ."""
        self.histories: Dict[int, Dict[Optional[int], List[HistoryRow]]] = {}
        self.chats: Dict[int, List[dict]] = {}
        self.chat_id_counter = 0

    def save_message(self, user_id: int, role: str, content: str, chat_id: Optional[int] = None) -> None:
        """Сохраняет сообщение в вложенный словарь в памяти."""
        if user_id not in self.histories:
            self.histories[user_id] = {}
        if chat_id not in self.histories[user_id]:
            self.histories[user_id][chat_id] = []
        self.histories[user_id][chat_id].append((role, content))
        # Ограничиваем размер истории в памяти для предотвращения утечек
        if len(self.histories[user_id][chat_id]) > 100:
            self.histories[user_id][chat_id] = self.histories[user_id][chat_id][-100:]

    def load_history(self, user_id: int, limit: int, chat_id: Optional[int] = None) -> List[HistoryRow]:
        """Возвращает срез списка сообщений из памяти."""
        if user_id not in self.histories or chat_id not in self.histories[user_id]:
            return []
        return self.histories[user_id][chat_id][-limit:]

    def clear_history(self, user_id: int, chat_id: Optional[int] = None) -> None:
        """Удаляет ключ чата из словаря истории."""
        if user_id in self.histories and chat_id in self.histories[user_id]:
            self.histories[user_id].pop(chat_id, None)

    def get_chats(self, user_id: int) -> List[dict]:
        """Возвращает список чатов из памяти пользователя."""
        return self.chats.get(user_id, [])

    def create_chat(self, user_id: int, title: str = "Новый чат") -> int:
        """Создает виртуальную запись чата в ОЗУ."""
        if user_id not in self.chats:
            self.chats[user_id] = []
        self.chat_id_counter += 1
        chat = {"id": self.chat_id_counter, "title": title, "created_at": "", "updated_at": ""}
        self.chats[user_id].insert(0, chat)
        return self.chat_id_counter

    def delete_chat(self, user_id: int, chat_id: int) -> bool:
        """Удаляет чат из списков в памяти."""
        if user_id in self.chats:
            self.chats[user_id] = [c for c in self.chats[user_id] if c["id"] != chat_id]
        if user_id in self.histories:
            self.histories[user_id].pop(chat_id, None)
        return True

    def rename_chat(self, user_id: int, chat_id: int, title: str) -> bool:
        """Находит чат в списке и меняет его название."""
        if user_id in self.chats:
            for c in self.chats[user_id]:
                if c["id"] == chat_id:
                    c["title"] = title
                    return True
        return False


def history_storage_factory(db: Database) -> BaseHistoryStorage:
    """
    Фабричный метод для выбора стратегии хранения.
    Если есть живое соединение с БД — возвращает DbHistoryStorage.
    В противном случае — MemoryHistoryStorage для временной работы.
    """
    if db.connection:
        return DbHistoryStorage(db)
    return MemoryHistoryStorage()
