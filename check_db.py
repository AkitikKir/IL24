
import os
import pymysql
from dotenv import load_dotenv
from bot_core.config import BotConfig

# Загрузка переменных окружения из файла .env
# Это позволяет получить настройки доступа к базе данных
load_dotenv()

# Установка временного токена Telegram, если он отсутствует в окружении.
# Это необходимо для корректной загрузки класса BotConfig, который требует наличия токена.
if not os.environ.get("TELEGRAM_TOKEN"):
    os.environ["TELEGRAM_TOKEN"] = "dummy_token_for_check"

def check_db():
    """
    Функция для детальной проверки структуры таблиц в базе данных.
    Подключается к MySQL, запрашивает информацию о колонках и выводит её пользователю.
    Это помогает убедиться, что миграции базы данных прошли успешно.
    """
    # Загружаем текущие настройки бота, чтобы получить параметры подключения к БД
    config = BotConfig.load()
    try:
        # Пытаемся установить соединение с сервером MySQL, используя параметры из конфига
        # Мы используем DictCursor, чтобы результаты запросов возвращались в виде словарей
        conn = pymysql.connect(
            host=config.db.host,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        # Используем контекстный менеджер курсора для безопасного выполнения SQL-запросов
        with conn.cursor() as cursor:
            # Выполняем SQL команду SHOW COLUMNS для таблицы истории чатов
            # Это вернет список всех полей, их типов данных и ограничений
            print("Проверка колонок таблицы chat_history (хранение сообщений):")
            cursor.execute("SHOW COLUMNS FROM chat_history")
            for row in cursor.fetchall():
                # Печатаем информацию о каждой колонке (имя, тип, NULL, ключ, дефолт, доп. инфо)
                print(row)
            
            # Повторяем процедуру для таблицы пользователей
            # Здесь хранятся данные о подписках, балансе и ролях пользователей
            print("\nПроверка колонок таблицы users (данные пользователей):")
            cursor.execute("SHOW COLUMNS FROM users")
            for row in cursor.fetchall():
                print(row)
                  
        # Явно закрываем соединение после завершения всех проверок
        conn.close()
    except Exception as e:
        # В случае возникновения любой ошибки (сетевой, авторизации или SQL), выводим её в консоль
        print(f"КРИТИЧЕСКАЯ ОШИБКА при проверке структуры БД: {e}")


if __name__ == "__main__":
    # Запуск скрипта проверки
    check_db()
