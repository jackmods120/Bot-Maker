import os, logging, httpx, asyncio, random, html, re
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

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

# ── KEYBOARDS (کیبۆردەکانی خوارەوەی شاشە) ────────────────────────────────────
MAIN_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("➕ دروستکردنی بۆتی نوێ"), KeyboardButton("📂 بۆتەکانم")]], 
    resize_keyboard=True
)

CONTROL_PANEL = ReplyKeyboardMarkup([[KeyboardButton("▶️ دەستپێکردن"), KeyboardButton("⏸ وەستاندن")],[KeyboardButton("🔄 نوێکردنەوە"), KeyboardButton("🗑 سڕینەوە")],
    [KeyboardButton("🔙 گەڕانەوە بۆ لیست")]
], resize_keyboard=True)

# ── DATABASE HELPERS ──────────────────────────────────────────────────────────
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
# ── 1. MASTER BOT (بۆتە سەرەکییەکە)
# ==============================================================================
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # کاتێک دەستپێدەکات، هەموو دۆخێکی پێشوو دەسڕینەوە بۆ دڵنیایی
    await db_del(f"users/{update.effective_user.id}/state")
    
    msg = (
        "👋 <b>بەخێربێیت بۆ پانێڵی دروستکردنی بۆت!</b>\n\n"
        "لێرە دەتوانیت بۆتی تایبەت بە خۆت دروست بکەیت و کۆنترۆڵیان بکەیت.\n"
        "تکایە لە کیبۆردی خوارەوە هەڵبژێرە:"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=MAIN_MENU)

async def handle_text_commands(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # 1. گەڕانەوە بۆ سەرەتا
    if text == "🔙 گەڕانەوە بۆ سەرەتا":
        await db_del(f"users/{user_id}/state")
        await master_start(update, ctx)
        return

    # 2. مینیوی جۆری بۆتەکان (کێشەی یەکەم چارەسەر کرا)
    if text == "➕ دروستکردنی بۆتی نوێ":
        kb = ReplyKeyboardMarkup([[KeyboardButton("🍓 بۆتی ڕیاکشن")],[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text("🤖 <b>جۆری ئەو بۆتە هەڵبژێرە کە دەتەوێت دروستی بکەیت:</b>", parse_mode="HTML", reply_markup=kb)
        return

    # 3. هەڵبژاردنی بۆتی ڕیاکشن و داواکردنی تۆکێن
    if text == "🍓 بۆتی ڕیاکشن":
        await db_put(f"users/{user_id}/state", "waiting_reaction_token")
        kb = ReplyKeyboardMarkup([[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text("🍓 <b>دروستکردنی بۆتی ڕیاکشن</b>\n\nتکایە تەنها تۆکێنی بۆتەکەت (Bot Token) لێرە بنێرە:", parse_mode="HTML", reply_markup=kb)
        return

    # 4. لیستی بۆتەکانم
    if text == "📂 بۆتەکانم" or text == "🔙 گەڕانەوە بۆ لیست":
        all_bots = await db_get("managed_bots") or {}
        user_bots = {k: v for k, v in all_bots.items() if v.get("owner") == user_id}

        if not user_bots:
            await update.message.reply_text("📭 هیچ بۆتێکت دروست نەکردووە!", reply_markup=MAIN_MENU)
            return

        bot_buttons =[]
        for b_id, info in user_bots.items():
            username = info.get("bot_username", "Bot")
            bot_buttons.append([KeyboardButton(f"🤖 @{username}")])
        
        bot_buttons.append([KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")])
        bot_list_kb = ReplyKeyboardMarkup(bot_buttons, resize_keyboard=True)
        
        await update.message.reply_text("📂 <b>بۆتەکانت:</b>\nکام بۆتە دەتەوێت کۆنترۆڵ بکەیت؟", parse_mode="HTML", reply_markup=bot_list_kb)
        return

    # 5. چوونە ناو کۆنترۆڵ پانێڵی بۆتێک
    if text.startswith("🤖 @"):
        selected_username = text.replace("🤖 @", "").strip()
        all_bots = await db_get("managed_bots") or {}
        
        bot_id = None
        for k, v in all_bots.items():
            if v.get("owner") == user_id and v.get("bot_username") == selected_username:
                bot_id = k
                break
        
        if bot_id:
            await db_put(f"users/{user_id}/selected_bot", bot_id)
            status = all_bots[bot_id].get("status", "running")
            status_text = "🟢 کاردەکات (Running)" if status == "running" else "🔴 ڕاگیراوە (Stopped)"
            
            msg = (
                f"⚙️ <b>پانێڵی کۆنترۆڵ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 یوزەر: @{selected_username}\n"
                f"📊 دۆخ: {status_text}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"لە کیبۆردی خوارەوە کۆنترۆڵی بکە:"
            )
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=CONTROL_PANEL)
        else:
            await update.message.reply_text("❌ ئەم بۆتە نەدۆزرایەوە!")
        return

    # 6. دوگمەکانی کۆنترۆڵکردن
    if text in["▶️ دەستپێکردن", "⏸ وەستاندن", "🔄 نوێکردنەوە", "🗑 سڕینەوە"]:
        selected_bot_id = await db_get(f"users/{user_id}/selected_bot")
        if not selected_bot_id:
            await update.message.reply_text("⚠️ تکایە سەرەتا بۆتێک هەڵبژێرە.")
            return

        bot_data = await db_get(f"managed_bots/{selected_bot_id}")
        if not bot_data:
            await update.message.reply_text("❌ بۆتەکە سڕاوەتەوە.")
            return

        username = bot_data.get("bot_username", "Bot")

        if text == "▶️ دەستپێکردن":
            bot_data["status"] = "running"
            await db_put(f"managed_bots/{selected_bot_id}", bot_data)
            await update.message.reply_text(f"✅ بۆتی @{username} دەستی پێکرد.", reply_markup=CONTROL_PANEL)
        
        elif text == "⏸ وەستاندن":
            bot_data["status"] = "stopped"
            await db_put(f"managed_bots/{selected_bot_id}", bot_data)
            await update.message.reply_text(f"🛑 بۆتی @{username} وەستاندرا.", reply_markup=CONTROL_PANEL)

        elif text == "🔄 نوێکردنەوە":
            bot_data["status"] = "running"
            await db_put(f"managed_bots/{selected_bot_id}", bot_data)
            await update.message.reply_text(f"🔄 بۆتی @{username} نوێکرایەوە و کار دەکات.", reply_markup=CONTROL_PANEL)

        elif text == "🗑 سڕینەوە":
            await db_del(f"managed_bots/{selected_bot_id}")
            await db_del(f"users/{user_id}/selected_bot")
            await update.message.reply_text(f"🗑 بۆتی @{username} بە تەواوی سڕایەوە!", reply_markup=MAIN_MENU)
        return

    # 7. وەرگرتن و چالاککردنی تۆکێن (شۆڕشەکە لێرەدایە!)
    if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", text):
        # پشکنین بزانین ئایا لە دۆخی داواکردنی تۆکێندایە
        state = await db_get(f"users/{user_id}/state")
        if state != "waiting_reaction_token":
            await update.message.reply_text("⚠️ تکایە لەسەرەتاوە کلیک لە '➕ دروستکردنی بۆتی نوێ' بکە.")
            return

        status_msg = await update.message.reply_text("⏳ خەریکی چالاککردنی بۆتەکەم...")
        
        # لێرەدا ڕاستەوخۆ پەیوەندی دەکەین بە API ی تێلیگرامەوە (بێ کێشەترین شێواز)
        async with httpx.AsyncClient() as client:
            try:
                # 1. پشکنینی تۆکێن
                res = await client.get(f"https://api.telegram.org/bot{text}/getMe")
                if res.status_code != 200 or not res.json().get("ok"):
                    await status_msg.edit_text("❌ تۆکێنەکە هەڵەیە یان کار ناکات.")
                    return
                
                bot_info = res.json()["result"]
                bot_id_str = str(bot_info["id"])
                bot_username = bot_info["username"]
                bot_first_name = bot_info["first_name"]
                
                # 2. بەستنەوەی وەبهووک
                safe_url = PROJECT_URL.rstrip('/')
                webhook_url = f"{safe_url}/api/bot/{text}"
                res2 = await client.post(f"https://api.telegram.org/bot{text}/setWebhook", json={"url": webhook_url})
                
                if res2.status_code != 200 or not res2.json().get("ok"):
                    await status_msg.edit_text("❌ هەڵەیەک ڕوویدا لە بەستنەوەی وەبەهوک بە سێرڤەرەوە.")
                    return
                
                # 3. پاشەکەوتکردن لە داتابەیس
                await db_put(f"managed_bots/{bot_id_str}", {
                    "token": text,
                    "owner": user_id,
                    "bot_username": bot_username,
                    "bot_name": bot_first_name,
                    "status": "running"
                })
                await db_del(f"users/{user_id}/state") # سڕینەوەی دۆخەکە
                
                msg = (
                    f"✅ <b>بۆتەکەت سەرکەوتووانە دروست کرا!</b>\n\n"
                    f"🤖 ناو: {html.escape(bot_first_name)}\n"
                    f"🔗 یوزەر: @{bot_username}\n\n"
                    f"ئێستا لە بەشی <b>'📂 بۆتەکانم'</b> دەتوانیت کۆنترۆڵی بکەیت."
                )
                await status_msg.edit_text(msg, parse_mode="HTML")
            except Exception as e:
                await status_msg.edit_text(f"❌ هەڵەیەکی چاوەڕواننەکراو ڕوویدا: {str(e)}")
        return

    # ئەگەر شتێکی تر بوو
    await update.message.reply_text("تکایە لە کیبۆردی خوارەوە هەڵبژێرە:", reply_markup=MAIN_MENU)

master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_commands))

# ==============================================================================
# ── 2. CHILD BOT LOGIC (بەبێ ئەوەی جام بکات)
# ==============================================================================
async def process_child_update(token: str, body: dict):
    try:
        bot_id_str = token.split(":")[0]
        bot_data = await db_get(f"managed_bots/{bot_id_str}")
        
        # پشکنین بزانین ئایا بۆتەکە کارپێکراوە؟
        if not bot_data or bot_data.get("status") != "running":
            return

        bot_username = bot_data.get("bot_username", "UnknownBot")
        bot_name = bot_data.get("bot_name", "Reaction Bot")

        # دۆزینەوەی پەیامەکە
        msg = body.get("message") or body.get("channel_post")
        if not msg: return

        chat_id = msg["chat"]["id"]
        message_id = msg["message_id"]
        text = msg.get("text", "")
        
        from_user = msg.get("from", {})
        user_name = html.escape(from_user.get("first_name", "Subscriber"))
        user_id = from_user.get("id", 0)

        # بەکارهێنانی HTTPx ی ڕاستەوخۆ بۆ وەڵامدانەوەی خێرا
        async with httpx.AsyncClient() as client:
            if text.startswith('/start'):
                keyboard = {
                    "inline_keyboard": [[{"text": "My channel ✌", "url": f"https://t.me/{CHANNEL_USER}"}],[
                            {"text": "ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᵍʳᵒᵘᵖ ✨", "url": f"https://t.me/{bot_username}?startgroup=new"},
                            {"text": "ᵃᵈᵈ ᵐᵉ ᵗᵒ ʸᵒᵘʳ ᶜʰᵃᶰᶰᵉˡ 🎶", "url": f"https://t.me/{bot_username}?startchannel=new"}
                        ],[{"text": "ᵖʳᵒᵍʳᵃᵐᵐᵉʳ 🎧", "url": f"tg://user?id={OWNER_ID}"}]
                    ]
                }
                
                caption = (
                    f"Hi dear, <a href='tg://user?id={user_id}'>{user_name}</a>\n\n"
                    f"I'm a reaction bot 🍓, my name is <b>{html.escape(bot_name)}</b>\n"
                    f"My job is to interact with messages using {' '.join(EMOJIS)}\n"
                    f"I can interact in groups, channels and private chats 🌼\n"
                    f"Just add me to your group or channel and make me an admin with simple permissions ☘️\n"
                    f"And I will interact with every message you send. Try me now 💗"
                )

                payload = {
                    "chat_id": chat_id,
                    "photo": PHOTO_URL,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                    "reply_to_message_id": message_id
                }
                # ناردنی وێنە
                await client.post(f"https://api.telegram.org/bot{token}/sendPhoto", json=payload)
            
            else:
                # ڕیاکشن بۆ نامەکان
                emoji = random.choice(EMOJIS)
                payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reaction":[{"type": "emoji", "emoji": emoji}]
                }
                await client.post(f"https://api.telegram.org/bot{token}/setMessageReaction", json=payload)

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
    return {"status": "Bot Maker Panel is Active & Ultra Fast! 🚀"}
