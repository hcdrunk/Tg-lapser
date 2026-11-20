import os
import re
import io
import base64
import random
from collections import deque
import telebot
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("BOT_TOKEN")
GIGA_KEY = os.environ.get("GIGACHAT_KEY")

print(f"Старт бота... Токен: {bool(TG_TOKEN)}, Ключ GigaChat: {bool(GIGA_KEY)}", flush=True)

bot = telebot.TeleBot(TG_TOKEN)

BOT_CALL_NAME = "вялобот"

ALWAYS_TRIGGERS = [
    "таймлапс", "порьюс", "загорелось", "посияет", "волоярви", "учёба", "учеба"
]

OFTEN_TRIGGERS = [
    "bz", "ветер", "плотность", "скорость", "тучи", "облачность", 
    "дуга", "дыра", "пыхнуло", "не посияет"
]
OFTEN_CHANCE = 0.40
RANDOM_CHANCE = 0.02
MEME_CHANCE = 0.01

DRAW_WORDS = ["нарисуй", "рисуй", "сгенерируй", "изобрази", "картинк"]

SYSTEM_PROMPT = (
    "Ты — обычный живой парень из дружеского питерского телеграм-чата. "
    "В этом чате сидят ребята, которые иногда охотятся за северными сияниями, но в основном просто треплются за жизнь, работу, дорогу, погоду и всякую фигню. "
    "Твой характер: острый на язык, саркастичный, постироничный кореш, который любит вовремя подколоть собеседника по сути его слов.\n\n"
    "ГЛАВНЫЕ ПРАВИЛА (ОБЯЗАТЕЛЬНО):\n"
    "1. Отвечай СТРОГО по контексту разговора. Цепляйся за конкретные слова, несостыковки или нытье в сообщении человека.\n"
    "2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО приплетать северные сияния, таймлапсы, штативы, выдержку, Bz и фототехнику, если люди в последних сообщениях сами об этом не говорили! Не веди себя как робот-фотограф.\n"
    "3. Пиши коротко (1, максимум 2 предложения), как пишут в мессенджерах с телефона: с маленькой буквы, без лишних знаков препинания и без восклицательных знаков.\n"
    "4. Никаких нейросетевых штампов, морализаторства и душных советов.\n"
    "5. Если последнее сообщение в чате — это просто 'ок', 'понял', 'хаха' или там реально не над чем пошутить — ответь ОДНИМ словом: ПРОПУСК"
)

chat_histories = {}
BOT_USERNAME = None
BOT_FIRST_NAME = None
BEST_MODEL = None

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

def init_bot_info():
    global BOT_USERNAME, BOT_FIRST_NAME
    if not BOT_USERNAME:
        me = bot.get_me()
        BOT_USERNAME = me.username.lower()
        BOT_FIRST_NAME = me.first_name or "Вялобот"
        print(f"Авторизован как {BOT_FIRST_NAME} (@{BOT_USERNAME})", flush=True)

def pick_smartest_model(giga):
    global BEST_MODEL
    if BEST_MODEL:
        return BEST_MODEL
    raw_models = giga.get_models().data
    models = []
    for item in raw_models:
        m_id = getattr(item, 'id_', None) or getattr(item, 'id', None) or str(item)
        models.append(m_id)
    for keyword in ["Ultra", "Max", "Pro"]:
        for m in models:
            if keyword.lower() in m.lower() and "preview" not in m.lower():
                BEST_MODEL = m
                return BEST_MODEL
    BEST_MODEL = models[0]
    return BEST_MODEL
def generate_and_send_image(giga, model_name, draw_prompt, chat_id, reply_msg_id):
    print(f"Генерирую картинку: {draw_prompt}", flush=True)
    bot.send_chat_action(chat_id, 'upload_photo')
    payload = Chat(
        model="GigaChat-2",
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content="Ты художник-мемодел. Когда тебя просят нарисовать картинку, вызывай генерацию изображения с ярким, ироничным и точным визуальным описанием."
            ),
            Messages(role=MessagesRole.USER, content=f"Нарисуй: {draw_prompt}")
        ],
        function_call="auto"
    )
    response = giga.chat(payload)
    content = response.choices[0].message.content
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if not match:
        print(f"Картинка не сгенерировалась: {content}", flush=True)
        return False
    file_id = match.group(1)
    image_data = giga.get_image(file_id)
    img_bytes = io.BytesIO(base64.b64decode(image_data.content))
    img_bytes.name = "meme.jpg"
    bot.send_photo(chat_id, img_bytes, reply_to_message_id=reply_msg_id)
    print("Картинка отправлена!", flush=True)
    return True

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not message.text:
        return
    init_bot_info()
    text = message.text.strip()
    text_lower = text.lower()
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "Чатерс"
    print(f"[Чат {chat_id}] {user_name}: {text}", flush=True)

    if chat_id not in chat_histories:
        chat_histories[chat_id] = deque(maxlen=20)
    if not text.startswith('/'):
        chat_histories[chat_id].append(f"{user_name}: {clean_for_sber(text)}")
    if text.startswith('/'):
        return
    if '@' in text_lower and f"@{BOT_USERNAME}" not in text_lower:
        return

    is_reply_to_bot = (
        message.reply_to_message is not None and 
        message.reply_to_message.from_user.username and 
        message.reply_to_message.from_user.username.lower() == BOT_USERNAME
    )
    is_mentioned = (
        f"@{BOT_USERNAME}" in text_lower or 
        BOT_CALL_NAME in text_lower or 
        BOT_FIRST_NAME.lower() in text_lower
    )

    if is_mentioned and any(dw in text_lower for dw in DRAW_WORDS):
        clean_prompt = clean_for_sber(text)
        for word in [BOT_CALL_NAME, f"@{BOT_USERNAME}", "нарисуй", "рисуй", "сгенерируй", "изобрази", "картинку", "картинка"]:
            clean_prompt = re.sub(rf'\b{re.escape(word)}\b', '', clean_prompt, flags=re.IGNORECASE).strip(" ,.!?-:")
        if len(clean_prompt) < 3:
            clean_prompt = "смешной абсурдный мем про северное сияние и фотографов"
        try:
            with GigaChat(credentials=GIGA_KEY, verify_ssl_certs=False, timeout=60.0) as giga:
                model_name = pick_smartest_model(giga)
                if not generate_and_send_image(giga, model_name, clean_prompt, chat_id, message.message_id):
                    bot.reply_to(message, "не, цензура такое рисовать запрещает, придумай что-нибудь попроще")
        except Exception as e:
            print(f"ОШИБКА генерации картинки: {e}", flush=True)
        return

    should_reply = False
    if is_reply_to_bot or is_mentioned or any(word in text_lower for word in ALWAYS_TRIGGERS):
        should_reply = True
    elif any(word in text_lower for word in OFTEN_TRIGGERS):
        if random.random() < OFTEN_CHANCE:
            should_reply = True
    elif len(text) >= 12 and random.random() < RANDOM_CHANCE:
        should_reply = True

    if not should_reply:
        return

    history_text = "\n".join(chat_histories[chat_id])
    safe_last_text = clean_for_sber(text)

    try:
        with GigaChat(credentials=GIGA_KEY, verify_ssl_certs=False, timeout=60.0) as giga:
            model_name = pick_smartest_model(giga)
            if random.random() < MEME_CHANCE:
                print("Выпал 1% шанс на случайный мем!", flush=True)
                idea_payload = Chat(
                    model=model_name,
                    messages=[
                        Messages(role=MessagesRole.SYSTEM, content="Придумай короткое (1 предложение) смешное описание картинки-мема по сути последней фразы в переписке. Без мата и реальных знаменитостей."),
                        Messages(role=MessagesRole.USER, content=f"Переписка:\n{history_text}\n\nПридумай идею картинки-подкола на фразу {user_name}: «{safe_last_text}»")
                    ],
                    temperature=0.75,
                    max_tokens=80
                )
                meme_idea = giga.chat(idea_payload).choices[0].message.content.strip()
                if generate_and_send_image(giga, model_name, meme_idea, chat_id, message.message_id):
                    chat_histories[chat_id].append(f"{BOT_CALL_NAME}: [скинул картинку-мем]")
                    return

            prompt_for_ai = (
                f"Вот переписка в чате (последние сообщения):\n"
                f"{history_text}\n\n"
                f"Вклинься в разговор и остроумно подколи {user_name} в ответ на его последнюю фразу: «{safe_last_text}»"
            )
            print(f"Запрос в {model_name}...", flush=True)
            payload = Chat(
                model=model_name,
                messages=[
                    Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT),
                    Messages(role=MessagesRole.USER, content=prompt_for_ai)
                ],
                temperature=0.72,
                max_tokens=120
            )
            response = giga.chat(payload)
            reply = response.choices[0].message.content.strip()
            print(f"Ответ ({model_name}): {reply}", flush=True)

            censorship_phrases = [
                "генеративные языковые модели",
                "не обладают собственным мнением",
                "чувствительные темы могут быть ограничены",
                "я не могу обсуждать",
                "как искусственный интеллект"
            ]
            if any(phrase in reply.lower() for phrase in censorship_phrases):
                return
            if "ПРОПУСК" in reply.upper() and len(reply) < 15:
                return

            chat_histories[chat_id].append(f"{BOT_CALL_NAME}: {reply}")
            bot.reply_to(message, reply)
    except Exception as e:
        print(f"ОШИБКА GigaChat: {e}", flush=True)

if __name__ == "__main__":
    init_bot_info()
    print("Запускаю прослушку...", flush=True)
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
