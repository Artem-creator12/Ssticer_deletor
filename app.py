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

logger.info("=" * 50)
logger.info("🚀 Sticker Ban Bot")
logger.info(f"🌐 PORT: {PORT}")
logger.info(f"🔗 WEBHOOK_URL: {WEBHOOK_URL}")
logger.info(f"🤖 BOT_TOKEN: {'установлен' if BOT_TOKEN else 'НЕТ'}")
logger.info("=" * 50)

# Глобальные переменные
application = None
bot_instance = None

class StickerBanBot:
    def __init__(self):
        self.banned_packs = {}
        self.load_data()
        logger.info("✅ StickerBanBot создан")
    
    def load_data(self):
        """Загружает данные из файла"""
        try:
            if os.path.exists('data.json'):
                with open('data.json', 'r') as f:
                    self.banned_packs = json.load(f)
                    logger.info(f"📂 Загружено {len(self.banned_packs)} чатов")
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            self.banned_packs = {}
    
    def save_data(self):
        """Сохраняет данные в файл"""
        try:
            with open('data.json', 'w') as f:
                json.dump(self.banned_packs, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        await update.message.reply_text(
            f"🤖 *Sticker Ban Bot*\n\n"
            f"Привет, {user.first_name}!\n\n"
            "*Блокировка стикер-паков:*\n"
            "• /stickban (ответ на стикер) - запретить\n"
            "• /stickbanlist - список запрещенных\n"
            "• /help - помощь\n\n"
            "⚠️ Нарушение = мут 1 час + удаление",
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        await update.message.reply_text(
            "📚 *Команды:*\n\n"
            "*Админам:*\n"
            "▫️ /stickban (ответ на стикер) - запретить пак\n"
            "▫️ /stickbanlist - список\n"
            "▫️ /stickunban <название> - разблокировать\n\n"
            "*Всем:*\n"
            "▫️ /start - информация\n"
            "▫️ /help - справка\n\n"
            "*Наказание:*\n"
            "Запрещенный стикер = удаление + мут 1 час",
            parse_mode='Markdown'
        )
    
    async def stickban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stickban"""
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
    
    async def stickbanlist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stickbanlist"""
        chat = update.effective_chat
        chat_id = str(chat.id)
        
        if chat_id in self.banned_packs and self.banned_packs[chat_id]:
            packs = "\n".join([f"• `{pack}`" for pack in self.banned_packs[chat_id]])
            await update.message.reply_text(f"📋 *Запрещенные паки:*\n\n{packs}", parse_mode='Markdown')
        else:
            await update.message.reply_text("✅ Нет запрещенных паков")
    
    async def stickunban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stickunban"""
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
            logger.error(f"Ошибка обработки стикера: {e}")

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
def init_bot():
    """Инициализирует Telegram бота"""
    global application, bot_instance
    
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
        return False
    
    try:
        # Создаем приложение Telegram
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Создаем экземпляр бота
        bot_instance = StickerBanBot()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", bot_instance.start_command))
        application.add_handler(CommandHandler("help", bot_instance.help_command))
        application.add_handler(CommandHandler("stickban", bot_instance.stickban_command))
        application.add_handler(CommandHandler("stickbanlist", bot_instance.stickbanlist_command))
        application.add_handler(CommandHandler("stickunban", bot_instance.stickunban_command))
        application.add_handler(MessageHandler(filters.Sticker.ALL & ~filters.COMMAND, bot_instance.handle_sticker))
        
        logger.info("✅ Telegram бот инициализирован")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        return False

# ========== ASYNCIO EVENT LOOP FIX ==========
import asyncio
import nest_asyncio

# Применяем патч для nest_asyncio
nest_asyncio.apply()

def run_async(coro):
    """Запускает асинхронную функцию"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Ошибка запуска async: {e}")
        raise

# ========== FLASK МАРШРУТЫ ==========
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Sticker Ban Bot",
        "bot": "ready" if application else "not ready",
        "message": "✅ Сервис работает"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "time": datetime.now().isoformat()})

@app.route('/set_webhook')
def set_webhook():
    """Устанавливает webhook"""
    if not WEBHOOK_URL:
        return jsonify({
            "error": "RENDER_EXTERNAL_URL не установлен",
            "fix": "Добавьте: RENDER_EXTERNAL_URL=https://ssticer-deletor.onrender.com"
        }), 400
    
    if not application:
        return jsonify({
            "error": "Бот не инициализирован",
            "fix": "Проверьте TELEGRAM_BOT_TOKEN"
        }), 500
    
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Используем нашу функцию run_async
        run_async(application.bot.set_webhook(url=webhook_url))
        
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
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
def webhook_handler():
    """Обработчик webhook"""
    if not application:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    try:
        update_data = request.get_json(force=True)
        
        # Создаем новую задачу для обработки
        async def process():
            update = Update.de_json(update_data, application.bot)
            await application.initialize()
            await application.process_update(update)
        
        # Запускаем в отдельном потоке
        threading.Thread(
            target=lambda: run_async(process()),
            daemon=True
        ).start()
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/info')
def info():
    return jsonify({
        "service": "https://ssticer-deletor.onrender.com",
        "webhook": f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else "не установлен",
        "bot": "готов" if application else "не готов",
        "time": datetime.now().isoformat()
    })

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    # Инициализируем бота
    bot_ready = init_bot()
    
    # Если есть webhook URL, устанавливаем его
    if bot_ready and WEBHOOK_URL:
        try:
            webhook_url = f"{WEBHOOK_URL}/webhook"
            run_async(application.bot.set_webhook(url=webhook_url))
            logger.info(f"✅ Webhook установлен при запуске: {webhook_url}")
        except Exception as e:
            logger.error(f"Ошибка установки webhook: {e}")
    
    # Запускаем Flask
    logger.info(f"🚀 Запуск сервиса на порту {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
