from flask import Flask, jsonify
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Sticker Ban Bot",
        "message": "✅ Сервис работает!",
        "port": os.environ.get('PORT', 10000)
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/set_webhook')
def set_webhook():
    return jsonify({
        "status": "ready",
        "message": "Webhook можно будет установить после добавления Telegram функционала"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Запуск на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
