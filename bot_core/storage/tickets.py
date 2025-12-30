"""
Модуль для управления тикетами (обращениями пользователей в поддержку).
Обеспечивает сохранение заявок в базу данных MySQL или оперативную память.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from ..database import Database


class BaseTicketStorage:
    """
    Абстрактный интерфейс для операций с тикетами.
    Определяет стандартный набор методов для создания, чтения и обновления статусов заявок.
    """

    def create_ticket(self, user_id: int, username: str, message: str) -> Optional[int]:
        """Создает новый тикет и возвращает его идентификатор."""
        raise NotImplementedError

    def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        """Возвращает полную информацию о тикете по его ID."""
        raise NotImplementedError

    def update_status(self, ticket_id: int, status: str = "closed") -> None:
        """Изменяет текущий статус тикета (напр., 'open' -> 'closed')."""
        raise NotImplementedError

    def list_tickets(self, limit: int = 50) -> List[Dict]:
        """Возвращает список последних N тикетов для панели администратора."""
        raise NotImplementedError


class DbTicketStorage(BaseTicketStorage):
    """
    Реализация хранилища тикетов в MySQL.
    Используется для долгосрочного хранения обращений и отслеживания их статуса.
    """

    def __init__(self, db: Database):
        """Инициализация с внедрением объекта БД."""
        self.db = db
        self.logger = logging.getLogger(self.__class__.__name__)

    def create_ticket(self, user_id: int, username: str, message: str) -> Optional[int]:
        """
        Добавляет запись в таблицу 'tickets'.
        Возвращает AUTO_INCREMENT идентификатор новой строки.
        """
        if not self.db.connection:
            return None
        try:
            with self.db.connection.cursor() as cursor:
                # Вставляем данные обращения
                cursor.execute(
                    "INSERT INTO tickets (user_id, username, message) VALUES (%s, %s, %s)",
                    (user_id, username, message),
                )
                return cursor.lastrowid
        except Exception:
            self.logger.exception("Ошибка при создании тикета в MySQL.")
            return None

    def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        """
        Запрашивает данные тикета по его номеру.
        Нормализует ключи словаря для единообразия в коде бота.
        """
        if not self.db.connection:
            return None
        try:
            with self.db.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, user_id, username, message, status, created_at FROM tickets WHERE id = %s",
                    (ticket_id,),
                )
                r = cursor.fetchone()
                if not r:
                    return None
                # Приводим ключи к нижнему регистру для стабильности
                return {
                    "id": r.get("id") or r.get("Id") or r.get("ID"),
                    "user_id": r.get("user_id") or r.get("User_id") or r.get("USER_ID"),
                    "username": r.get("username") or r.get("Username") or r.get("USERNAME"),
                    "message": r.get("message") or r.get("Message") or r.get("MESSAGE"),
                    "status": r.get("status") or r.get("Status") or r.get("STATUS"),
                    "created_at": r.get("created_at") or r.get("Created_at") or r.get("CREATED_AT"),
                }
        except Exception:
            self.logger.exception("Ошибка при чтении тикета из БД.")
            return None

    def update_status(self, ticket_id: int, status: str = "closed") -> None:
        """Обновляет текстовое поле status для указанного тикета."""
        if not self.db.connection:
            return
        try:
            with self.db.connection.cursor() as cursor:
                cursor.execute("UPDATE tickets SET status = %s WHERE id = %s", (status, ticket_id))
        except Exception:
            self.logger.exception("Ошибка при обновлении статуса тикета.")

    def list_tickets(self, limit: int = 50) -> List[Dict]:
        """Загружает список последних тикетов, отсортированных по дате (сначала новые)."""
        if not self.db.connection:
            return []
        try:
            with self.db.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, user_id, username, status, created_at FROM tickets ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
                if not rows:
                    return []
                results = []
                for r in rows:
                    # Нормализация структуры данных каждой строки
                    normalized = {
                        "id": r.get("id") or r.get("Id") or r.get("ID"),
                        "user_id": r.get("user_id") or r.get("User_id") or r.get("USER_ID"),
                        "username": r.get("username") or r.get("Username") or r.get("USERNAME"),
                        "status": r.get("status") or r.get("Status") or r.get("STATUS"),
                        "created_at": r.get("created_at") or r.get("Created_at") or r.get("CREATED_AT"),
                    }
                    results.append(normalized)
                return results
        except Exception:
            self.logger.exception("Ошибка при получении списка тикетов.")
            return []


class MemoryTicketStorage(BaseTicketStorage):
    """
    Fallback-хранилище в ОЗУ.
    Используется, если подключение к MySQL не удалось.
    """

    def __init__(self):
        """Инициализация словаря и счетчика ID."""
        self.tickets: Dict[int, Dict] = {}
        self._next_id = 1

    def _next_ticket_id(self) -> int:
        """Генерирует следующий порядковый номер тикета."""
        tid = self._next_id
        self._next_id += 1
        return tid

    def create_ticket(self, user_id: int, username: str, message: str) -> Optional[int]:
        """Сохраняет тикет во временный словарь."""
        ticket_id = self._next_ticket_id()
        self.tickets[ticket_id] = {
            "id": ticket_id,
            "user_id": user_id,
            "username": username,
            "message": message,
            "status": "open",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return ticket_id

    def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        """Извлекает тикет из словаря по ключу."""
        return self.tickets.get(ticket_id)

    def update_status(self, ticket_id: int, status: str = "closed") -> None:
        """Меняет значение в словаре по ключу тикета."""
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["status"] = status

    def list_tickets(self, limit: int = 50) -> List[Dict]:
        """Возвращает отсортированный список значений словаря."""
        return sorted(self.tickets.values(), key=lambda x: x["id"], reverse=True)[:limit]


def ticket_storage_factory(db: Database) -> BaseTicketStorage:
    """
    Фабрика выбора стратегии хранения тикетов.
    Отдает DbTicketStorage при наличии живого коннекта к MySQL.
    """
    if db.connection:
        return DbTicketStorage(db)
    return MemoryTicketStorage()
