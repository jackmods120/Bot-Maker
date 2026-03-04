import os, logging, httpx, asyncio, json
from fastapi import FastAPI, Request, BackgroundTasks
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
# زانیارییەکان لە Vercel وەردەگرێت
MASTER_TOKEN = os.getenv("BOT_TOKEN") 
PROJECT_URL  = os.getenv("PROJECT_URL") 
DB_URL       = os.getenv("DB_URL") 
DB_SECRET    = os.getenv("DB_SECRET")

# لۆگین بۆ زانینی کێشەکان
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── DATABASE HELPERS (FIREBASE) ───────────────────────────────────────────────
def fb_url(path):
    # دروستکردنی لینکی داتابەیس بە شێوەیەکی پارێزراو
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def db_get(path):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(fb_url(path))
            return r.json() if r.status_code == 200 else None
        except:
            return None

async def db_put(path, data):
    async with httpx.AsyncClient() as client:
        try:
            await client.put(fb_url(path), json=data)
        except:
            pass

async def db_del(path):
    async with httpx.AsyncClient() as client:
        try:
            await client.delete(fb_url(path))
        except:
            pass

# ==============================================================================
# ── 1. MASTER BOT LOGIC (بۆتە سەرەکییەکە)
# ==============================================================================
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 بەخێربێیت بۆ بۆت مەیکەری وەڵامدانەوە!\n\n"
        "تکایە تۆکێنی بۆتەکەت بنێرە (Bot Token)، من دەیکەم بە بۆتێکی وەڵامدانەوەی خۆکار.\n\n"
        "تۆکێن لە @BotFather وەربگرە و لێرە بینێرە."
    )

async def handle_master_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    
    # پشکنینی سەرەتایی تۆکێن
    if ":" not in token or len(token) < 20:
        await update.message.reply_text("❌ تۆکێنەکە نادروستە! دڵنیابە کۆپییەکی ڕاستت ناردووە."); return

    status = await update.message.reply_text("⏳ خەریکی چالاککردنم...")
    
    try:
        # پشکنینی ڕاستی تۆکێنەکە
        bot_user = Bot(token=token)
        me = await bot_user.get_me()
        
        # بەستنەوەی وەبهووک بە سێرڤەری ئێمەوە
        webhook_url = f"{PROJECT_URL}/api/child_bot?token={token}"
        await bot_user.set_webhook(url=webhook_url)
        
        # پاشەکەوتکردنی زانیاری لە داتابەیس
        bot_id_str = str(me.id)
        await db_put(f"managed_bots/{bot_id_str}", {
            "token": token,
            "owner_id": update.effective_user.id,
            "bot_username": me.username
        })

        # ناردنی پەیامی سەرکەوتن بەبێ ئەستێرە (**)
        msg = (
            f"✅ بۆتەکەت چالاک کرا!\n\n"
            f"🤖 ناو: {me.first_name}\n"
            f"🔗 یوزەر: @{me.username}\n\n"
            f"⚙️ ڕێنمایی بەکارهێنان:\n"
            f"بڕۆ ناو بۆتە نوێیەکەت و ئەم فەرمانانە بنووسە:\n\n"
            f"1. زیادکردنی وەڵام:\n"
            f"/add کلیل وەڵام\n"
            f"نموونە: /add سڵاو بەخێربێیت بۆ چەناڵەکەمان\n\n"
            f"2. سڕینەوەی وەڵام:\n"
            f"/del کلیل\n\n"
            f"3. بینینی وەڵامەکان:\n"
            f"/list"
        )
        await status.edit_text(msg)
        
    except Exception as e:
        await status.edit_text(f"❌ هەڵە ڕوویدا: {str(e)}")

# دروستکردنی ئەپی بۆتە سەرەکییەکە
master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_master_messages))


# ==============================================================================
# ── 2. CHILD BOT LOGIC (بۆتە دروستکراوەکان)
# ==============================================================================
async def process_child_update(token: str, body: dict):
    """
    ئەم بەشە بەرپرسە لە بەڕێوەبردنی هەموو ئەو بۆتانەی دروست دەکرێن
    """
    try:
        # دروستکردنی پەیوەندی کاتی
        bot = Bot(token=token)
        update = Update.de_json(body, bot)
        
        if not update.message or not update.message.text:
            return
        
        text = update.message.text
        chat_id = update.message.chat_id
        bot_info = await bot.get_me()
        bot_id_str = str(bot_info.id)

        # ─── فەرمانەکان ───

        # 1. زیادکردن (/add)
        if text.startswith("/add"):
            parts = text.split(" ", 2)
            if len(parts) < 3:
                await bot.send_message(chat_id, "⚠️ هەڵە! تکایە ئاوا بنووسە:\n/add کلیل وەڵام")
                return
            
            keyword = parts[1] # ئەو وشەیەی دەینێرن
            answer = parts[2]  # ئەو وەڵامەی بۆتەکە دەیداتەوە
            
            # خەزنکردن لە داتابەیس
            # ڕێڕەو: replies -> bot_id -> keyword
            await db_put(f"replies/{bot_id_str}/{keyword}", answer)
            await bot.send_message(chat_id, f"✅ وەڵام بۆ وشەی '{keyword}' زیاد کرا.")
            return

        # 2. سڕینەوە (/del)
        if text.startswith("/del"):
            keyword = text.replace("/del", "").strip()
            if not keyword:
                await bot.send_message(chat_id, "⚠️ تکایە وشەکە بنووسە. نموونە:\n/del سڵاو")
                return
            
            await db_del(f"replies/{bot_id_str}/{keyword}")
            await bot.send_message(chat_id, f"🗑 وشەی '{keyword}' سڕایەوە.")
            return

        # 3. لیست (/list)
        if text == "/list":
            data = await db_get(f"replies/{bot_id_str}")
            if not data:
                await bot.send_message(chat_id, "📭 هیچ وەڵامێک زیاد نەکراوە.")
                return
            
            msg = "📋 لیستی وەڵامەکان:\n\n"
            for k, v in data.items():
                msg += f"🔹 {k} ➡️ {v}\n"
            await bot.send_message(chat_id, msg)
            return

        # 4. یارمەتی (/help)
        if text == "/help" or text == "/start":
            msg = (
                "👋 بەخێربێیت! من بۆتی وەڵامدانەوەم.\n\n"
                "فەرمانەکان:\n"
                "/add کلیل وەڵام - زیادکردنی وەڵام\n"
                "/del کلیل - سڕینەوەی وەڵام\n"
                "/list - بینینی هەموو وەڵامەکان"
            )
            await bot.send_message(chat_id, msg)
            return

        # ─── وەڵامدانەوەی خۆکار ───
        
        # هێنانی هەموو وەڵامەکانی ئەم بۆتە
        all_replies = await db_get(f"replies/{bot_id_str}")
        
        if all_replies and text in all_replies:
            # ئەگەر وشەکە هەبوو، وەڵام دەداتەوە
            await bot.send_message(chat_id, all_replies[text])

    except Exception as e:
        logger.error(f"Child Bot Error: {e}")

# ==============================================================================
# ── 3. FASTAPI ROUTES (ڕاوتەرەکان)
# ==============================================================================

@app.post("/api/main")
async def master_webhook_handler(request: Request):
    """وەبەهووک بۆ بۆتە سەرەکییەکە (Master Bot)"""
    try:
        if not master_app.running:
            await master_app.initialize()
        
        data = await request.json()
        await master_app.process_update(Update.de_json(data, master_app.bot))
        return {"ok": True}
    except Exception as e:
        logger.error(f"Master Webhook Error: {e}")
        return {"ok": False}


@app.post("/api/child_bot")
async def child_webhook_handler(request: Request, token: str, background_tasks: BackgroundTasks):
    """
    وەبەهووک بۆ بۆتە دروستکراوەکان (Child Bots).
    Vercel پارامیتەری 'token' دەنێرێت، ئێمەش دەینێرین بۆ 'process_child_update'.
    """
    try:
        data = await request.json()
        # بەکارهێنانی BackgroundTasks بۆ خێرایی
        background_tasks.add_task(process_child_update, token, data)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/main")
async def health_check():
    return {"status": "Active", "mode": "Auto Reply Bot Maker"}
