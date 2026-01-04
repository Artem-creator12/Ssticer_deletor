import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import asyncio

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
logger.info("🚀 Инициализация Sticker Ban Bot")
logger.info(f"🌐 PORT: {PORT}")
logger.info(f"🔗 WEBHOOK_URL: {WEBHOOK_URL}")
logger.info(f"🔑 BOT_TOKEN: {'установлен' if BOT_TOKEN else 'НЕТ'}")
logger.info("=" * 50)

# Глобальные переменные
application = None
bot_instance = None

class StickerBanBot:
    def __init__(self):
        self.banned_packs = {}
        self.load_data()
        logger.info("🤖 StickerBanBot инициализирован")
    
    def load_data(self):
        """Загружает данные из файла"""
        try:
            if os.path.exists('data.json'):
                with open('data.json', 'r') as f:
                    self.banned_packs = json.load(f)
                    logger.info(f"📂 Загружено {len(self.banned_packs)} чатов")
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
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        await update.message.reply_text(
            f"🤖 *Sticker Ban Bot*\n\n"
            f"Привет, {user.first_name}!\n\n"
            "*Функции:*\n"
            "• Запрет стикер-паков командой /stickban\n"
            "• Автоудаление запрещенных стикеров\n"
            "• Мут на 1 час за нарушение\n\n"
            "⚡ Работает 24/7 на Render.com\n\n"
            "Используйте /help для списка команд",
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        await update.message.reply_text(
            "📚 *Доступные команды:*\n\n"
            "*Для админов:*\n"
            "▫️ /stickban (ответ на стикер) - запретить весь пак\n"
            "▫️ /stickbanlist - список запрещенных паков\n"
            "▫️ /stickunban <название> - разблокировать пак\n\n"
            "*Для всех:*\n"
            "▫️ /start - информация о боте\n"
            "▫️ /help - эта справка\n\n"
            "⚠️ *Наказание за нарушение:*\n"
            "• Сообщение удаляется\n"
            "• Мут на 1 час\n"
            "• Уведомление в чат",
            parse_mode='Markdown'
        )
    
    async def stickban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stickban - запретить стикер-пак"""
        try:
            chat = update.effective_chat
            
            # Проверяем что это группа
            if chat.type == 'private':
                await update.message.reply_text("❌ Эта команда работает только в группах!")
                return
            
            # Проверяем что это ответ на стикер
            if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
                await update.message.reply_text("❌ Ответьте на стикер который хотите запретить!")
                return
            
            sticker = update.message.reply_to_message.sticker
            pack_name = sticker.set_name
            
            if not pack_name:
                await update.message.reply_text("❌ Этот стикер не из набора!")
                return
            
            # Получаем ID чата
            chat_id = str(chat.id)
            
            # Инициализируем список для чата если нужно
            if chat_id not in self.banned_packs:
                self.banned_packs[chat_id] = []
            
            # Проверяем не запрещен ли уже пак
            if pack_name in self.banned_packs[chat_id]:
                await update.message.reply_text(f"❌ Стикер-пак '{pack_name}' уже запрещен!")
                return
            
            # Добавляем пак в запрещенные
            self.banned_packs[chat_id].append(pack_name)
            self.save_data()
            
            # Пытаемся удалить оригинальный стикер
            try:
                await update.message.reply_to_message.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить стикер: {e}")
            
            # Отправляем подтверждение
            await update.message.reply_text(
                f"✅ *Стикер-пак запрещён!*\n\n"
                f"📛 *Название:* `{pack_name}`\n\n"
                f"⚠️ Теперь отправка стикеров из этого пака наказывается:\n"
                f"• Удаление сообщения\n"
                f"• Мут на 1 час",
                parse_mode='Markdown'
            )
            
            logger.info(f"Пак '{pack_name}' запрещен в чате {chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка в команде /stickban: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Убедитесь что бот - администратор!")
    
    async def stickbanlist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stickbanlist - список запрещенных паков"""
        try:
            chat = update.effective_chat
            chat_id = str(chat.id)
            
            if chat_id in self.banned_packs and self.banned_packs[chat_id]:
                packs = "\n".join([f"• `{pack}`" for pack in self.banned_packs[chat_id]])
                await update.message.reply_text(
                    f"📋 *Запрещенные стикер-паки в этом чате:*\n\n{packs}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("✅ В этом чате нет запрещенных стикер-паков.")
                
        except Exception as e:
            logger.error(f"Ошибка в команде /stickbanlist: {e}")
            await update.message.reply_text("❌ Произошла ошибка")
    
    async def stickunban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stickunban - разблокировать пак"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "❌ Укажите название пака:\n`/stickunban pack_name`",
                    parse_mode='Markdown'
                )
                return
            
            pack_name = ' '.join(context.args)
            chat = update.effective_chat
            chat_id = str(chat.id)
            
            if chat_id in self.banned_packs and pack_name in self.banned_packs[chat_id]:
                self.banned_packs[chat_id].remove(pack_name)
                self.save_data()
                await update.message.reply_text(
                    f"✅ Стикер-пак `{pack_name}` разблокирован!",
                    parse_mode='Markdown'
                )
                logger.info(f"Пак '{pack_name}' разблокирован в чате {chat_id}")
            else:
                await update.message.reply_text("❌ Этот стикер-пак не был запрещён.")
                
        except Exception as e:
            logger.error(f"Ошибка в команде /stickunban: {e}")
            await update.message.reply_text("❌ Произошла ошибка")
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик стикеров"""
        try:
            chat = update.effective_chat
            user = update.effective_user
            sticker = update.message.sticker
            
            # Игнорируем приватные чаты
            if chat.type == 'private':
                return
            
            chat_id = str(chat.id)
            pack_name = sticker.set_name
            
            # Проверяем запрещен ли этот пак
            if chat_id in self.banned_packs and pack_name in self.banned_packs[chat_id]:
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
                
                # Отправляем уведомление о муте
                warning_msg = await update.message.reply_text(
                    f"🚫 *Нарушение правил!*\n\n"
                    f"👤 *Пользователь:* {user.mention_html()}\n"
                    f"⏰ *Наказание:* мут на 1 час\n"
                    f"📛 *Причина:* отправка запрещенного стикера\n"
                    f"🖼 *Пак:* `{pack_name}`",
                    parse_mode='HTML'
                )
                
                # Удаляем уведомление через 15 секунд
                await asyncio.sleep(15)
                try:
                    await warning_msg.delete()
                except:
                    pass
                
                logger.info(f"Пользователь {user.id} получил мут за пак '{pack_name}' в чате {chat_id}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки стикера: {e}")
            # Если не удалось замутить, хотя бы удаляем стикер
            try:
                await update.message.delete()
                temp_msg = await update.message.reply_text(
                    f"⚠️ Этот стикер-пак запрещён в этом чате!",
                    parse_mode='HTML'
                )
                await asyncio.sleep(5)
                await temp_msg.delete()
            except Exception as e2:
                logger.error(f"Не удалось удалить сообщение: {e2}")

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
def init_bot():
    """Инициализирует Telegram бота"""
    global application, bot_instance
    
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
        logger.error("Добавьте переменную окружения TELEGRAM_BOT_TOKEN")
        return False
    
    try:
        # Создаем приложение Telegram
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Создаем экземпляр бота
        bot_instance = StickerBanBot()
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", bot_instance.start_command))
        application.add_handler(CommandHandler("help", bot_instance.help_command))
        application.add_handler(CommandHandler("stickban", bot_instance.stickban_command))
        application.add_handler(CommandHandler("stickbanlist", bot_instance.stickbanlist_command))
        application.add_handler(CommandHandler("stickunban", bot_instance.stickunban_command))
        
        # Регистрируем обработчик стикеров
        application.add_handler(MessageHandler(filters.Sticker.ALL & ~filters.COMMAND, bot_instance.handle_sticker))
        
        logger.info("✅ Telegram бот инициализирован")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        return False

# ========== FLASK МАРШРУТЫ ==========
@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "online",
        "service": "Telegram Sticker Ban Bot",
        "bot_ready": application is not None,
        "webhook_ready": bool(WEBHOOK_URL),
        "message": "✅ Сервис работает!",
        "endpoints": ["/", "/health", "/set_webhook", "/info"]
    })

@app.route('/health')
def health():
    """Health check для Render"""
    return jsonify({
        "status": "healthy",
        "bot_initialized": application is not None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/set_webhook')
def set_webhook():
    """Устанавливает webhook для Telegram"""
    if not WEBHOOK_URL:
        return jsonify({
            "error": "RENDER_EXTERNAL_URL не установлен",
            "fix": "Добавьте в Environment Variables: RENDER_EXTERNAL_URL=https://ssticer-deletor.onrender.com"
        }), 400
    
    if not application:
        return jsonify({
            "error": "Telegram бот не инициализирован",
            "fix": "Проверьте TELEGRAM_BOT_TOKEN в Environment Variables"
        }), 500
    
    try:
        # Устанавливаем webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        async def setup_webhook():
            await application.bot.set_webhook(url=webhook_url)
            return webhook_url
        
        # Запускаем асинхронно
        webhook_url_result = asyncio.run(setup_webhook())
        
        logger.info(f"✅ Webhook установлен: {webhook_url_result}")
        
        return jsonify({
            "status": "success",
            "message": "✅ Webhook успешно установлен!",
            "webhook_url": webhook_url_result,
            "next_steps": [
                "1. Откройте Telegram и найдите вашего бота",
                "2. Напишите команду /start для проверки",
                "3. Добавьте бота в группу",
                "4. Дайте права администратора (удалять сообщения, банить)",
                "5. Ответьте /stickban на стикер для тестирования"
            ]
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}")
        return jsonify({
            "error": str(e),
            "hint": "Проверьте токен и перезапустите сервис"
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Обработчик входящих обновлений от Telegram"""
    if not application:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    try:
        # Получаем данные от Telegram
        update_data = request.get_json(force=True)
        
        async def process_update():
            # Создаем объект Update
            update = Update.de_json(update_data, application.bot)
            # Инициализируем приложение если нужно
            await application.initialize()
            # Обрабатываем обновление
            await application.process_update(update)
        
        # Обрабатываем асинхронно
        asyncio.run(process_update())
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/info')
def info():
    """Информация о сервисе"""
    return jsonify({
        "service_url": "https://ssticer-deletor.onrender.com",
        "webhook_url": f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else "не установлен",
        "bot_token": "установлен" if BOT_TOKEN else "не установлен",
        "bot_initialized": application is not None,
        "chats_with_bans": len(bot_instance.banned_packs) if bot_instance else 0,
        "python_version": os.sys.version,
        "time": datetime.now().isoformat()
    })

# ========== ЗАПУСК СЕРВИСА ==========
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 Запуск Sticker Ban Bot")
    logger.info("=" * 50)
    
    # Инициализируем бота
    bot_ready = init_bot()
    
    if bot_ready and WEBHOOK_URL:
        try:
            # Устанавливаем webhook при запуске
            webhook_url = f"{WEBHOOK_URL}/webhook"
            asyncio.run(application.bot.set_webhook(url=webhook_url))
            logger.info(f"✅ Webhook установлен при запуске: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook при запуске: {e}")
    
    # Запускаем Flask
    app.run(host='0.0.0.0', port=PORT, debug=False)
