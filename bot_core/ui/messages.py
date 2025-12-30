"""Текстовые шаблоны и системные инструкции."""

MESSAGES = {
    "ru": {
        "start_header": "Добро пожаловать в <b>ИЛ24</b> — ваш помощник по технике 🚀",
        "start_long": (
            "<b>ИЛ24</b> — бот, который поможет с вопросами по компьютерам, программному обеспечению, обслуживанию и мобильным ОС. 💡\n\n"
            "<b>Что умеет этот бот:</b>\n"
            "• Отвечать на вопросы про ПО, настройку, диагностику и ремонт 🛠️\n"
            "• Поддерживать выбор нейросети 🌐\n"
        ),
        "choose_model": "Выбрать нейросеть 🖥️",
        "choose_language": "Выбрать язык 🌍",
        "start_chat": "💬 Начать чат",
        "stop_chat": "⏹ Остановить чат",
        "chat_started": "Чат запущен — задавайте вопрос🤖",
        "chat_stopped": "Чат завершен. Возвращайтесь в главное меню.",
        "choose_language_prompt": "Выберите язык:",
        "language_changed": "Язык успешно изменён. ✅",
        "history_cleared": "История очищена. 🗑️",
        "insufficient_balance": "Недостаточно токенов для выполнения запроса. ⚠️",
        "invalid_query": "Извините — я отвечаю только на вопросы о ПК, ПО, обслуживании и мобильных ОС. ❌",
        "help_title": "📚 Помощь",
        "help_text": (
            "— Формулируйте проблему чётко: укажите ОС, модель устройства и точный текст ошибки (если есть). 📝\n\n"
            "— Примеры:\n"
            "  • «После обновления Windows 11 пропал звук»\n"
            "  • «Ubuntu 22.04: как смонтировать smb-шару?» 🖧\n\n"
            "— Ограничения:\n"
            "  • Бот не даёт медицинских, юридических или финансовых советов.\n"
            "  • Бот не выполняет команды на вашем компьютере — только даёт рекомендации.\n\n"
            "Если нужно улучшить ответ — переформулируйте запрос и добавьте детали. 🛠️"
        ),
        "settings_title": "⚙️ Настройки ИЛ24",
        "settings_description": "Здесь можно очистить историю и посмотреть FAQ.",
        "faq_title": "❓ FAQ — часто задаваемые вопросы",
        "faq_text": (
            "Q: Сколько контекста бот хранит?\n"
            "A: Только <b>последний ответ</b> ассистента — это сделано для приватности. 🔒\n\n"
            "Q: Что происходит при смене модели?\n"
            "A: История автоматически очищается, контекст сбрасывается. 🔁\n\n"
            "Q: Кто может перезапустить бота?\n"
            "A: Только админ (см. /restart) или через systemd, если настроен SERVICE_NAME. ⚙️"
        ),
        "contact_support": "Опишите проблему — админы получат тикет и свяжутся с вами. 📨",
        "back": "◀ Назад",
        "ticket_prompt": "Опишите вашу проблему подробно и отправьте сообщение — оно станет тикетом. После отправки админы получат уведомление и смогут ответить вам. ✉️",
        "ticket_created": "Заявка отправлена! Номер: #{ticket_id}. Админы оповещены. ✅",
        "ticket_failed_db": "Тикет отправлен админу, но не удалось сохранить в БД (режим fallback).",
        "gethelp": "Связаться с поддержкой👨🏽",
        "settbut": "Настройки⚙️",
        "feedback_positive": "Спасибо за отзыв! Рад был помочь. 😊",
        "feedback_negative": "Жаль, что ответ не помог. Возможно, эти варианты будут полезнее:\n1. Попробуйте переформулировать вопрос с деталями (модель, ОС, текст ошибки).\n2. Проверьте наш FAQ в настройках.\n3. Свяжитесь с поддержкой для детального разбора.",
        "bot_description": "ИЛ24 — ваш умный помощник по технике, компьютерам и ПО. Решим любой вопрос вместе! 🚀",
        "bot_short_description": "Технический помощник по ПК и ПО 💻",
    },
    "en": {
        "start_header": "Welcome to <b>IL24</b> — your tech assistant 🚀",
        "start_long": (
            "<b>IL24</b> helps with questions about computers, software, maintenance and mobile OS. 💡\n\n"
            "<b>What can this bot do:</b>\n"
            "• Answers about software, setup, diagnostics and troubleshooting 🛠️\n"
            "• Supports model selection 🌐\n"
        ),
        "choose_model": "Choose model 🖥️",
        "choose_language": "Choose language 🌍",
        "start_chat": "💬 Start chat",
        "stop_chat": "⏹ Stop chat",
        "chat_started": "Chat started — ask your question🤖",
        "chat_stopped": "Chat stopped. Returning to main menu. ↩️",
        "choose_language_prompt": "Choose a language:",
        "language_changed": "Language changed. ✅",
        "history_cleared": "Conversation history cleared — last assistant answer removed. 🗑️",
        "insufficient_balance": "Not enough tokens for this request. ⚠️",
        "invalid_query": "Sorry — I only answer questions about PCs, software, maintenance and mobile OS. ❌",
        "help_title": "📚 Help",
        "help_text": (
            "— Be specific: OS, device model, and error text help a lot. 📝\n\n"
            "— Examples:\n"
            "  • \"No sound after Windows 11 update\" \n"
            "  • \"How to mount an SMB share on Ubuntu 22.04?\" 🖧\n\n"
            "— Limitations:\n"
            "  • No medical/legal/financial advice.\n"
            "  • Bot does not execute commands on your machine — only provides recommendations.\n\n"
            "If you need a better answer, refine the question and add details. 🛠️"
        ),
        "settings_title": "⚙️ IL24 settings",
        "settings_description": "View current model/language, clear history, open FAQ or contact support. 🧭",
        "faq_title": "❓ FAQ",
        "faq_text": (
            "Q: How much context is stored?\n"
            "A: Only the <b>last assistant response</b> — to protect privacy. 🔒\n\n"
            "Q: What happens on model change?\n"
            "A: History is cleared automatically, context is reset. 🔁\n\n"
            "Q: Who can restart the bot?\n"
            "A: Admin only (see /restart) or via systemd if SERVICE_NAME is set. ⚙️"
        ),
        "contact_support": "Describe the issue — admins will receive a ticket. 📨",
        "back": "◀ Back",
        "ticket_prompt": "Describe your problem in detail and send the message — it will become a ticket. Admins will be notified.",
        "ticket_created": "Ticket created! Number: #{ticket_id}. Admins notified. ✅",
        "ticket_failed_db": "Ticket sent to admin but failed to save to DB (fallback mode). Admin will be notified.",
        "gethelp": "Contact support👨🏽",
        "settbut": "Settings⚙️",
        "feedback_positive": "Thank you for the feedback! Glad I could help. 😊",
        "feedback_negative": "Sorry the answer wasn't helpful. These options might be more useful:\n1. Try rephrasing your question with more details (model, OS, error text).\n2. Check our FAQ in settings.\n3. Contact support for a detailed investigation.",
        "bot_description": "IL24 — your smart assistant for tech, computers, and software. Let's solve any issue together! 🚀",
        "bot_short_description": "Tech assistant for PC & software 💻",
    },
}

SYSTEM_INSTRUCTIONS = {
    "ru": (
        "Вы — технический ассистент ИЛ24. Вы ДОЛЖНЫ отвечать ТОЛЬКО на вопросы, напрямую связанные с персональными компьютерами (ПК), "
        "операционными системами (Windows, macOS, Linux), программным обеспечением для ПК, обслуживанием железа, "
        "а также мобильными операционными системами (Android, iOS) и их приложениями. "
        "Если вопрос не относится к этим техническим темам (например, вопросы о жизни, еде, политике, общие советы и т.д.), "
        "вы ДОЛЖНЫ ответить ровно следующую фразу и ничего больше: "
        "'Извините, я могу отвечать только на вопросы о ПК, программном обеспечении, обслуживании, ОС, также на вопросы связанные с смартфонами, их ОС и ПО.'"
    ),
    "en": (
        "You are the IL24 tech assistant. You MUST ONLY answer questions directly related to personal computers (PCs), "
        "operating systems (Windows, macOS, Linux), PC software, hardware maintenance, "
        "as well as mobile operating systems (Android, iOS) and their apps. "
        "If a question is unrelated to these tech topics (e.g., questions about life, food, politics, general advice, etc.), "
        "you MUST respond with exactly the following phrase and nothing else: "
        "'Sorry, I can only answer questions about PCs, software, maintenance, and operating systems, as well as questions related to smartphones, their OS and software.'"
    ),
}

REFUSAL_PHRASES = {
    "ru": "Извините, я могу отвечать только на вопросы о ПК, программном обеспечении, обслуживании, ОС, также на вопросы связанные с смартфонами, их ОС и ПО.",
    "en": "Sorry, I can only answer questions about PCs, software, maintenance, and operating systems, as well as questions related to smartphones, their OS and software"
}


