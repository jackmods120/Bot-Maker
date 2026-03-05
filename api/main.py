import os, logging, httpx, asyncio, random, html
from fastapi import FastAPI, Request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from telegram.error import BadRequest

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
MASTER_TOKEN = os.getenv("BOT_TOKEN") 
PROJECT_URL  = os.getenv("PROJECT_URL") 
DB_URL       = os.getenv("DB_URL") 
DB_SECRET    = os.getenv("DB_SECRET")

# زانیارییەکانی خاوەن بۆت (تۆ)
OWNER_ID = 5977475208
CHANNEL_USER = "j4ck_721s"
EMOJIS =["❤️", "🔥", "🎉", "👏", "🤩", "💯"]
PHOTO_URL = "https://zecora0.serv00.net/photo/photo.jpg"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── DATABASE HELPERS ──────────────────────────────────────────────────────────
def fb_url(path): return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def db_put(path, data):
    if not DB_URL: return
    async with httpx.AsyncClient() as client:
        try: await client.put(fb_url(path), json=data)
        except: pass

# ==============================================================================
# ── 1. MASTER BOT (دروستکەری بۆت)
# ==============================================================================
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 بەخێربێیت بۆ بۆت مەیکەری ڕیاکشن!\n\n"
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
        async with Bot(token=token) as bot_user:
            me = await bot_user.get_me()
            
            # گۆڕانکارییە گەورەکە: خستنە ناوەوەی تۆکێن ڕاستەوخۆ لەناو ڕاوتەکە (نەک پرسیار)
            safe_url = PROJECT_URL.rstrip('/')
            webhook_url = f"{safe_url}/api/bot/{token}"
            
            # دانانی وەبەهوک
            await bot_user.set_webhook(url=webhook_url)
            
            # تۆمارکردن لە داتابەیس
            bot_id_str = str(me.id)
            await db_put(f"managed_bots/{bot_id_str}", {"token": token, "owner": update.effective_user.id})

            msg = (
                f"✅ بۆتەکەت چالاک کرا!\n\n"
                f"🤖 ناو: {me.first_name}\n"
                f"🔗 یوزەر: @{me.username}\n\n"
                f"🍓 ئێستا بۆتەکەت ئامادەیە. تاقیی بکەرەوە!"
            )
            await status.edit_text(msg)
    except Exception as e:
        await status.edit_text(f"❌ هەڵە لە چالاککردن: {str(e)}")

master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_master_messages))

# ==============================================================================
# ── 2. CHILD BOT LOGIC (لۆجیکی بۆتە نوێیەکان)
# ==============================================================================
async def process_child_update(token: str, body: dict):
    try:
        # گۆڕانکاری گرنگ: بەکارهێنانی 'async with' بۆ ئەوەی Vercel دای نەخات
        async with Bot(token=token) as bot:
            update = Update.de_json(body, bot)
            
            if not (update.message or update.channel_post):
                return

            msg = update.message if update.message else update.channel_post
            chat_id = msg.chat_id
            message_id = msg.message_id
            text = msg.text or ""
            
            user_name = html.escape(msg.from_user.first_name) if msg.from_user else "Subscriber"
            user_id = msg.from_user.id if msg.from_user else 0
            
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            bot_name = html.escape(bot_info.first_name)

            # ─── فەرمانی /start ───
            if text.startswith('/start'):
                keyboard = [[InlineKeyboardButton("My channel ✌", url=f"https://t.me/{CHANNEL_USER}")],[
                        InlineKeyboardButton("ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᵍʳᵒᵘᵖ ✨", url=f"https://t.me/{bot_username}?startgroup=new"),
                        InlineKeyboardButton("ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᶜʰᵃᶰᶰᵉˡ 🎶", url=f"https://t.me/{bot_username}?startchannel=new")
                    ],[InlineKeyboardButton("ᵖʳᵒᵍʳᵃᵐᵐᵉʳ 🎧", url=f"tg://user?id={OWNER_ID}")]
                ]
                
                caption = (
                    f"Hi dear, <a href='tg://user?id={user_id}'>{user_name}</a>\n\n"
                    f"I'm a reaction bot 🍓, my name is <b>{bot_name}</b>\n"
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
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        reply_to_message_id=message_id
                    )
                except Exception as e:
                    # ئەگەر وێنەکە نەنێردرا، بە تێکست وەڵام دەداتەوە
                    await bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        reply_to_message_id=message_id
                    )
            
            # ─── ڕیاکشن بۆ نامەکانی تر ───
            else:
                try:
                    random_emoji = random.choice(EMOJIS)
                    await bot.set_message_reaction(
                        chat_id=chat_id,
                        message_id=message_id,
                        reaction=[ReactionTypeEmoji(emoji=random_emoji)]
                    )
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Child Error: {e}")
        # ئەگەر بۆتە نوێیەکە ئیرۆرێکی هەبێت، ڕاستەوخۆ بە بۆتە سەرەکییەکە نامە بۆ تۆ دەنێرێت!
        try:
            async with Bot(token=MASTER_TOKEN) as mbot:
                await mbot.send_message(
                    chat_id=OWNER_ID, 
                    text=f"⚠️ <b>هەڵەیەک ڕوویدا لە بۆتێکی دروستکراودا:</b>\n\n<code>{str(e)}</code>",
                    parse_mode=ParseMode.HTML
                )
        except:
            pass

# ==============================================================================
# ── 3. ROUTES (ڕاوتەرەکان)
# ==============================================================================
@app.post("/api/main")
async def master_route(request: Request):
    """وەبەهووکی بۆتە سەرەکییەکە"""
    if not master_app.running: await master_app.initialize()
    data = await request.json()
    await master_app.process_update(Update.de_json(data, master_app.bot))
    return {"ok": True}

# ڕاوتەری نوێ (زۆر پارێزراوتر)
@app.post("/api/bot/{token}")
async def child_route(request: Request, token: str):
    """وەبەهووکی بۆتە دروستکراوەکان"""
    data = await request.json()
    await process_child_update(token, data)
    return {"ok": True}

@app.get("/api/main")
async def health(): 
    return {"status": "Reaction Bot Maker is Active and Running! 🚀"}
