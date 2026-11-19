import os
import re
import random
from collections import deque
import telebot
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Подхватываем ключи из настроек Bothost
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("BOT_TOKEN")
GIGA_KEY = os.environ.get("GIGACHAT_KEY")

print(f"Старт бота... Токен найден: {bool(TG_TOKEN)}, Ключ GigaChat найден: {bool(GIGA_KEY)}", flush=True)

bot = telebot.TeleBot(TG_TOKEN)

# --- НАСТРОЙКИ ВЕРОЯТНОСТЕЙ И ТРИГГЕРОВ ---

# 1. Слова, на которые бот реагирует ВСЕГДА (шанс 100%)
ALWAYS_TRIGGERS = [
    "таймлапс", "порьюс", "загорелось", "посияет", "волоярви", "учёба", "учеба"
]

# 2. Слова, на которые бот реагирует ЧАСТО
OFTEN_TRIGGERS = [
    "bz", "ветер", "плотность", "скорость", "тучи", "облачность", 
    "дуга", "дыра", "пыхнуло", "не посияет"
]
OFTEN_CHANCE = 0.40  # 40% вероятность ответа

# 3. Вероятность случайного врыва в обычный разговор без триггеров
RANDOM_CHANCE = 0.05  # 5% (примерно каждое 20-е сообщение)

# --- ХАРАКТЕР БОТА (СИСТЕМНЫЙ ПРОМПТ) ---
# (Формулируем без мата в инструкции, чтобы не триггерить цензуру Сбера)
SYSTEM_PROMPT = (
    "Ты — Безумный Таймлапсер, бывалый участник телеграм-чата охотников за северными сияниями (Ленобласть, Карелия, Волоярви, Порьюс). "
    "Ты обожаешь снимать северные сияния, делать таймлапсы, шаришь за солнечный ветер, Bz и засвеченные фонари. "
    "Твой стиль: постироничный, саркастичный, слегка циничный, но свой в доску кореш. Ты любишь мягко подкалывать и троллить участников чата за их нытье, "
    "ожидание чуда при плюсовом Bz, поездки в глухие тучи или глупые вопросы. Можешь слегка коверкать слова, использовать сленг охотников и постиронию. "
    "Не душни, не читай лекции и не пиши длинные простыни — отвечай коротко (1-2 емких предложения), как в живом чате. "
    "Отвечай с юмором и перчинкой, чтобы было смешно. "
    "ВАЖНО: Тебе передают последние сообщения из чата для контекста. Тебе нужно ответить именно на ПОСЛЕДНЕЕ сообщение от указанного юзера. "
    "Если последнее сообщение слишком короткое, бессмысленное или там вообще не за что зацепиться для шутки — ответь ОДНИМ словом: ПРОПУСК"
)
# ----------------------------------------

chat_histories = {}
BOT_USERNAME = None

# Смягчаем мат перед отправкой в Сбер, чтобы не срабатывала цензура
def clean_for_sber(text):
    bad_patterns = [
        r'\b[хx][уy][йяеёию]\w*',
        r'\b[пp][иi][зz][дd]\w*',
        r'\b[еeё][бb]\w*',
        r'\b[бb][лl][яa]\w*',
        r'\b[сc][уy][кk]\w*',
        r'\b[мm][уy][дd][аa]\w*',
        r'\b[гg][оo][вv][нn]\w*',
        r'\b[жj][оo][пp]\w*'
    ]
    cleaned = text
    for pat in bad_patterns:
        cleaned = re.sub(pat, '[эмоции]', cleaned, flags=re.IGNORECASE)
    return cleaned

def get_bot_username():
    global BOT_USERNAME
    if not BOT_USERNAME:
        me = bot.get_me()
        BOT_USERNAME = me.username.lower()
        print(f"Бот успешно авторизован в Telegram как @{BOT_USERNAME}", flush=True)
    return BOT_USERNAME

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not message.text:
        return

    text = message.text.strip()
    text_lower = text.lower()
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "Чатерс"

    print(f"[Чат {chat_id}] {user_name}: {text}", flush=True)

    if chat_id not in chat_histories:
        chat_histories[chat_id] = deque(maxlen=12)

    if not text.startswith('/'):
        # В историю сохраняем уже смягченный текст, чтобы старый мат не ломал будущие запросы
        chat_histories[chat_id].append(f"{user_name}: {clean_for_sber(text)}")

    bot_user = get_bot_username()
    if text.startswith('/'):
        return
    if '@' in text_lower and f"@{bot_user}" not in text_lower:
        return

    is_reply_to_bot = (
        message.reply_to_message is not None and 
        message.reply_to_message.from_user.username and 
        message.reply_to_message.from_user.username.lower() == bot_user
    )
    is_mentioned = f"@{bot_user}" in text_lower or "таймлапсер" in text_lower

    should_reply = False

    if is_reply_to_bot or is_mentioned or any(word in text_lower for word in ALWAYS_TRIGGERS):
        should_reply = True
    elif any(word in text_lower for word in OFTEN_TRIGGERS):
        if random.random() < OFTEN_CHANCE:
            should_reply = True
    else:
        if len(text) >= 12 and random.random() < RANDOM_CHANCE:
            should_reply = True

    if not should_reply:
        return

    print("Триггер сработал! Отправляю запрос в GigaChat...", flush=True)

    history_text = "\n".join(chat_histories[chat_id])
    safe_last_text = clean_for_sber(text)

    prompt_for_ai = (
        f"Вот последние сообщения в чате для понимания контекста:\n"
        f"{history_text}\n\n"
        f"Напиши саркастичный ответ от лица Безумного Таймлапсера на ПОСЛЕДНЕЕ сообщение от {user_name}: «{safe_last_text}»"
    )

    try:
        with GigaChat(credentials=GIGA_KEY, verify_ssl_certs=False) as giga:
            models_list = giga.get_models()
            available_model = models_list.data.id_

            payload = Chat(
                model=available_model,
                messages=[
                    Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT),
                    Messages(role=MessagesRole.USER, content=prompt_for_ai)
                ],
                temperature=0.85,
                max_tokens=160
            )
            response = giga.chat(payload)
            reply = response.choices.message.content.strip()
            print(f"Ответ GigaChat: {reply}", flush=True)

            # Блокируем душные системные отписки Сбера, если цензура всё-таки сработала
            censorship_phrases = [
                "генеративные языковые модели",
                "не обладают собственным мнением",
                "чувствительные темы могут быть ограничены",
                "я не могу обсуждать",
                "как искусственный интеллект"
            ]
            if any(phrase in reply.lower() for phrase in censorship_phrases):
                print("Сработала цензура Сбера — сообщение отброшено.", flush=True)
                return

            if "ПРОПУСК" in reply.upper() and len(reply) < 15:
                return

            chat_histories[chat_id].append(f"Безумный Таймлапсер: {reply}")
            bot.reply_to(message, reply)

    except Exception as e:
        print(f"ОШИБКА GigaChat: {e}", flush=True)

if __name__ == "__main__":
    get_bot_username()
    print("Запускаю прослушку сообщений...", flush=True)
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
