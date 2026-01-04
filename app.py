import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)

# Глобальные переменные
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL', '') + '/webhook'
PORT = int(os.environ.get('PORT', 10000))

# Проверка токена
if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
    logger.error("Добавьте в Environment Variables на Render.com:")
    logger.error("Key: TELEGRAM_BOT_TOKEN")
    logger.error("Value: ваш_токен_от_BotFather")

# Инициализация бота
application = Application.builder().token(BOT_TOKEN).request(HTTPXRequest(http_version="1.1")).build()

class StickerBanBot:
    def __init__(self):
        self.banned_packs = self.load_data()
        logger.info("🤖 StickerBanBot инициализирован")
    
    def load_data(self):
        """Загружает данные из файла"""
        try:
            if os.path.exists('data.json'):
                with open('data.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
        return {}
    
    def save_data(self):
        """Сохраняет данные в файл"""
        try:
            with open('data.json', 'w') as f:
                json.dump(self.banned_packs, f, indent=2)
            logger.debug("Данные сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        chat = update.effective_chat
        
        if chat.type == 'private':
            await update.message.reply_text(
                "🤖 *Sticker Ban Bot*\n\n"
                "Этот бот запрещает стикер-паки в группах.\n\n"
                "*Как использовать:*\n"
                "1. Добавьте бота в группу\n"
                "2. Дайте права администратора\n"
                "3. Ответьте /stickban на стикер для запрета пак\n\n"
                "*Команды:*\n"
                "• /stickban (ответ на стикер)\n"
                "• /stickbanlist\n"
                "• /help\n\n"
                "⚡ Работает на Render.com",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "✅ Бот активен! Используйте /help для списка команд",
                parse_mode='Markdown'
            )
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "📚 *Помощь по командам:*\n\n"
            "*Для админов:*\n"
            "▫️ /stickban (ответ на стикер) - запретить весь пак\n"
            "▫️ /stickbanlist - список запрещенных паков\n"
            "▫️ /stickunban <название> - разблокировать пак\n\n"
            "*Наказание:*\n"
            "Отправка запрещенных стикеров:\n"
            "• Сообщение удаляется\n"
            "• Мут на 1 час\n"
            "• Уведомление в чат\n\n"
            "*Требования:*\n"
            "Бот должен быть администратором с правами:\n"
            "✓ Удалять сообщения\n"
            "✓ Блокировать пользователей"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def stickban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрещает стикер-пак"""
        chat = update.effective_chat
        user = update.effective_user
        
        # Проверка что это группа
        if chat.type == 'private':
            await update.message.reply_text("❌ Эта команда работает только в группах!")
            return
        
        # Проверка что это ответ на стикер
        if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
            await update.message.reply_text("❌ Ответьте на стикер который хотите запретить!")
            return
        
        sticker = update.message.reply_to_message.sticker
        pack_name = sticker.set_name
        
        if not pack_name:
            await update.message.reply_text("❌ Этот стикер не из набора!")
            return
        
        chat_id = str(chat.id)
        
        # Проверяем права администратора
        try:
            member = await chat.get_member(user.id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Только администраторы могут запрещать стикер-паки!")
                return
        except Exception as e:
            logger.error(f"Ошибка проверки прав: {e}")
            await update.message.reply_text("❌ Ошибка проверки прав. Убедитесь что бот - администратор!")
            return
        
        # Инициализация списка для чата если нужно
        if chat_id not in self.banned_packs:
            self.banned_packs[chat_id] = []
        
        # Проверка не запрещен ли уже
        if pack_name in self.banned_packs[chat_id]:
            await update.message.reply_text(f"❌ Пак '{pack_name}' уже запрещен!")
            return
        
        # Добавляем в запрещенные
        self.banned_packs[chat_id].append(pack_name)
        self.save_data()
        
        # Удаляем исходный стикер
        try:
            await update.message.reply_to_message.delete()
        except Exception as e:
            logger.error(f"Не удалось удалить стикер: {e}")
        
        # Удаляем команду
        try:
            await update.message.delete()
        except:
            pass
        
        # Отправляем подтверждение
        success_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=f"✅ *Стикер-пак запрещён!*\n\n"
                 f"📛 *Название:* `{pack_name}`\n"
                 f"👤 *Администратор:* {user.mention_html()}\n\n"
                 f"⚠️ Отправка стикеров из этого пака теперь наказывается мутом на 1 час!",
            parse_mode='HTML'
        )
        
        # Удаляем подтверждение через 10 секунд
        await asyncio.sleep(10)
        try:
            await success_msg.delete()
        except:
            pass
    
    async def stickbanlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список запрещенных паков"""
        chat = update.effective_chat
        if chat.type == 'private':
            await update.message.reply_text("❌ Эта команда работает только в группах!")
            return
        
        chat_id = str(chat.id)
        
        if chat_id in self.banned_packs and self.banned_packs[chat_id]:
            packs = "\n".join([f"• `{pack}`" for pack in self.banned_packs[chat_id]])
            await update.message.reply_text(
                f"📋 *Запрещенные стикер-паки в этом чате:*\n\n{packs}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("✅ В этом чате нет запрещенных стикер-паков.")
    
    async def stickunban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Разблокирует стикер-пак"""
        chat = update.effective_chat
        user = update.effective_user
        
        if chat.type == 'private':
            await update.message.reply_text("❌ Эта команда работает только в группах!")
            return
        
        # Проверяем права администратора
        try:
            member = await chat.get_member(user.id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Только администраторы могут использовать эту команду!")
                return
        except Exception as e:
            logger.error(f"Ошибка проверки прав: {e}")
            return
        
        # Проверка аргументов
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите название пака:\n`/stickunban pack_name`",
                parse_mode='Markdown'
            )
            return
        
        pack_name = ' '.join(context.args)
        chat_id = str(chat.id)
        
        if chat_id in self.banned_packs and pack_name in self.banned_packs[chat_id]:
            self.banned_packs[chat_id].remove(pack_name)
            self.save_data()
            
            await update.message.reply_text(
                f"✅ Стикер-пак `{pack_name}` разблокирован!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Этот стикер-пак не был запрещён.")
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает отправку стикеров"""
        chat = update.effective_chat
        user = update.effective_user
        sticker = update.message.sticker
        
        # Не обрабатываем приватные чаты
        if chat.type == 'private':
            return
        
        chat_id = str(chat.id)
        pack_name = sticker.set_name
        
        # Проверяем запрещен ли пак
        if chat_id in self.banned_packs and pack_name in self.banned_packs[chat_id]:
            try:
                # Удаляем стикер
                await update.message.delete()
                
                # Даем мут на 1 час
                until_date = datetime.now() + timedelta(hours=1)
                permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                )
                
                await chat.restrict_member(
                    user.id,
                    permissions,
                    until_date=until_date
                )
                
                # Отправляем предупреждение
                warning_msg = await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"🚫 *Нарушение правил!*\n\n"
                         f"👤 *Пользователь:* {user.mention_html()}\n"
                         f"⏰ *Наказание:* мут на 1 час\n"
                         f"📛 *Причина:* отправка запрещенного стикера\n"
                         f"🖼 *Пак:* `{pack_name}`",
                    parse_mode='HTML'
                )
                
                # Удаляем предупреждение через 15 секунд
                await asyncio.sleep(15)
                try:
                    await warning_msg.delete()
                except:
                    pass
                
            except Exception as e:
                logger.error(f"Ошибка при муте пользователя: {e}")
                
                # Если не удалось замутить, хотя бы удаляем стикер
                try:
                    await update.message.delete()
                    temp_msg = await context.bot.send_message(
                        chat_id=chat.id,
                        text=f"⚠️ {user.mention_html()}, этот стикер-пак запрещён в этом чате!",
                        parse_mode='HTML'
                    )
                    
                    # Удаляем предупреждение через 5 секунд
                    await asyncio.sleep(5)
                    await temp_msg.delete()
                    
                except Exception as e2:
                    logger.error(f"Не удалось удалить сообщение: {e2}")

# Создаем экземпляр бота
bot = StickerBanBot()

# Регистрируем обработчики
application.add_handler(CommandHandler("start", bot.start))
application.add_handler(CommandHandler("help", bot.help_cmd))
application.add_handler(CommandHandler("stickban", bot.stickban))
application.add_handler(CommandHandler("stickbanlist", bot.stickbanlist))
application.add_handler(CommandHandler("stickunban", bot.stickunban))
application.add_handler(MessageHandler(filters.Sticker.ALL & ~filters.COMMAND, bot.handle_sticker))

# Инициализируем bot_data
application.bot_data['sticker_bot'] = bot

# Маршруты Flask
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Telegram Sticker Ban Bot",
        "webhook_set": WEBHOOK_URL != "",
        "endpoints": ["/", "/webhook", "/health", "/set_webhook", "/delete_webhook"]
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/set_webhook', methods=['GET'])
async def set_webhook():
    """Устанавливает webhook"""
    if not WEBHOOK_URL:
        return jsonify({"error": "WEBHOOK_URL not set"}), 400
    
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook установлен: {webhook_url}")
        return jsonify({
            "status": "success",
            "webhook_url": webhook_url,
            "message": "Webhook установлен успешно"
        })
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/delete_webhook', methods=['GET'])
async def delete_webhook():
    """Удаляет webhook"""
    try:
        result = await application.bot.delete_webhook()
        logger.info("Webhook удален")
        return jsonify({"status": "success", "result": str(result)})
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Обработчик webhook от Telegram"""
    if request.is_json:
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.initialize()
        await application.process_update(update)
        return jsonify({"status": "ok"})
    return jsonify({"error": "Invalid request"}), 400

async def main():
    """Основная функция запуска"""
    logger.info("🚀 Запуск Sticker Ban Bot...")
    logger.info(f"🌐 PORT: {PORT}")
    logger.info(f"🔗 WEBHOOK_URL: {WEBHOOK_URL}")
    
    if WEBHOOK_URL:
        # Режим webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        # Запускаем Flask в отдельном потоке
        import threading
        flask_thread = threading.Thread(
            target=lambda: app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
        )
        flask_thread.daemon = True
        flask_thread.start()
        logger.info(f"✅ Flask запущен на порту {PORT}")
        
        # Бесконечный цикл для поддержания работы
        while True:
            await asyncio.sleep(3600)  # Спим 1 час
    else:
        # Режим polling (для разработки)
        logger.info("⚠️ WEBHOOK_URL не установлен, используем polling")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("✅ Бот запущен в режиме polling")
        
        # Ожидаем завершения
        await asyncio.Event().wait()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
