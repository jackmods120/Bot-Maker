import os, logging, httpx, asyncio, random, html, re
from fastapi import FastAPI, Request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
MASTER_TOKEN = os.getenv("BOT_TOKEN") 
PROJECT_URL  = os.getenv("PROJECT_URL") 
DB_URL       = os.getenv("DB_URL") 
DB_SECRET    = os.getenv("DB_SECRET")

OWNER_ID = 5977475208
CHANNEL_USER = "j4ck_721s"
EMOJIS =["❤️", "🔥", "🎉", "👏", "🤩", "💯"]
PHOTO_URL = "https://zecora0.serv00.net/photo/photo.jpg"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── DATABASE HELPERS (FIREBASE) ───────────────────────────────────────────────
def fb_url(path): return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def db_get(path):
    if not DB_URL: return None
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(fb_url(path))
            return r.json() if r.status_code == 200 else None
        except: return None

async def db_put(path, data):
    if not DB_URL: return
    async with httpx.AsyncClient() as client:
        try: await client.put(fb_url(path), json=data)
        except: pass

async def db_del(path):
    if not DB_URL: return
    async with httpx.AsyncClient() as client:
        try: await client.delete(fb_url(path))
        except: pass

# ==============================================================================
# ── 1. MASTER BOT (پانێڵی دروستکردن و کۆنترۆڵ)
# ==============================================================================
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 <b>بەخێربێیت بۆ پانێڵی دروستکردنی بۆت!</b>\n\n"
        "لێرە دەتوانیت بۆتی تایبەت بە خۆت دروست بکەیت و کۆنترۆڵیان بکەیت.\n"
        "تکایە لە دوگمەکانی خوارەوە هەڵبژێرە:"
    )
    kb = [[InlineKeyboardButton("➕ دروستکردنی بۆتی نوێ", callback_data="create_bot")],[InlineKeyboardButton("📂 بۆتەکانم (کۆنترۆڵ)", callback_data="my_bots")]
    ]
    if update.message:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    user_id = q.from_user.id
    try: await q.answer()
    except: pass

    # --- گەڕانەوە بۆ سەرەتا ---
    if data == "main_menu":
        await master_start(update, ctx)
        return

    # --- مینیوی دروستکردن ---
    if data == "create_bot":
        msg = "🤖 <b>جۆری ئەو بۆتە هەڵبژێرە کە دەتەوێت دروستی بکەیت:</b>"
        kb = [[InlineKeyboardButton("🍓 بۆتی ڕیاکشن (Reaction Bot)", callback_data="type_reaction")],[InlineKeyboardButton("🔜 جۆری تر (بەمزوانە)", callback_data="coming_soon")],[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="main_menu")]
        ]
        await q.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    # --- دوای هەڵبژاردنی بۆتی ڕیاکشن ---
    if data == "type_reaction":
        msg = (
            "🍓 <b>دروستکردنی بۆتی ڕیاکشن</b>\n\n"
            "ئەم بۆتە وەڵامی /start دەداتەوە و ڕیاکشن بۆ هەموو نامەیەک دەکات.\n\n"
            "👇 <b>تکایە تەنها تۆکێنی بۆتەکەت (Bot Token) لێرە بنێرە:</b>"
        )
        kb = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="create_bot")]]
        await q.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "coming_soon":
        await q.answer("⏳ لە داهاتوودا بەردەست دەبێت!", show_alert=True)
        return

    # --- لیستی بۆتەکانم ---
    if data == "my_bots":
        all_bots = await db_get("managed_bots") or {}
        # هێنانی تەنیا ئەو بۆتانەی کە خاوەنەکەی ئەم کەسەیە
        user_bots = {bot_id: info for bot_id, info in all_bots.items() if info.get("owner") == user_id}

        if not user_bots:
            msg = "📭 <b>هیچ بۆتێکت دروست نەکردووە!</b>"
            kb = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="main_menu")]]
            await q.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        msg = "📂 <b>بۆتەکانت:</b>\n\nتکایە کلیک لەو بۆتە بکە کە دەتەوێت کۆنترۆڵی بکەیت:"
        kb =[]
        for bot_id, info in user_bots.items():
            username = info.get("bot_username", "UnknownBot")
            status_icon = "🟢" if info.get("status") == "running" else "🔴"
            kb.append([InlineKeyboardButton(f"{status_icon} @{username}", callback_data=f"manage_{bot_id}")])
        
        kb.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="main_menu")])
        await q.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    # --- پانێڵی کۆنترۆڵی بۆتێکی دیاریکراو ---
    if data.startswith("manage_"):
        bot_id = data.split("_")[1]
        bot_data = await db_get(f"managed_bots/{bot_id}")
        
        if not bot_data:
            await q.answer("❌ ئەم بۆتە نەدۆزرایەوە!", show_alert=True)
            return

        status = bot_data.get("status", "running")
        status_text = "🟢 کاردەکات (Running)" if status == "running" else "🔴 ڕاگیراوە (Stopped)"
        btn_toggle = "⏸ ڕاگرتن" if status == "running" else "▶️ کارپێکردنەوە"

        msg = (
            f"⚙️ <b>پانێڵی کۆنترۆڵ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>یوزەر:</b> @{bot_data.get('bot_username')}\n"
            f"📊 <b>دۆخ:</b> {status_text}\n"
            f"🔌 <b>جۆر:</b> ڕیاکشن بۆت\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"چیت دەوێت لەگەڵ ئەم بۆتە بکەیت؟"
        )
        kb = [[InlineKeyboardButton(btn_toggle, callback_data=f"toggle_{bot_id}")],[InlineKeyboardButton("🗑 سڕینەوەی بۆت", callback_data=f"delete_{bot_id}")],[InlineKeyboardButton("🔙 گەڕانەوە بۆ لیست", callback_data="my_bots")]
        ]
        await q.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    # --- ڕاگرتن / کارپێکردنەوە ---
    if data.startswith("toggle_"):
        bot_id = data.split("_")[1]
        bot_data = await db_get(f"managed_bots/{bot_id}")
        if bot_data:
            new_status = "stopped" if bot_data.get("status", "running") == "running" else "running"
            bot_data["status"] = new_status
            await db_put(f"managed_bots/{bot_id}", bot_data)
            
            # گەڕانەوە بۆ لاپەڕەی کۆنترۆڵ بۆ بینینی گۆڕانکارییەکە
            q.data = f"manage_{bot_id}"
            await handle_callback(update, ctx)
        return

    # --- سڕینەوەی بۆت ---
    if data.startswith("delete_"):
        bot_id = data.split("_")[1]
        await db_del(f"managed_bots/{bot_id}")
        await q.answer("🗑 بۆتەکە بە تەواوی سڕایەوە!", show_alert=True)
        # گەڕانەوە بۆ لیستی بۆتەکان
        q.data = "my_bots"
        await handle_callback(update, ctx)
        return

# --- وەرگرتنی تۆکێن لەلایەن بەکارهێنەرەوە ---
async def handle_master_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # بەکارهێنانی ڕێگێکس بۆ دۆزینەوەی تۆکێن لەناو نامەکە (زۆر پارێزراوە لە Vercel)
    if not re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", text):
        # ئەگەر تۆکێن نەبوو، تەنها نامەیەک دەنێرێت کە بچێتە مینیو
        await update.message.reply_text("تکایە فەرمانی /start بەکاربهێنە بۆ بینینی مینیو، یان تەنها تۆکێن بنێرە.")
        return

    token = text
    status_msg = await update.message.reply_text("⏳ خەریکی چالاککردنی بۆتەکەم...")
    
    try:
        # پشکنینی تۆکێن
        async with Bot(token=token) as bot_user:
            me = await bot_user.get_me()
            bot_id_str = str(me.id)
            
            # پاککردنەوەی لینکەکە و دانانی وەبەهوک
            safe_url = PROJECT_URL.rstrip('/')
            webhook_url = f"{safe_url}/api/bot/{token}"
            await bot_user.set_webhook(url=webhook_url)
            
            # پاشەکەوتکردن لە داتابەیس (status: running) بەشێوەی بنچینە
            await db_put(f"managed_bots/{bot_id_str}", {
                "token": token,
                "owner": user_id,
                "bot_username": me.username,
                "type": "reaction",
                "status": "running"
            })

            msg = (
                f"✅ <b>بۆتەکەت سەرکەوتووانە دروست کرا!</b>\n\n"
                f"🤖 یوزەر: @{me.username}\n\n"
                f"ئێستا دەتوانیت لە ڕێگەی دوگمەی <b>'📂 بۆتەکانم'</b> لە فەرمانی /start کۆنترۆڵی بکەیت."
            )
            kb = [[InlineKeyboardButton("📂 بڕۆ بۆ پانێڵی بۆتەکەم", callback_data=f"manage_{bot_id_str}")]]
            await status_msg.edit_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    
    except Exception as e:
        await status_msg.edit_text(f"❌ هەڵە لە تۆکێنەکە یان چالاککردن: {str(e)}")

master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(CallbackQueryHandler(handle_callback))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_master_messages))

# ==============================================================================
# ── 2. CHILD BOT LOGIC (بۆتە دروستکراوەکان)
# ==============================================================================
async def process_child_update(token: str, body: dict):
    try:
        bot_id_str = token.split(":")[0]
        
        # ١. پشکنین بزانین ئایا بۆتەکە 'running'ە یان 'stopped'
        bot_data = await db_get(f"managed_bots/{bot_id_str}")
        if not bot_data: return # بۆتەکە سڕاوەتەوە
        if bot_data.get("status") != "running": return # بۆتەکە ڕاگیراوە لەلایەن خاوەنەکەیەوە!

        async with Bot(token=token) as bot:
            update = Update.de_json(body, bot)
            if not (update.message or update.channel_post): return

            msg = update.message if update.message else update.channel_post
            chat_id = msg.chat_id
            message_id = msg.message_id
            text = msg.text or ""
            
            user_name = html.escape(msg.from_user.first_name) if msg.from_user else "Subscriber"
            user_id = msg.from_user.id if msg.from_user else 0
            
            bot_info = await bot.get_me()
            bot_username = bot_info.username

            # ─── فەرمانی /start ───
            if text.startswith('/start'):
                keyboard = [[InlineKeyboardButton("My channel ✌", url=f"https://t.me/{CHANNEL_USER}")],[
                        InlineKeyboardButton("ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᵍʳᵒᵘᵖ ✨", url=f"https://t.me/{bot_username}?startgroup=new"),
                        InlineKeyboardButton("ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᶜʰᵃᶰᶰᵉˡ 🎶", url=f"https://t.me/{bot_username}?startchannel=new")
                    ],[InlineKeyboardButton("ᵖʳᵒᵍʳᵃᵐᵐᵉʳ 🎧", url=f"tg://user?id={OWNER_ID}")]
                ]
                
                caption = (
                    f"Hi dear, <a href='tg://user?id={user_id}'>{user_name}</a>\n\n"
                    f"I'm a reaction bot 🍓, my name is <b>{bot_info.first_name}</b>\n"
                    f"My job is to interact with messages using {' '.join(EMOJIS)}\n"
                    f"I can interact in groups, channels and private chats 🌼\n"
                    f"Just add me to your group or channel and make me an admin with simple permissions ☘️\n"
                    f"And I will interact with every message you send. Try me now 💗"
                )

                try:
                    await bot.send_photo(chat_id=chat_id, photo=PHOTO_URL, caption=caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard), reply_to_message_id=message_id)
                except Exception:
                    await bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard), reply_to_message_id=message_id)
            
            # ─── ڕیاکشن بۆ نامەکانی تر ───
            else:
                try:
                    random_emoji = random.choice(EMOJIS)
                    await bot.set_message_reaction(chat_id=chat_id, message_id=message_id, reaction=[ReactionTypeEmoji(emoji=random_emoji)])
                except Exception: pass

    except Exception as e:
        logger.error(f"Child Error: {e}")

# ==============================================================================
# ── 3. ROUTES (ڕاوتەرەکان)
# ==============================================================================
@app.post("/api/main")
async def master_route(request: Request):
    if not master_app.running: await master_app.initialize()
    data = await request.json()
    await master_app.process_update(Update.de_json(data, master_app.bot))
    return {"ok": True}

@app.post("/api/bot/{token}")
async def child_route(request: Request, token: str):
    data = await request.json()
    await process_child_update(token, data)
    return {"ok": True}

@app.get("/api/main")
async def health(): 
    return {"status": "Bot Maker Panel is Active! 🚀"}
