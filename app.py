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
    logger.error("Добавьте в Environment Variables:")
    logger.error("Key: TELEGRAM_BOT_TOKEN")
    logger.error("Value: ваш_токен_от_BotFather")

# Инициализация бота
application = None
try:
    if BOT_TOKEN and len(BOT_TOKEN) > 20:  # Проверка что токен похож на реальный
        application = Application.builder().token(BOT_TOKEN).build()
        logger.info("✅ Бот инициализирован")
    else:
        logger.warning("⚠️ Токен не установлен или неверный")
        logger.warning("Бот будет работать в тестовом режиме")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации бота: {e}")

class StickerBanBot:
    def __init__(self):
        self.banned_packs = self.load_data()
        logger.info("🤖 StickerBanBot готов")
    
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
        user = update.effective_user
        await update.message.reply_text(
            f"🤖 *Sticker Ban Bot*\n\n"
            f"Привет, {user.first_name}!\n\n"
            "*Функции:*\n"
            "• Запрет стикер-паков\n"
            "• Автоудаление запрещенных стикеров\n"
            "• Мут на 1 час за нарушение\n\n"
            "⚡ Работает 24/7 на Render.com",
            parse_mode='Markdown'
        )
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        await update.message.reply_text(
            "📚 *Доступные команды:*\n\n"
            "*Для админов:*\n"
            "▫️ /stickban (ответ на стикер) - запретить пак\n"
            "▫️ /stickbanlist - список запрещенных\n"
            "▫️ /stickunban <название> - разблокировать\n\n"
            "*Для всех:*\n"
            "▫️ /start - информация о боте\n"
            "▫️ /help - эта справка\n\n"
            "⚠️ *Наказание:*\n"
            "Отправка запрещенного стикера:\n"
            "• Сообщение удаляется\n"
            "• Мут на 1 час",
            parse_mode='Markdown'
        )
    
    async def stickban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрет стикер-пака"""
        try:
            chat = update.effective_chat
            user = update.effective_user
            
            # Проверка для групп
            if chat.type == 'private':
                await update.message.reply_text("❌ Эта команда только для групп!")
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
            
            # Инициализация списка для чата
            if chat_id not in self.banned_packs:
                self.banned_packs[chat_id] = []
            
            # Проверка не запрещен ли уже
            if pack_name in self.banned_packs[chat_id]:
                await update.message.reply_text(f"❌ Пак '{pack_name}' уже запрещен!")
                return
            
            # Добавляем в запрещенные
            self.banned_packs[chat_id].append(pack_name)
            self.save_data()
            
            # Удаляем стикер и команду
            try:
                await update.message.reply_to_message.delete()
            except:
                logger.warning("Не удалось удалить стикер")
            
            try:
                await update.message.delete()
            except:
                pass
            
            # Отправляем подтверждение
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"✅ *Стикер-пак запрещён!*\n\n"
                     f"📛 *Название:* `{pack_name}`\n"
                     f"👤 *Администратор:* {user.mention_html()}\n\n"
                     f"⚠️ Отправка стикеров из этого пака теперь наказывается мутом на 1 час!",
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Ошибка в stickban: {e}")
            await update.message.reply_text("❌ Ошибка. Убедитесь что бот - администратор!")
    
    async def stickbanlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список запрещенных паков"""
        chat = update.effective_chat
        
        if chat.type == 'private':
            await update.message.reply_text("❌ Эта команда только для групп!")
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
        """Разблокировка пака"""
        if not context.args:
            await update.message.reply_text("❌ Укажите название пака: `/stickunban pack_name`", parse_mode='Markdown')
            return
        
        pack_name = ' '.join(context.args)
        chat = update.effective_chat
        chat_id = str(chat.id)
        
        if chat_id in self.banned_packs and pack_name in self.banned_packs[chat_id]:
            self.banned_packs[chat_id].remove(pack_name)
            self.save_data()
            await update.message.reply_text(f"✅ Пак `{pack_name}` разблокирован!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Этот стикер-пак не был запрещён.")
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка стикеров"""
        try:
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
                # Удаляем стикер
                await update.message.delete()
                
                # Даем мут на 1 час
                until_date = datetime.now() + timedelta(hours=1)
                permissions = ChatPermissions(can_send_messages=False)
                
                await chat.restrict_member(user.id, permissions, until_date=until_date)
                
                # Уведомление
                warning = await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"🚫 *Нарушение правил!*\n\n"
                         f"👤 *Пользователь:* {user.mention_html()}\n"
                         f"⏰ *Наказание:* мут на 1 час\n"
                         f"📛 *Причина:* запрещенный стикер\n"
                         f"🖼 *Пак:* `{pack_name}`",
                    parse_mode='HTML'
                )
                
                # Удаляем уведомление через 15 секунд
                import asyncio
                await asyncio.sleep(15)
                try:
                    await warning.delete()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Ошибка обработки стикера: {e}")
            try:
                await update.message.delete()
                await update.message.reply_text("⚠️ Этот стикер-пак запрещён!")
            except:
                pass

# Создаем экземпляр бота
bot = StickerBanBot()

if application:
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_cmd))
    application.add_handler(CommandHandler("stickban", bot.stickban))
    application.add_handler(CommandHandler("stickbanlist", bot.stickbanlist))
    application.add_handler(CommandHandler("stickunban", bot.stickunban))
    application.add_handler(MessageHandler(filters.Sticker.ALL & ~filters.COMMAND, bot.handle_sticker))
    logger.info("✅ Обработчики зарегистрированы")

# ========== KEEP-ALIVE ФУНКЦИЯ ==========
def keep_alive():
    """Будит сервис каждые 5 минут чтобы избежать сна"""
    while True:
        try:
            time.sleep(300)  # 5 минут
            
            # Отправляем запрос к своему сервису
            response = requests.get(f"{SERVICE_URL}/health", timeout=10)
            logger.info(f"🔔 Keep-alive запрос: {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Keep-alive ошибка: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка keep-alive: {e}")

# Запускаем keep-alive в отдельном потоке
if SERVICE_URL.startswith("https://"):
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    logger.info("✅ Keep-alive поток запущен")

# ========== FLASK МАРШРУТЫ ==========
@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "online",
        "service": "Telegram Sticker Ban Bot",
        "webhook_ready": bool(WEBHOOK_URL),
        "bot_ready": application is not None,
        "endpoints": ["/", "/health", "/set_webhook", "/info"],
        "message": "Сервис работает. Используйте /set_webhook для настройки бота."
    })

@app.route('/health')
def health():
    """Health check для Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Устанавливает webhook для Telegram"""
    if not WEBHOOK_URL:
        return jsonify({
            "error": "RENDER_EXTERNAL_URL не установлен",
            "fix": "Добавьте в Environment Variables: RENDER_EXTERNAL_URL=https://ssticer-deletor.onrender.com"
        }), 400
    
    if not application:
        return jsonify({
            "error": "Бот не инициализирован",
            "fix": "Проверьте TELEGRAM_BOT_TOKEN в Environment Variables"
        }), 500
    
    try:
        # Устанавливаем webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        import asyncio
        
        async def async_set():
            await application.bot.set_webhook(url=webhook_url)
            return webhook_url
        
        # Запускаем асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        webhook_url = loop.run_until_complete(async_set())
        loop.close()
        
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        return jsonify({
            "status": "success",
            "message": "✅ Webhook успешно установлен!",
            "webhook_url": webhook_url,
            "next_steps": [
                "1. Откройте Telegram и найдите вашего бота",
                "2. Напишите /start для проверки",
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
        
        import asyncio
        
        async def process_update():
            # Создаем объект Update из данных
            update = Update.de_json(update_data, application.bot)
            # Обрабатываем обновление
            await application.process_update(update)
        
        # Обрабатываем асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_update())
        loop.close()
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/info')
def info():
    """Информация о сервисе"""
    return jsonify({
        "service_url": SERVICE_URL,
        "webhook_url": f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else "не установлен",
        "bot_initialized": application is not None,
        "environment": {
            "BOT_TOKEN_set": bool(os.environ.get('TELEGRAM_BOT_TOKEN')),
            "RENDER_EXTERNAL_URL_set": bool(WEBHOOK_URL),
            "PORT": PORT
        },
        "keep_alive": "активен" if SERVICE_URL.startswith("https://") else "не активен"
    })

# ========== ЗАПУСК СЕРВИСА ==========
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 Запуск Sticker Ban Bot")
    logger.info(f"🌐 Сервис: {SERVICE_URL}")
    logger.info(f"🔧 Бот инициализирован: {application is not None}")
    logger.info(f"📡 Webhook URL: {WEBHOOK_URL}")
    logger.info("=" * 50)
    
    # Запускаем Flask
    app.run(host='0.0.0.0', port=PORT, debug=False)
