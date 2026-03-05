import os, logging, httpx, asyncio, json, random
from fastapi import FastAPI, Request, BackgroundTasks
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
MASTER_TOKEN = os.getenv("BOT_TOKEN") 
PROJECT_URL  = os.getenv("PROJECT_URL") 
DB_URL       = os.getenv("DB_URL") 
DB_SECRET    = os.getenv("DB_SECRET")

# زانیارییەکانی بۆتەکەی تۆ
DEV_ID = 5977475208
CHANNEL_USER = "j4ck_721s"
EMOJIS = ["❤️", "🔥", "🎉", "👏", "🤩", "💯"]
PHOTO_URL = "https://zecora0.serv00.net/photo/photo.jpg"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── DATABASE HELPERS ──────────────────────────────────────────────────────────
def fb_url(path): return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def db_put(path, data):
    async with httpx.AsyncClient() as client:
        try: await client.put(fb_url(path), json=data)
        except: pass

# ==============================================================================
# ── 1. MASTER BOT (دروستکەری بۆت)
# ==============================================================================
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **بەخێربێیت بۆ بۆت مەیکەری ڕیاکشن!**\n\n"
        "تەنها تۆکێنی بۆتەکەت بنێرە، من دەیکەم بە بۆتێکی ڕیاکشن (Reaction Bot).\n"
        "بۆتەکە وەڵامی /start دەداتەوە و ڕیاکشن بۆ هەموو نامەیەک دەکات."
    )

async def handle_master_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    if ":" not in token or len(token) < 20:
        await update.message.reply_text("❌ تۆکێنەکە نادروستە!"); return

    status = await update.message.reply_text("⏳ خەریکی چالاککردنم...")
    try:
        # پشکنینی تۆکێن
        bot_user = Bot(token=token)
        me = await bot_user.get_me()
        
        # بەستنەوەی وەبهووک
        webhook_url = f"{PROJECT_URL}/api/child_bot?token={token}"
        await bot_user.set_webhook(url=webhook_url)
        
        # تۆمارکردن لە داتابەیس
        bot_id_str = str(me.id)
        await db_put(f"managed_bots/{bot_id_str}", {"token": token, "owner": update.effective_user.id})

        await status.edit_text(
            f"✅ **بۆتەکەت چالاک کرا!**\n\n"
            f"🤖 ناو: {me.first_name}\n"
            f"🔗 یوزەر: @{me.username}\n\n"
            f"🍓 **ئێستا بۆتەکەت چی دەکات؟**\n"
            f"١. وەڵامی `/start` دەداتەوە بە وێنە و دوگمە.\n"
            f"٢. ڕیاکشن (Reaction) بۆ هەموو نامەیەک دەکات."
        )
    except Exception as e:
        await status.edit_text(f"❌ هەڵە: {str(e)}")

master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_master_messages))

# ==============================================================================
# ── 2. CHILD BOT LOGIC (لۆجیکی بۆتە دروستکراوەکان)
# ==============================================================================
async def process_child_update(token: str, body: dict):
    try:
        bot = Bot(token=token)
        update = Update.de_json(body, bot)
        
        # ئەگەر نامە نەبێت یان پۆستی چەناڵ نەبێت، هیچی پێ ناکرێت
        if not (update.message or update.channel_post):
            return

        # دیاریکردنی جۆری پەیام (چات یان چەناڵ)
        msg = update.message if update.message else update.channel_post
        chat_id = msg.chat_id
        message_id = msg.message_id
        text = msg.text or ""
        
        # زانیاری بەکارهێنەر (ئەگەر لە چەناڵ نەبوو)
        user_name = msg.from_user.first_name if msg.from_user else "Subscriber"
        user_id = msg.from_user.id if msg.from_user else 0
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        bot_name = bot_info.first_name

        # --- ئەگەر فەرمانی /start بوو ---
        if text == '/start':
            # دروستکردنی دوگمەکان
            keyboard = [
                [InlineKeyboardButton("My channel ✌", url=f"https://t.me/{CHANNEL_USER}")],
                [
                    InlineKeyboardButton("ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᵍʳᵒᵘᵖ ✨", url=f"https://t.me/{bot_username}?startgroup=new"),
                    InlineKeyboardButton("ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᶜʰᵃᶰᶰᵉˡ 🎶", url=f"https://t.me/{bot_username}?startchannel=new")
                ],
                [InlineKeyboardButton('ᵖʳᵒᵍʳᵃᵐᵐᵉʳ 🎧 ', url=f"tg://user?id={DEV_ID}")]
            ]
            
            # نووسینی کەپشنەکە
            caption = (
                f"Hi dear, [{user_name}](tg://user?id={user_id})\n\n"
                f"I'm a reaction bot 🍓, my name is {bot_name}\n"
                f"My job is to interact with messages using {' '.join(EMOJIS)}\n"
                f"I can interact in groups, channels and private chats 🌼\n"
                f"Just add me to your group or channel and make me an admin with simple permissions ☘️\n"
                f"And I will interact with every message you send. Try me now 💗"
            )

            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=PHOTO_URL,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    reply_to_message_id=message_id
                )
            except Exception as e:
                logger.error(f"Error sending start message: {e}")
        
        # --- بۆ هەموو نامەکانی تر: ڕیاکشن ---
        else:
            try:
                random_emoji = random.choice(EMOJIS)
                await bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[ReactionTypeEmoji(random_emoji)]
                )
            except BadRequest:
                # ئەگەر ڕیاکشن قەدەغە بێت یان بۆتەکە ئەدمین نەبێت
                pass
            except Exception as e:
                logger.error(f"Error reacting: {e}")

    except Exception as e:
        logger.error(f"General Child Bot Error: {e}")

# ==============================================================================
# ── 3. ROUTES
# ==============================================================================
@app.post("/api/main")
async def master_route(request: Request):
    if not master_app.running: await master_app.initialize()
    data = await request.json()
    await master_app.process_update(Update.de_json(data, master_app.bot))
    return {"ok": True}

@app.post("/api/child_bot")
async def child_route(request: Request, token: str, background_tasks: BackgroundTasks):
    data = await request.json()
    background_tasks.add_task(process_child_update, token, data)
    return {"ok": True}

@app.get("/api/main")
async def health(): return {"status": "Reaction Bot Maker Running"}
