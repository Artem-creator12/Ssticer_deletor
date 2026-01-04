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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)

# Конфигурация
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
PORT = int(os.environ.get('PORT', 10000))

# Проверка переменных окружения
logger.info(f"🔧 Конфигурация:")
logger.info(f"   BOT_TOKEN: {'установлен' if BOT_TOKEN else 'НЕ установлен'}")
logger.info(f"   WEBHOOK_URL: {WEBHOOK_URL}")
logger.info(f"   PORT: {PORT}")

# Инициализация бота
application = None
if BOT_TOKEN:
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        logger.info("✅ Бот Telegram инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
else:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")

class StickerBanBot:
    def __init__(self):
        self.banned_packs = {}
        self.load_data()
    
    def load_data(self):
        """Загружает данные из файла"""
        try:
            if os.path.exists('data.json'):
                with open('data.json', 'r') as f:
                    self.banned_packs = json.load(f)
                    logger.info(f"✅ Загружены данные для {len(self.banned_packs)} чатов")
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            self.banned_packs = {}
    
    def save_data(self):
        """Сохраняет данные в файл"""
        try:
            with open('data.json', 'w') as f:
                json.dump(self.banned_packs, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Sticker Ban Bot*\n\n"
            "✅ Бот работает!\n\n"
            "*Команды:*\n"
            "• /stickban (ответ на стикер) - запретить пак\n"
            "• /stickbanlist - список запрещенных\n"
            "• /help - помощь\n\n"
            "⚡ Работает на Render.com",
            parse_mode='Markdown'
        )
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📚 *Как использовать:*\n\n"
            "1. Добавьте бота в группу\n"
            "2. Дайте права админа (удалять сообщения, банить)\n"
            "3. Ответьте /stickban на стикер для запрета\n"
            "4. Автоудаление + мут 1 час за запрещенные стикеры",
            parse_mode='Markdown'
        )
    
    async def stickban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запретить стикер-пак"""
        try:
            if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
                await update.message.reply_text("❌ Ответьте на стикер!")
                return
            
            sticker = update.message.reply_to_message.sticker
            pack_name = sticker.set_name
            
            if not pack_name:
                await update.message.reply_text("❌ Этот стикер не из набора!")
                return
            
            chat = update.effective_chat
            chat_id = str(chat.id)
            
            if chat_id not in self.banned_packs:
                self.banned_packs[chat_id] = []
            
            if pack_name in self.banned_packs[chat_id]:
                await update.message.reply_text(f"❌ Пак уже запрещен!")
                return
            
            self.banned_packs[chat_id].append(pack_name)
            self.save_data()
            
            # Удаляем оригинальный стикер
            try:
                await update.message.reply_to_message.delete()
            except:
                pass
            
            await update.message.reply_text(
                f"✅ *Пак запрещён!*\n`{pack_name}`\n\n"
                f"Теперь за этот стикер = мут 1 час",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await update.message.reply_text("❌ Ошибка. Проверьте права бота!")
    
    async def stickbanlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список запрещенных паков"""
        chat = update.effective_chat
        chat_id = str(chat.id)
        
        if chat_id in self.banned_packs and self.banned_packs[chat_id]:
            packs = "\n".join([f"• `{pack}`" for pack in self.banned_packs[chat_id]])
            await update.message.reply_text(f"📋 *Запрещенные паки:*\n\n{packs}", parse_mode='Markdown')
        else:
            await update.message.reply_text("✅ Нет запрещенных паков")
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка стикеров"""
        try:
            chat = update.effective_chat
            user = update.effective_user
            sticker = update.message.sticker
            
            if chat.type == 'private':
                return
            
            chat_id = str(chat.id)
            pack_name = sticker.set_name
            
            if chat_id in self.banned_packs and pack_name in self.banned_packs[chat_id]:
                # Удаляем стикер
                await update.message.delete()
                
                # Мут на 1 час
                until_date = datetime.now() + timedelta(hours=1)
                permissions = ChatPermissions(can_send_messages=False)
                
                await chat.restrict_member(user.id, permissions, until_date=until_date)
                
                # Уведомление
                warning = await update.message.reply_text(
                    f"🚫 {user.mention_html()} - мут 1 час\n"
                    f"Причина: запрещенный стикер `{pack_name}`",
                    parse_mode='HTML'
                )
                
                # Удаляем уведомление через 10 сек
                import asyncio
                await asyncio.sleep(10)
                try:
                    await warning.delete()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Ошибка: {e}")

# Создаем экземпляр бота
bot = StickerBanBot()

# Регистрируем обработчики
if application:
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_cmd))
    application.add_handler(CommandHandler("stickban", bot.stickban))
    application.add_handler(CommandHandler("stickbanlist", bot.stickbanlist))
    application.add_handler(MessageHandler(filters.Sticker.ALL & ~filters.COMMAND, bot.handle_sticker))
    logger.info("✅ Обработчики команд зарегистрированы")

# ========== FLASK МАРШРУТЫ ==========
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Telegram Sticker Ban Bot",
        "bot": "ready" if application else "not ready",
        "endpoints": ["/", "/health", "/set_webhook", "/info"],
        "time": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    """Health check для Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/set_webhook')
def set_webhook():
    """Установка webhook для Telegram"""
    if not WEBHOOK_URL:
        return jsonify({"error": "RENDER_EXTERNAL_URL не установлен"}), 400
    
    if not application:
        return jsonify({"error": "Бот не инициализирован. Проверьте TELEGRAM_BOT_TOKEN"}), 500
    
    try:
        # Устанавливаем webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Импортируем asyncio внутри функции
        import asyncio
        
        async def setup():
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        # Запускаем асинхронно
        asyncio.run(setup())
        
        return jsonify({
            "status": "success",
            "message": "✅ Webhook установлен!",
            "webhook_url": webhook_url,
            "next": "Напишите /start боту в Telegram"
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint для Telegram"""
    if not application:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    try:
        # Получаем данные от Telegram
        update_data = request.get_json(force=True)
        
        # Импортируем asyncio внутри функции
        import asyncio
        
        async def process():
            update = Update.de_json(update_data, application.bot)
            await application.process_update(update)
        
        # Обрабатываем асинхронно
        asyncio.run(process())
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/info')
def info():
    """Информация о сервисе"""
    return jsonify({
        "service": "https://ssticer-deletor.onrender.com",
        "webhook": f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else "не установлен",
        "bot_token": "установлен" if BOT_TOKEN else "не установлен",
        "python": os.sys.version,
        "time": datetime.now().isoformat()
    })

# Запуск приложения
if __name__ == '__main__':
    logger.info(f"🚀 Запуск сервиса на порту {PORT}")
    
    # Если есть webhook URL, устанавливаем его
    if WEBHOOK_URL and application:
        try:
            import asyncio
            webhook_url = f"{WEBHOOK_URL}/webhook"
            asyncio.run(application.bot.set_webhook(url=webhook_url))
            logger.info(f"✅ Webhook установлен: {webhook_url}")
        except Exception as e:
            logger.error(f"Ошибка установки webhook: {e}")
    
    # Запускаем Flask
    app.run(host='0.0.0.0', port=PORT, debug=False)
