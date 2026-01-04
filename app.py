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
BOT_USERNAME = "Nazuna_chan_bot"  # Замените на реальное имя вашего бота

logger.info("=" * 50)
logger.info("🚀 🌸 Помощница Назуна-чан 🌸")
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
    
    def load_data(self):
        """Загружает данные из файла"""
        try:
            if os.path.exists('data.json'):
                with open('data.json', 'r') as f:
                    self.banned_packs = json.load(f)
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

def is_admin(chat_id, user_id):
    """Проверяет, является ли пользователь администратором"""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        return False

def get_full_permissions():
    """Возвращает полные права для пользователя"""
    return ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False
    )

def check_command(text, command_variants):
    """Проверяет текст на наличие команды (без /)"""
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Удаляем упоминание бота если есть
    if f"@{BOT_USERNAME}".lower() in text_lower:
        text_lower = text_lower.replace(f"@{BOT_USERNAME}".lower(), "").strip()
    
    # Проверяем все варианты команд
    for variant in command_variants:
        if text_lower == variant.lower():
            return True
    
    return False

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработчик команды /start"""
    try:
        bot.reply_to(message,
            f"🌸 *Помощница Назуна-чан* 🌸\n\n"
            f"Привет, {message.from_user.first_name}!\n\n"
            "*Функции для админов:*\n"
            "• `стикбан` (ответ на стикер) - запретить пак\n"
            "• `стикбанлист` - список запрещенных\n"
            "• `стикразбан <название>` - разблокировать\n"
            "• `размут @username` - снять мут с пользователя\n\n"
            "⚠️ *Наказание за нарушение:*\n"
            "Запрещенный стикер = удаление + мут 1 час\n\n"
            "⚡ Работает 24/7 на Render.com",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Обработчик команды /help"""
    help_text = (
        "📚 🌸 *Помощница Назуна-чан* 🌸 - Помощь\n\n"
        "*Только для администраторов:*\n"
        "▫️ `стикбан` (ответ на стикер) - запретить весь пак\n"
        "▫️ `стикбанлист` - список запрещенных паков\n"
        "▫️ `стикразбан <название>` - разблокировать пак\n"
        "▫️ `размут @username` - снять мут с пользователя\n\n"
        "*Для всех:*\n"
        "▫️ /start - информация о боте\n"
        "▫️ /help - эта справка\n\n"
        "⚠️ *Наказание за нарушение:*\n"
        "Отправка запрещенного стикера:\n"
        "• Сообщение удаляется\n"
        "• Мут на 1 час\n"
        "• Уведомление в чат\n\n"
        "*Требования:*\n"
        "Бот должен быть администратором с правами:\n"
        "✓ Удалять сообщения\n"
        "✓ Блокировать пользователей\n"
        "✓ Размучивать пользователей"
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')

# ========== ОБРАБОТКА ОБЫЧНЫХ КОМАНД (без /) ==========

def handle_unmute_command(message):
    """Команда размут - снять мут с пользователя (только для админов)"""
    try:
        # Проверяем что это группа
        if message.chat.type == 'private':
            bot.reply_to(message, "❌ Эта команда работает только в группах!")
            return
        
        # Проверяем что отправитель - администратор
        if not is_admin(message.chat.id, message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администраторов чата!")
            return
        
        # Определяем пользователя для размута
        target_user_id = None
        target_username = None
        
        # Вариант 1: Ответ на сообщение пользователя
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user_id = message.reply_to_message.from_user.id
            target_username = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
        
        # Вариант 2: По юзернейму (@username) в тексте
        elif '@' in message.text:
            # Ищем юзернейм в тексте
            import re
            username_match = re.search(r'@(\w+)', message.text)
            if username_match:
                username = username_match.group(1)
                # Ищем пользователя по юзернейму в чате
                try:
                    chat_member = bot.get_chat_member(message.chat.id, f"@{username}")
                    target_user_id = chat_member.user.id
                    target_username = chat_member.user.username or chat_member.user.first_name
                except Exception as e:
                    logger.error(f"Не найден пользователь @{username}: {e}")
                    bot.reply_to(message, f"❌ Пользователь @{username} не найден в этом чате!")
                    return
        
        # Вариант 3: По ID пользователя (если указан числовой ID)
        else:
            # Пытаемся найти ID в тексте
            import re
            id_match = re.search(r'(\d+)', message.text)
            if id_match:
                target_user_id = int(id_match.group(1))
                try:
                    chat_member = bot.get_chat_member(message.chat.id, target_user_id)
                    target_username = chat_member.user.username or chat_member.user.first_name
                except Exception as e:
                    logger.error(f"Не найден пользователь ID {target_user_id}: {e}")
                    bot.reply_to(message, f"❌ Пользователь с ID {target_user_id} не найден в этом чате!")
                    return
        
        if not target_user_id:
            bot.reply_to(message, 
                "❌ Не удалось определить пользователя.\n"
                "Используйте:\n"
                "• `размут @username`\n"
                "• Ответьте `размут` на сообщение пользователя",
                parse_mode='Markdown'
            )
            return
        
        # Проверяем что не пытаемся размутить себя (бота)
        if target_user_id == bot.get_me().id:
            bot.reply_to(message, "❌ Не могу размутить самого себя!")
            return
        
        # Проверяем что не пытаемся размутить администратора (если мы не создатель)
        try:
            target_member = bot.get_chat_member(message.chat.id, target_user_id)
            if target_member.status in ['administrator', 'creator']:
                # Проверяем что мы создатель, чтобы размутить админа
                requester = bot.get_chat_member(message.chat.id, message.from_user.id)
                if requester.status != 'creator':
                    bot.reply_to(message, "❌ Не могу размутить администратора!")
                    return
        except:
            pass
        
        # Снимаем мут (устанавливаем полные права)
        full_permissions = get_full_permissions()
        
        try:
            bot.restrict_chat_member(
                message.chat.id,
                target_user_id,
                permissions=full_permissions,
                until_date=0  # 0 = снять ограничения немедленно
            )
            
            # Отправляем подтверждение (НЕ удаляем)
            bot.send_message(
                message.chat.id,
                f"✅ *Мут снят!* 🌸\n\n"
                f"👤 *Пользователь:* {target_username}\n"
                f"👮 *Администратор:* {message.from_user.first_name}",
                parse_mode='Markdown'
            )
            
            logger.info(f"Мут снят с пользователя {target_user_id} в чате {message.chat.id} админом {message.from_user.id}")
            
        except Exception as e:
            logger.error(f"Ошибка при снятии мута: {e}")
            bot.reply_to(message, f"❌ Не удалось снять мут. Убедитесь что пользователь замучен и у бота есть права!")
            
    except Exception as e:
        logger.error(f"Ошибка в команде размут: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Проверьте права бота!")

def handle_stickban_command(message):
    """Команда стикбан - запретить стикер-пак (только для админов)"""
    try:
        # Проверяем что это группа
        if message.chat.type == 'private':
            bot.reply_to(message, "❌ Эта команда работает только в группах!")
            return
        
        # Проверяем что отправитель - администратор
        if not is_admin(message.chat.id, message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администраторов чата!")
            return
        
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
        chat_id_str = str(message.chat.id)
        
        # Инициализируем список для чата если нужно
        if chat_id_str not in sticker_bot.banned_packs:
            sticker_bot.banned_packs[chat_id_str] = []
        
        # Проверяем не запрещен ли уже пак
        if pack_name in sticker_bot.banned_packs[chat_id_str]:
            bot.reply_to(message, f"❌ Стикер-пак '{pack_name}' уже запрещен!")
            return
        
        # Добавляем пак в запрещенные
        sticker_bot.banned_packs[chat_id_str].append(pack_name)
        sticker_bot.save_data()
        
        # Удаляем только оригинальный стикер (не команду админа!)
        try:
            bot.delete_message(message.chat.id, message.reply_to_message.message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить стикер: {e}")
        
        # Отправляем подтверждение и НЕ УДАЛЯЕМ ЕГО
        bot.send_message(
            message.chat.id,
            f"🌸 *Стикер-пак запрещён!* 🌸\n\n"
            f"📛 *Название:* `{pack_name}`\n"
            f"👤 *Администратор:* {message.from_user.first_name}\n\n"
            f"⚠️ Отправка стикеров из этого пака теперь наказывается мутом на 1 час!",
            parse_mode='Markdown'
        )
        
        logger.info(f"Пак '{pack_name}' запрещен в чате {chat_id_str} админом {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка в команде стикбан: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Убедитесь что бот - администратор!")

def handle_stickbanlist_command(message):
    """Команда стикбанлист - список запрещенных паков"""
    try:
        chat_id_str = str(message.chat.id)
        
        if chat_id_str in sticker_bot.banned_packs and sticker_bot.banned_packs[chat_id_str]:
            packs = "\n".join([f"• `{pack}`" for pack in sticker_bot.banned_packs[chat_id_str]])
            bot.reply_to(message,
                f"🌸 *Запрещенные стикер-паки в этом чате:* 🌸\n\n{packs}",
                parse_mode='Markdown'
            )
        else:
            bot.reply_to(message, "🌸 В этом чате нет запрещенных стикер-паков. 🌸")
            
    except Exception as e:
        logger.error(f"Ошибка в команде стикбанлист: {e}")
        bot.reply_to(message, "❌ Произошла ошибка")

def handle_stickunban_command(message):
    """Команда стикразбан - разблокировать пак (только для админов)"""
    try:
        # Проверяем что это группа
        if message.chat.type == 'private':
            bot.reply_to(message, "❌ Эта команда работает только в группах!")
            return
        
        # Проверяем что отправитель - администратор
        if not is_admin(message.chat.id, message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администраторов чата!")
            return
        
        # Получаем название пака из текста
        text = message.text.lower()
        
        # Удаляем упоминание бота если есть
        if f"@{BOT_USERNAME}".lower() in text:
            text = text.replace(f"@{BOT_USERNAME}".lower(), "")
        
        # Удаляем команду из текста
        for variant in ["стикразбан", "стикразбан", "стикразбан"]:
            text = text.replace(variant, "").strip()
        
        if not text:
            bot.reply_to(message, "❌ Укажите название пака:\n`стикразбан название_пака`", parse_mode='Markdown')
            return
        
        pack_name = text.strip()
        chat_id_str = str(message.chat.id)
        
        if chat_id_str in sticker_bot.banned_packs and pack_name in sticker_bot.banned_packs[chat_id_str]:
            sticker_bot.banned_packs[chat_id_str].remove(pack_name)
            sticker_bot.save_data()
            
            # Отправляем подтверждение (НЕ удаляем)
            bot.send_message(
                message.chat.id,
                f"🌸 *Стикер-пак разблокирован!* 🌸\n\n"
                f"📛 *Название:* `{pack_name}`\n"
                f"👤 *Администратор:* {message.from_user.first_name}",
                parse_mode='Markdown'
            )
            logger.info(f"Пак '{pack_name}' разблокирован в чате {chat_id_str} админом {message.from_user.id}")
        else:
            bot.reply_to(message, "❌ Этот стикер-пак не был запрещён.")
            
    except Exception as e:
        logger.error(f"Ошибка в команде стикразбан: {e}")
        bot.reply_to(message, "❌ Произошла ошибка")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    """Обработчик текстовых сообщений (команд без /)"""
    try:
        text = message.text.strip()
        
        # Игнорируем пустые сообщения
        if not text:
            return
        
        # Команда "стикбан" (запретить стикер-пак)
        if check_command(text, ["стикбан", "Стикбан"]):
            handle_stickban_command(message)
        
        # Команда "стикбанлист" (список запрещенных)
        elif check_command(text, ["стикбанлист", "Стикбанлист"]):
            handle_stickbanlist_command(message)
        
        # Команда "стикразбан" (разблокировать пак)
        elif check_command(text, ["стикразбан", "Стикразбан"]):
            # Для этой команды нужен дополнительный текст, поэтому обрабатываем в своей функции
            handle_stickunban_command(message)
        
        # Команда "размут" (снять мут)
        elif check_command(text, ["размут", "Размут"]):
            handle_unmute_command(message)
        
        # Также обрабатываем команды с упоминанием бота
        elif f"@{BOT_USERNAME}" in text:
            text_without_mention = text.replace(f"@{BOT_USERNAME}", "").strip().lower()
            
            if text_without_mention in ["стикбан", "стикбан"]:
                handle_stickban_command(message)
            
            elif text_without_mention in ["стикбанлист", "стикбанлист"]:
                handle_stickbanlist_command(message)
            
            elif any(cmd in text_without_mention for cmd in ["стикразбан", "стикразбан"]):
                handle_stickunban_command(message)
            
            elif text_without_mention in ["размут", "размут"]:
                handle_unmute_command(message)
    
    except Exception as e:
        logger.error(f"Ошибка обработки текста: {e}")

@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    """Обработчик стикеров"""
    try:
        # Игнорируем приватные чаты
        if message.chat.type == 'private':
            return
        
        chat_id_str = str(message.chat.id)
        pack_name = message.sticker.set_name
        
        # Проверяем запрещен ли этот пак
        if chat_id_str in sticker_bot.banned_packs and pack_name in sticker_bot.banned_packs[chat_id_str]:
            # Удаляем стикер (нарушителя)
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить стикер: {e}")
                return
            
            # Даем мут на 1 час
            until_date = datetime.now() + timedelta(hours=1)
            mute_permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            
            try:
                bot.restrict_chat_member(
                    message.chat.id,
                    message.from_user.id,
                    permissions=mute_permissions,
                    until_date=until_date
                )
            except Exception as e:
                logger.error(f"Не удалось замутить пользователя: {e}")
                # Если не удалось замутить, хотя бы предупредим (и не удаляем это предупреждение)
                bot.send_message(
                    message.chat.id,
                    f"⚠️ {message.from_user.first_name}, этот стикер-пак запрещён!",
                    parse_mode='HTML'
                )
                return
            
            # Отправляем уведомление о муте (НЕ УДАЛЯЕМ ЕГО)
            bot.send_message(
                message.chat.id,
                f"🚫 *Нарушение правил!* 🌸\n\n"
                f"👤 *Пользователь:* {message.from_user.first_name}\n"
                f"⏰ *Наказание:* мут на 1 час\n"
                f"📛 *Причина:* отправка запрещенного стикера\n"
                f"🖼 *Пак:* `{pack_name}`\n\n"
                f"_Администратор может снять мут командой размут_",
                parse_mode='Markdown'
            )
            
            logger.info(f"Пользователь {message.from_user.id} получил мут за пак '{pack_name}' в чате {chat_id_str}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки стикера: {e}")

# ========== FLASK МАРШРУТЫ ==========
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "🌸 Помощница Назуна-чан 🌸",
        "message": "✅ Сервис работает"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/set_webhook')
def set_webhook():
    if not WEBHOOK_URL or not bot:
        return jsonify({"error": "Не настроено"}), 400
    
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        return jsonify({
            "status": "success",
            "message": "✅ Webhook установлен!",
            "webhook_url": webhook_url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    if not bot:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    try:
        json_data = request.get_json(force=True)
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 400

# ========== ЗАПУСК СЕРВИСА ==========
if __name__ == '__main__':
    logger.info("🚀 Запуск 🌸 Помощницы Назуна-чан 🌸...")
    
    if bot and WEBHOOK_URL:
        try:
            webhook_url = f"{WEBHOOK_URL}/webhook"
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook установлен: {webhook_url}")
        except Exception as e:
            logger.error(f"Ошибка установки webhook: {e}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
