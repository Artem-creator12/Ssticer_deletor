import os
import json
import logging
import threading
import time
import requests
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
SERVICE_URL = "https://ssticer-deletor.onrender.com"

if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
    # Для Render - создадим заглушку, но приложение запустится
    BOT_TOKEN = "placeholder"

# Инициализация бота
application = None
if BOT_TOKEN and BOT_TOKEN != "placeholder":
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        logger.info("✅ Бот инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        application = None
else:
    logger.warning("⚠️ Используется заглушка для токена")

class StickerBanBot:
    def __init__(self):
        self.banned_packs = self.load_data()
        logger.info(f"🤖 StickerBanBot загружен")
    
    def load_data(self):
        """Загружает данные из файла"""
        try:
            if os.path.exists('data.json'):
                with open('data.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
        return {}
    
    def save_data(self):
        """Сохраняет данные в файл"""
        try:
            with open('data.json', 'w') as f:
                json.dump(self.banned_packs, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        await update.message.reply_text(
            "🤖 *Sticker Ban Bot*\n\n"
            "✅ Бот активен!\n\n"
            "*Как использовать:*\n"
            "1. Добавьте в группу\n"
            "2. Дайте права админа\n"
            "3. Ответьте /stickban на стикер\n\n"
            "⚡ Авто-пробуждение включено",
            parse_mode='Markdown'
        )
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        await update.message.reply_text(
            "📚 *Команды:*\n\n"
            "• /stickban (ответ на стикер) - запретить пак\n"
            "• /stickbanlist - список запрещенных\n"
            "• /stickunban <название> - разблокировать\n\n"
            "⚠️ *Наказание:*\n"
            "Запрещенный стикер = удаление + мут 1 час",
            parse_mode='Markdown'
        )
    
    async def stickban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрет стикер-пака"""
        try:
            if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
                await update.message.reply_text("❌ Ответьте на стикер!")
                return
            
            sticker = update.message.reply_to_message.sticker
            pack_name = sticker.set_name
            
            if not pack_name:
                await update.message.reply_text("❌ Стикер не из набора!")
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
            
            # Пытаемся удалить стикер
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
        """Список запрещенных"""
        chat = update.effective_chat
        chat_id = str(chat.id)
        
        if chat_id in self.banned_packs and self.banned_packs[chat_id]:
            packs = "\n".join([f"• `{pack}`" for pack in self.banned_packs[chat_id]])
            await update.message.reply_text(f"📋 *Запрещенные паки:*\n\n{packs}", parse_mode='Markdown')
        else:
            await update.message.reply_text("✅ Нет запрещенных паков")
    
    async def stickunban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Разблокировка"""
        if not context.args:
            await update.message.reply_text("❌ Укажите название: /stickunban pack_name")
            return
        
        pack_name = ' '.join(context.args)
        chat = update.effective_chat
        chat_id = str(chat.id)
        
        if chat_id in self.banned_packs and pack_name in self.banned_packs[chat_id]:
            self.banned_packs[chat_id].remove(pack_name)
            self.save_data()
            await update.message.reply_text(f"✅ Пак `{pack_name}` разблокирован!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Пак не был запрещен")
    
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
                    f"Причина: запрещенный стикер-пак `{pack_name}`",
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
            logger.error(f"Ошибка обработки стикера: {e}")

# Инициализация бота
bot = StickerBanBot()

if application:
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_cmd))
    application.add_handler(CommandHandler("stickban", bot.stickban))
    application.add_handler(CommandHandler("stickbanlist", bot.stickbanlist))
    application.add_handler(CommandHandler("stickunban", bot.stickunban))
    application.add_handler(MessageHandler(filters.Sticker.ALL & ~filters.COMMAND, bot.handle_sticker))

# ========== KEEP-ALIVE ФУНКЦИЯ ==========
def keep_alive():
    """Периодически будит сервис чтобы он не засыпал"""
    while True:
        try:
            # Ждем 10 минут
            time.sleep(600)
            
            # Отправляем запрос к своему же сервису
            response = requests.get(f"{SERVICE_URL}/health", timeout=10)
            logger.info(f"🔔 Keep-alive: {response.status_code}")
            
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")
            # Ждем меньше при ошибке
            time.sleep(300)

# Запускаем keep-alive в отдельном потоке
keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()
logger.info("✅ Keep-alive thread started")

# ========== FLASK МАРШРУТЫ ==========
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Sticker Ban Bot",
        "webhook_set": WEBHOOK_URL != "",
        "keep_alive": "active",
        "uptime": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "bot": application is not None,
        "timestamp": datetime.now().isoformat(),
        "message": "✅ Сервис работает"
    })

@app.route('/wakeup')
def wakeup():
    """Специальный endpoint для пробуждения"""
    return jsonify({
        "status": "awake",
        "message": "Сервис пробужден",
        "time": datetime.now().isoformat()
    })

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Устанавливает webhook"""
    if not WEBHOOK_URL:
        return jsonify({"error": "RENDER_EXTERNAL_URL не установлен"}), 400
    
    if not application:
        return jsonify({"error": "Бот не инициализирован. Проверьте TELEGRAM_BOT_TOKEN"}), 500
    
    try:
        import asyncio
        
        async def async_set_webhook():
            webhook_url = f"{WEBHOOK_URL}/webhook"
            await application.bot.set_webhook(url=webhook_url)
            return webhook_url
        
        # Запускаем асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        webhook_url = loop.run_until_complete(async_set_webhook())
        loop.close()
        
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        return jsonify({
            "status": "success",
            "webhook_url": webhook_url,
            "message": "Webhook успешно установлен!",
            "next_step": "Добавьте бота в группу и дайте права администратора"
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}")
        return jsonify({
            "error": str(e),
            "hint": "Проверьте TELEGRAM_BOT_TOKEN и перезапустите сервис"
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Обработчик webhook от Telegram"""
    if not application:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    try:
        import asyncio
        
        # Получаем обновление от Telegram
        update_data = request.get_json(force=True)
        
        async def process_update():
            update = Update.de_json(update_data, application.bot)
            await application.initialize()
            await application.process_update(update)
        
        # Обрабатываем асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_update())
        loop.close()
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/info')
def info():
    """Информация о сервисе"""
    return jsonify({
        "service_url": SERVICE_URL,
        "webhook_url": f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else "not set",
        "bot_token_set": bool(BOT_TOKEN and BOT_TOKEN != "placeholder"),
        "keep_alive": "active",
        "endpoints": [
            "/", "/health", "/wakeup", "/set_webhook", "/info"
        ]
    })

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 Запуск Sticker Ban Bot")
    logger.info(f"🌐 PORT: {PORT}")
    logger.info(f"🔗 SERVICE_URL: {SERVICE_URL}")
    logger.info(f"🤖 BOT INIT: {application is not None}")
    logger.info("=" * 50)
    
    # Запускаем Flask
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
