import os
import re
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from openai import OpenAI
import httpx
import nest_asyncio

load_dotenv()

# Инициализация клиентов
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
user_data = {}

# Голосовое приветствие на иврите
HEBREW_GREETING = "שלום! אני הבוט שלך ללימוד עברית. שלח לי הודעת קול ואני אעזור לך."

# URL для WebApp (будет заменен на Cloudflare Tunnel URL)
WEBAPP_URL = "https://your-tunnel-url.cfargotunnel.com/webapp"
print(f"Mini App доступен по адресу: {WEBAPP_URL}")

async def send_voice_greeting(chat_id, context):
    """Отправка голосового приветствия"""
    audio_data = await generate_voice(HEBREW_GREETING)
    voice_path = "greeting.mp3"
    with open(voice_path, "wb") as f:
        f.write(audio_data)

    await context.bot.send_voice(
        chat_id=chat_id,
        voice=open(voice_path, "rb"),
        caption="👋 Приветствие на иврите",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❓ Помощь", callback_data="help"),
             InlineKeyboardButton("📖 Разбор слов", web_app=WebAppInfo(url=WEBAPP_URL))]
        ])
    )
    os.remove(voice_path)

async def generate_voice(text: str):
    """Генерация голосового сообщения через ElevenLabs"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            json={"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
            timeout=30
        )
        return response.content

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Добро пожаловать в бота для изучения иврита!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❓ Помощь", callback_data="help"),
             InlineKeyboardButton("📖 Разбор слов", web_app=WebAppInfo(url=WEBAPP_URL))]
        ])
    )
    await send_voice_greeting(update.message.chat_id, context)

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Помощь'"""
    query = update.callback_query
    await query.answer()

    help_text = (
        "🤖 <b>Как пользоваться ботом:</b>\n\n"
        "1. Отправьте голосовое сообщение на иврите\n"
        "2. Бот ответит вам голосовым сообщением\n"
        "3. Используйте кнопки под сообщением:\n"
        "   - <b>❓ Помощь</b> - это сообщение\n"
        "   - <b>📖 Разбор слов</b> - интерактивный словарь\n\n"
        "В словаре можно кликнуть на любое слово для получения перевода и объяснения."
    )

    await query.edit_message_text(
        text=help_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ])
    )

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных из WebApp"""
    data = json.loads(update.effective_message.web_app_data.data)
    word = data.get('word')
    
    if word:
        analysis = await analyze_word(word)
        await update.message.reply_text(
            text=f"🔍 <b>Разбор слова:</b> {word}\n\n"
                 f"📖 <b>Транскрипция:</b> {analysis.get('transcription', 'N/A')}\n"
                 f"🌍 <b>Перевод:</b> {analysis.get('translation', 'N/A')}\n"
                 f"📚 <b>Объяснение:</b> {analysis.get('explanation', 'N/A')}",
            parse_mode="HTML"
        )

async def analyze_word(word: str):
    """Анализ слова через ChatGPT"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"Дай транскрипцию, перевод и объяснение для ивритского слова: {word}\n"
                           "Формат: JSON: {'transcription': '...', 'translation': '...', 'explanation': '...'}"
            }],
            temperature=0.3
        )
        return eval(response.choices[0].message.content)
    except Exception as e:
        print(f"Ошибка анализа слова: {e}")
        return {"transcription": "N/A", "translation": "N/A", "explanation": "N/A"}

async def back_to_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Главное меню:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❓ Помощь", callback_data="help"),
             InlineKeyboardButton("📖 Разбор слов", web_app=WebAppInfo(url=WEBAPP_URL))]
        ])
    )

def main():
    # Настройка asyncio (может потребоваться для некоторых сред)
    nest_asyncio.apply()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    # Обработчики callback-кнопок
    app.add_handler(CallbackQueryHandler(help_callback, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_to_main_callback, pattern="^back_to_main$"))

    print("Бот запущен с голосовым приветствием и Mini App для разбора слов")
    print(f"Mini App доступен по адресу: {WEBAPP_URL}")
    app.run_polling()

if __name__ == "__main__":
    main()