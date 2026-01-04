import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import telebot
from telebot.types import ChatPermissions

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
logger.info("🚀 Sticker Ban Bot (синхронная версия)")
logger.info(f"🌐 PORT: {PORT}")
logger.info(f"🔗 WEBHOOK_URL: {WEBHOOK_URL}")
logger.info(f"🤖 BOT_TOKEN: {'установлен' if BOT_TOKEN else 'НЕТ'}")
logger.info("=" * 50)

# Инициализация бота
bot = None
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
        logger.info("✅ Бот инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        bot = None

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

# Создаем экземпляр бота
sticker_bot = StickerBanBot()

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработчик команды /start"""
    try:
        bot.reply_to(message,
            f"🤖 *Sticker Ban Bot*\n\n"
            f"Привет, {message.from_user.first_name}!\n\n"
            "*Функции:*\n"
            "• Запрет стикер-паков командой /stickban\n"
            "• Автоудаление запрещенных стикеров\n"
            "• Мут на 1 час за нарушение\n\n"
            "⚡ Работает 24/7 на Render.com\n\n"
            "Используйте /help для списка команд",
            parse_mode='Markdown'
        )
        logger.info(f"Команда /start от {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Обработчик команды /help"""
    bot.reply_to(message,
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

@bot.message_handler(commands=['stickban'])
def stickban_command(message):
    """Команда /stickban - запретить стикер-пак"""
    try:
        # Проверяем что это ответ на стикер
        if not message.reply_to_message or not message.reply_to_message.sticker:
            bot.reply_to(message, "❌ Ответьте на стикер который хотите запретить!")
            return
        
        sticker = message.reply_to_message.sticker
        pack_name = sticker.set_name
        
        if not pack_name:
            bot.reply_to(message, "❌ Этот стикер не из набора!")
            return
        
        # Получаем ID чата
        chat_id = str(message.chat.id)
        
        # Инициализируем список для чата если нужно
        if chat_id not in sticker_bot.banned_packs:
            sticker_bot.banned_packs[chat_id] = []
        
        # Проверяем не запрещен ли уже пак
        if pack_name in sticker_bot.banned_packs[chat_id]:
            bot.reply_to(message, f"❌ Стикер-пак '{pack_name}' уже запрещен!")
            return
        
        # Добавляем пак в запрещенные
        sticker_bot.banned_packs[chat_id].append(pack_name)
        sticker_bot.save_data()
        
        # Пытаемся удалить оригинальный стикер
        try:
            bot.delete_message(message.chat.id, message.reply_to_message.message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить стикер: {e}")
        
        # Отправляем подтверждение
        bot.reply_to(message,
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
        bot.reply_to(message, "❌ Произошла ошибка. Убедитесь что бот - администратор!")

@bot.message_handler(commands=['stickbanlist'])
def stickbanlist_command(message):
    """Команда /stickbanlist - список запрещенных паков"""
    try:
        chat_id = str(message.chat.id)
        
        if chat_id in sticker_bot.banned_packs and sticker_bot.banned_packs[chat_id]:
            packs = "\n".join([f"• `{pack}`" for pack in sticker_bot.banned_packs[chat_id]])
            bot.reply_to(message,
                f"📋 *Запрещенные стикер-паки в этом чате:*\n\n{packs}",
                parse_mode='Markdown'
            )
        else:
            bot.reply_to(message, "✅ В этом чате нет запрещенных стикер-паков.")
            
    except Exception as e:
        logger.error(f"Ошибка в команде /stickbanlist: {e}")
        bot.reply_to(message, "❌ Произошла ошибка")

@bot.message_handler(commands=['stickunban'])
def stickunban_command(message):
    """Команда /stickunban - разблокировать пак"""
    try:
        # Получаем аргументы команды
        if not message.text or len(message.text.split()) < 2:
            bot.reply_to(message, "❌ Укажите название пака:\n`/stickunban pack_name`", parse_mode='Markdown')
            return
        
        # Извлекаем название пака
        pack_name = ' '.join(message.text.split()[1:])
        chat_id = str(message.chat.id)
        
        if chat_id in sticker_bot.banned_packs and pack_name in sticker_bot.banned_packs[chat_id]:
            sticker_bot.banned_packs[chat_id].remove(pack_name)
            sticker_bot.save_data()
            bot.reply_to(message, f"✅ Стикер-пак `{pack_name}` разблокирован!", parse_mode='Markdown')
            logger.info(f"Пак '{pack_name}' разблокирован в чате {chat_id}")
        else:
            bot.reply_to(message, "❌ Этот стикер-пак не был запрещён.")
            
    except Exception as e:
        logger.error(f"Ошибка в команде /stickunban: {e}")
        bot.reply_to(message, "❌ Произошла ошибка")

@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    """Обработчик стикеров"""
    try:
        # Игнорируем приватные чаты
        if message.chat.type == 'private':
            return
        
        chat_id = str(message.chat.id)
        pack_name = message.sticker.set_name
        
        # Проверяем запрещен ли этот пак
        if chat_id in sticker_bot.banned_packs and pack_name in sticker_bot.banned_packs[chat_id]:
            # Удаляем стикер
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить стикер: {e}")
                return
            
            # Даем мут на 1 час
            until_date = datetime.now() + timedelta(hours=1)
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            
            try:
                bot.restrict_chat_member(
                    message.chat.id,
                    message.from_user.id,
                    permissions=permissions,
                    until_date=until_date
                )
            except Exception as e:
                logger.error(f"Не удалось замутить пользователя: {e}")
                # Если не удалось замутить, хотя бы предупредим
                warning = bot.send_message(
                    message.chat.id,
                    f"⚠️ {message.from_user.first_name}, этот стикер-пак запрещён!",
                    parse_mode='HTML'
                )
                # Удаляем предупреждение через 5 секунд
                threading.Thread(target=delete_message_after_delay, 
                               args=(message.chat.id, warning.message_id, 5)).start()
                return
            
            # Отправляем уведомление о муте
            warning_msg = bot.send_message(
                message.chat.id,
                f"🚫 *Нарушение правил!*\n\n"
                f"👤 *Пользователь:* {message.from_user.first_name}\n"
                f"⏰ *Наказание:* мут на 1 час\n"
                f"📛 *Причина:* отправка запрещенного стикера\n"
                f"🖼 *Пак:* `{pack_name}`",
                parse_mode='Markdown'
            )
            
            # Удаляем уведомление через 15 секунд
            threading.Thread(target=delete_message_after_delay, 
                           args=(message.chat.id, warning_msg.message_id, 15)).start()
            
            logger.info(f"Пользователь {message.from_user.id} получил мут за пак '{pack_name}' в чате {chat_id}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки стикера: {e}")

def delete_message_after_delay(chat_id, message_id, delay):
    """Удаляет сообщение через указанную задержку"""
    time.sleep(delay)
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

# ========== FLASK МАРШРУТЫ ==========
@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "online",
        "service": "Telegram Sticker Ban Bot",
        "bot_ready": bot is not None,
        "message": "✅ Сервис работает!",
        "endpoints": ["/", "/health", "/set_webhook", "/info"]
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
    """Устанавливает webhook для Telegram"""
    if not WEBHOOK_URL:
        return jsonify({
            "error": "RENDER_EXTERNAL_URL не установлен",
            "fix": "Добавьте в Environment Variables: RENDER_EXTERNAL_URL=https://ssticer-deletor.onrender.com"
        }), 400
    
    if not bot:
        return jsonify({
            "error": "Telegram бот не инициализирован",
            "fix": "Проверьте TELEGRAM_BOT_TOKEN в Environment Variables"
        }), 500
    
    try:
        # Устанавливаем webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Удаляем старый webhook если есть
        bot.remove_webhook()
        time.sleep(1)
        
        # Устанавливаем новый webhook
        bot.set_webhook(url=webhook_url)
        
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        return jsonify({
            "status": "success",
            "message": "✅ Webhook успешно установлен!",
            "webhook_url": webhook_url,
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
    if not bot:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    try:
        # Получаем данные от Telegram
        json_data = request.get_json(force=True)
        
        # Создаем объект Update из данных
        update = telebot.types.Update.de_json(json_data)
        
        # Обрабатываем обновление
        bot.process_new_updates([update])
        
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
        "bot_initialized": bot is not None,
        "chats_with_bans": len(sticker_bot.banned_packs),
        "time": datetime.now().isoformat()
    })

# ========== ЗАПУСК СЕРВИСА ==========
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 Запуск Sticker Ban Bot")
    logger.info("=" * 50)
    
    # Если есть webhook URL, устанавливаем его
    if bot and WEBHOOK_URL:
        try:
            webhook_url = f"{WEBHOOK_URL}/webhook"
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook установлен при запуске: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook при запуске: {e}")
    
    # Запускаем Flask
    logger.info(f"🌐 Сервис запущен на порту {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
