import os, logging, httpx, asyncio, random, html, re
from fastapi import FastAPI, Request
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ── CONFIGURATION (ڕێکخستنەکان) ──────────────────────────────────────────────
MASTER_TOKEN = os.getenv("BOT_TOKEN") 
PROJECT_URL  = os.getenv("PROJECT_URL") 
DB_URL       = os.getenv("DB_URL") 
DB_SECRET    = os.getenv("DB_SECRET")

OWNER_ID = 5977475208  # ئایدی تۆ
CHANNEL_USER = "j4ck_721s"
EMOJIS =["❤️", "🔥", "🎉", "👏", "🤩", "💯", "🥰", "⚡️", "🍓", "👑"]
PHOTO_URL = "https://jobin-bro-143-02-7e44d11483ed.herokuapp.com//dl/24585?code=21c8667075cad1c405c844a32363059fc6f15bd353cfbea4"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── KEYBOARDS (کیبۆردەکان) ──────────────────────────────────────────────────
# 1. مینیوی بەکارهێنەر
USER_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("➕ دروستکردنی بۆتی نوێ")],[KeyboardButton("📂 بۆتەکانم (کۆنترۆڵ)")],
    [KeyboardButton("ℹ️ دەربارە")]
], resize_keyboard=True)

# 2. مینیوی خاوەن (تەنیا بۆ تۆیە)
OWNER_MENU = ReplyKeyboardMarkup([[KeyboardButton("➕ دروستکردنی بۆتی نوێ"), KeyboardButton("📂 بۆتەکانم (کۆنترۆڵ)")],
    [KeyboardButton("👑 پانێڵی خاوەن")],[KeyboardButton("ℹ️ دەربارە")]
], resize_keyboard=True)

# 3. ناو پانێڵی خاوەن
OWNER_PANEL_KB = ReplyKeyboardMarkup([[KeyboardButton("📊 ئاماری گشتی"), KeyboardButton("📢 ناردنی نامەی گشتی")],
    [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]
], resize_keyboard=True)

# 4. پانێڵی کۆنترۆڵی بۆتی بەکارهێنەر
CONTROL_PANEL = ReplyKeyboardMarkup([[KeyboardButton("▶️ کارپێکردن"), KeyboardButton("⏸ ڕاگرتن")],
    [KeyboardButton("🗑 سڕینەوەی بۆت")],[KeyboardButton("🔙 گەڕانەوە بۆ لیست")]
], resize_keyboard=True)


# ── DATABASE HELPERS (یارمەتیدەرەکانی داتابەیس) ─────────────────────────────
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
    user_id = update.effective_user.id
    first_name = html.escape(update.effective_user.first_name)
    
    # خەزنکردنی ئایدی یوزەر بۆ مەبەستی برۆدکاست (ناردنی گشتی)
    await db_put(f"users_list/{user_id}", True)
    await db_del(f"user_state/{user_id}") # سڕینەوەی هەر دۆخێکی پێشوو
    
    msg = (
        f"👋 <b>سڵاو {first_name} گیان! بەخێربێیت.</b>\n\n"
        f"🤖 لێرە دەتوانیت بە ئاسانترین شێوە بۆتی ڕیاکشن بۆ خۆت دروست بکەیت.\n"
        f"تکایە لە دوگمەکانی خوارەوە هەڵبژێرە:"
    )
    
    # جیاکردنەوەی کیبۆردی تۆ لە کەسانی تر
    if user_id == OWNER_ID:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=OWNER_MENU)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=USER_MENU)

async def handle_text_commands(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    menu_to_use = OWNER_MENU if user_id == OWNER_ID else USER_MENU

    # ─── دۆخی چاوەڕوانی (بۆ ناردنی برۆدکاست) ───
    state = await db_get(f"user_state/{user_id}")
    if state == "waiting_for_broadcast" and user_id == OWNER_ID:
        if text == "🔙 گەڕانەوە بۆ سەرەتا":
            await db_del(f"user_state/{user_id}")
            await master_start(update, ctx)
            return
            
        users = await db_get("users_list") or {}
        sent_count = 0
        status_msg = await update.message.reply_text("⏳ خەریکی ناردنی نامەکەم بۆ بەکارهێنەران...")
        
        for uid in users.keys():
            try:
                await ctx.bot.copy_message(chat_id=int(uid), from_chat_id=update.message.chat_id, message_id=update.message.message_id)
                sent_count += 1
                await asyncio.sleep(0.05) # پاراستن لە فڵۆد
            except: pass
            
        await db_del(f"user_state/{user_id}")
        await status_msg.edit_text(f"✅ <b>نامەکە بە سەرکەوتوویی نێردرا بۆ {sent_count} کەس.</b>", parse_mode="HTML")
        await update.message.reply_text("گەڕایتەوە مینیوی سەرەکی:", reply_markup=OWNER_MENU)
        return

    # ─── فەرمانە بنچینەییەکان ───
    if text == "🔙 گەڕانەوە بۆ سەرەتا":
        await db_del(f"user_state/{user_id}")
        await master_start(update, ctx)
        return

    if text == "ℹ️ دەربارە":
        msg = (
            "👨‍💻 <b>دەربارەی ئێمە</b>\n\n"
            "ئەم بۆتە دروستکراوە بۆ ئاسانکاری دروستکردنی بۆتی تێلیگرام بەبێ هیچ کۆدینێک.\n"
            f"پەرەپێدەر: @{CHANNEL_USER}"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=menu_to_use)
        return

    # ─── بەشی دروستکردن ───
    if text == "➕ دروستکردنی بۆتی نوێ":
        kb = ReplyKeyboardMarkup([[KeyboardButton("🍓 بۆتی ڕیاکشن")],[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text("🤖 <b>تکایە جۆری بۆتەکە هەڵبژێرە:</b>", parse_mode="HTML", reply_markup=kb)
        return

    if text == "🍓 بۆتی ڕیاکشن":
        await db_put(f"user_state/{user_id}", "waiting_for_token")
        kb = ReplyKeyboardMarkup([[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        msg = (
            "🍓 <b>دروستکردنی بۆتی ڕیاکشن</b>\n\n"
            "بڕۆرە ناو @BotFather، بۆتێکی نوێ دروست بکە، پاشان <b>تۆکێنەکەی (Bot Token)</b> کۆپی بکە و لێرە بۆمی بنێرە:\n\n"
            "<i>نموونە: 1234567890:ABCdefGhIJKlmNoPQRstUVwxyZ</i>"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)
        return

    # ─── لیستی بۆتەکانی بەکارهێنەر ───
    if text == "📂 بۆتەکانم (کۆنترۆڵ)" or text == "🔙 گەڕانەوە بۆ لیست":
        all_bots = await db_get("managed_bots") or {}
        user_bots = {k: v for k, v in all_bots.items() if str(v.get("owner")) == str(user_id)}

        if not user_bots:
            await update.message.reply_text("📭 تۆ هیچ بۆتێکت دروست نەکردووە تا ئێستا!", reply_markup=menu_to_use)
            return

        bot_buttons =[]
        for b_id, info in user_bots.items():
            bot_buttons.append([KeyboardButton(f"🤖 @{info.get('bot_username', 'Bot')} ({b_id})")])
        bot_buttons.append([KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")])
        
        await update.message.reply_text("📂 <b>لیستی بۆتەکانت:</b>\nکام بۆتە دەتەوێت کۆنترۆڵ بکەیت؟", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(bot_buttons, resize_keyboard=True))
        return

    # ─── چوونە ناو پانێڵی بۆتێک ───
    if text.startswith("🤖 @") and "(" in text and ")" in text:
        bot_id = text.split("(")[-1].replace(")", "").strip()
        bot_data = await db_get(f"managed_bots/{bot_id}")
        
        if bot_data and str(bot_data.get("owner")) == str(user_id):
            await db_put(f"user_state/{user_id}_selected_bot", bot_id)
            status = bot_data.get("status", "running")
            status_icon = "🟢 کاردەکات" if status == "running" else "🔴 ڕاگیراوە"
            
            msg = (
                f"⚙️ <b>پانێڵی کۆنترۆڵ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 یوزەر: @{bot_data.get('bot_username')}\n"
                f"📊 دۆخ: <b>{status_icon}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"لە خوارەوە فەرمانێک هەڵبژێرە:"
            )
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=CONTROL_PANEL)
        else:
            await update.message.reply_text("❌ ئەم بۆتە نەدۆزرایەوە یان هی تۆ نییە!")
        return

    # ─── دوگمەکانی کۆنترۆڵکردنی بۆت ───
    if text in["▶️ کارپێکردن", "⏸ ڕاگرتن", "🗑 سڕینەوەی بۆت"]:
        bot_id = await db_get(f"user_state/{user_id}_selected_bot")
        if not bot_id:
            await update.message.reply_text("⚠️ سەرەتا بۆتێک لە لیستەکە هەڵبژێرە.")
            return

        bot_data = await db_get(f"managed_bots/{bot_id}")
        if not bot_data:
            await update.message.reply_text("❌ بۆتەکە نەدۆزرایەوە.")
            return

        uname = bot_data.get("bot_username")

        if text == "▶️ کارپێکردن":
            bot_data["status"] = "running"
            await db_put(f"managed_bots/{bot_id}", bot_data)
            await update.message.reply_text(f"✅ بۆتی @{uname} خرایە کار.", reply_markup=CONTROL_PANEL)
            
        elif text == "⏸ ڕاگرتن":
            bot_data["status"] = "stopped"
            await db_put(f"managed_bots/{bot_id}", bot_data)
            await update.message.reply_text(f"🛑 بۆتی @{uname} وەستێنرا.", reply_markup=CONTROL_PANEL)
            
        elif text == "🗑 سڕینەوەی بۆت":
            await db_del(f"managed_bots/{bot_id}")
            await db_del(f"user_state/{user_id}_selected_bot")
            await update.message.reply_text(f"🗑 بۆتی @{uname} بە تەواوی سڕایەوە!", reply_markup=menu_to_use)
        return

    # ─── پانێڵی خاوەن (تەنیا بۆ تۆ) ───
    if text == "👑 پانێڵی خاوەن" and user_id == OWNER_ID:
        await update.message.reply_text("👑 <b>بەخێربێیت گەورەم بۆ پانێڵی سەرەکی.</b>", parse_mode="HTML", reply_markup=OWNER_PANEL_KB)
        return

    if text == "📊 ئاماری گشتی" and user_id == OWNER_ID:
        all_users = await db_get("users_list") or {}
        all_bots = await db_get("managed_bots") or {}
        running = sum(1 for b in all_bots.values() if b.get("status") == "running")
        
        msg = (
            f"📊 <b>ئاماری ڕاستەوخۆ:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👥 کۆی بەکارهێنەران: <b>{len(all_users)}</b> کەس\n"
            f"🤖 کۆی بۆتەکان: <b>{len(all_bots)}</b> بۆت\n"
            f"🟢 بۆتە چالاکەکان: <b>{running}</b> بۆت\n"
            f"🔴 بۆتە وەستاوەکان: <b>{len(all_bots) - running}</b> بۆت\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=OWNER_PANEL_KB)
        return

    if text == "📢 ناردنی نامەی گشتی" and user_id == OWNER_ID:
        await db_put(f"user_state/{user_id}", "waiting_for_broadcast")
        kb = ReplyKeyboardMarkup([[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text("✍️ <b>تکایە ئەو نامەیە بنێرە کە دەتەوێت بۆ هەمووانی بنێریت (دەتوانیت وێنە و ڤیدیۆش بنێریت):</b>", parse_mode="HTML", reply_markup=kb)
        return

    # ─── وەرگرتنی تۆکێن ───
    if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", text):
        state = await db_get(f"user_state/{user_id}")
        if state != "waiting_for_token":
            await update.message.reply_text("⚠️ بۆ دروستکردنی بۆت، کلیک لە '➕ دروستکردنی بۆتی نوێ' بکە.")
            return

        status_msg = await update.message.reply_text("⏳ خەریکی پەیوەندیکردنم بە تێلیگرامەوە...", reply_markup=menu_to_use)
        
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(f"https://api.telegram.org/bot{text}/getMe")
                if not res.json().get("ok"):
                    await status_msg.edit_text("❌ تۆکێنەکە کار ناکات. تکایە دڵنیابە لە ڕاستییەکەی.")
                    return
                
                b_info = res.json()["result"]
                b_id = str(b_info["id"])
                
                safe_url = PROJECT_URL.rstrip('/')
                wh_url = f"{safe_url}/api/bot/{text}"
                res2 = await client.post(f"https://api.telegram.org/bot{text}/setWebhook", json={"url": wh_url})
                
                if not res2.json().get("ok"):
                    await status_msg.edit_text("❌ کێشەیەک لە سێرڤەر ڕوویدا، نەتوانرا وەبەهوک ببەسترێتەوە.")
                    return
                
                await db_put(f"managed_bots/{b_id}", {
                    "token": text,
                    "owner": user_id,
                    "bot_username": b_info["username"],
                    "bot_name": b_info["first_name"],
                    "status": "running"
                })
                await db_del(f"user_state/{user_id}")
                
                msg = (
                    f"✅ <b>پیرۆزە! بۆتەکەت دروست کرا.</b>\n\n"
                    f"🤖 یوزەر: @{b_info['username']}\n"
                    f"✨ ناو: {html.escape(b_info['first_name'])}\n\n"
                    f"بۆتەکە ئێستا ئامادەیە و کاردەکات! دەتوانیت لە بەشی <b>📂 بۆتەکانم</b> کۆنترۆڵی بکەیت."
                )
                await status_msg.edit_text(msg, parse_mode="HTML")
            except Exception as e:
                await status_msg.edit_text("❌ کێشەیەک ڕوویدا لە کاتی پەیوەندیکردن.")
        return

    # ئەگەر شتێکی نەناسراو بوو
    await update.message.reply_text("تکایە لە کیبۆردی خوارەوە دوگمەیەک هەڵبژێرە:", reply_markup=menu_to_use)

master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_text_commands))

# ==============================================================================
# ── 2. CHILD BOT LOGIC (بۆتە دروستکراوەکان بە خێرایی باڵا)
# ==============================================================================
async def process_child_update(token: str, body: dict):
    try:
        bot_id_str = token.split(":")[0]
        bot_data = await db_get(f"managed_bots/{bot_id_str}")
        
        # ئەگەر بۆتەکە وەستێنرابوو، هیج وەڵامێک ناداتەوە
        if not bot_data or bot_data.get("status") != "running": return

        bot_username = bot_data.get("bot_username", "Bot")
        bot_name = bot_data.get("bot_name", "Reaction Bot")

        msg = body.get("message") or body.get("channel_post")
        if not msg: return

        chat_id = msg["chat"]["id"]
        message_id = msg["message_id"]
        text = msg.get("text", "")
        
        from_user = msg.get("from", {})
        user_name = html.escape(from_user.get("first_name", "Subscriber"))
        user_id = from_user.get("id", 0)

        async with httpx.AsyncClient() as client:
            if text.startswith('/start'):
                keyboard = {
                    "inline_keyboard":[[{"text": "کەناڵی گەشەپێدەر ✌", "url": f"https://t.me/{CHANNEL_USER}"}],[
                            {"text": "✨ زیادکردن بۆ گرووپ", "url": f"https://t.me/{bot_username}?startgroup=new"},
                            {"text": "🎶 زیادکردن بۆ چەناڵ", "url": f"https://t.me/{bot_username}?startchannel=new"}
                        ],[{"text": "🎧 دروستکەر", "url": f"tg://user?id={OWNER_ID}"}]
                    ]
                }
                
                caption = (
                    f"سڵاو ئازیزم، <a href='tg://user?id={user_id}'>{user_name}</a>\n\n"
                    f"من بۆتی ڕیاکشنم 🍓، ناوم <b>{html.escape(bot_name)}</b> ە.\n"
                    f"کاری من دانانی ڕیاکشنە بۆ نامەکانت بەم ئیمۆجیانە {' '.join(EMOJIS[:4])}\n"
                    f"دەتوانم لە گرووپ، چەناڵ و چاتی تایبەت کار بکەم 🌼\n"
                    f"تەنها من زیاد بکە بۆ گرووپ یان چەناڵەکەت و بمکە بە ئەدمین ☘️\n"
                    f"ئیتر من ڕیاکشن بۆ هەموو نامەیەک دادەنێم. ئێستا تاقیم بکەرەوە 💗"
                )

                payload = {
                    "chat_id": chat_id,
                    "photo": PHOTO_URL,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                    "reply_to_message_id": message_id
                }
                await client.post(f"https://api.telegram.org/bot{token}/sendPhoto", json=payload)
            
            else:
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
# ── 3. ROUTES & KEEP-ALIVE PING 
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

# ئەم ڕاوتەرە تایبەت دروستکراوە بۆ ئەوەی بۆتەکە نەخەوێت!
@app.get("/api/ping")
async def keep_awake(): 
    return {"status": "I am awake and fast! ⚡️"}
