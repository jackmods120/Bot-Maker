# ==============================================================================
# ==           BOT MAKER - CREATE YOUR OWN BOT HOSTING                        ==
# ==           Developed for: @j4ck_721s                                      ==
# ==                                                                          ==
# ==============================================================================

import os, logging, httpx, asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.error import InvalidToken

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
# تۆکێنی بۆتە سەرەکییەکەت (Bot Maker)
MASTER_TOKEN = os.getenv("BOT_TOKEN") 
# لینکی پڕۆژەکەت لە ڤێرسێل (بەبێ / لە کۆتایی) - زۆر گرنگە
# نموونە: https://my-bot-maker.vercel.app
PROJECT_URL  = os.getenv("PROJECT_URL") 

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ==============================================================================
# ── 1. MASTER BOT LOGIC (بۆتە سەرەکییەکە)
# ==============================================================================

async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **بەخێربێیت بۆ بۆت مەیکەر!**\n\n"
        "من دەتوانم بۆتەکەت بۆ کار پێ بکەم (Host) بەخۆڕایی.\n"
        "تەنها **تۆکێنی بۆتەکەت (Bot Token)**ـم بۆ بنێرە کە لە @BotFather وەرتگرتووە.\n\n"
        "👇 **تۆکێن بنێرە:**"
    )

async def handle_token_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    user_id = update.effective_user.id
    
    # پشکنینی سەرەتایی تۆکێن (دەبێت ژمارە و دوای دووخاڵ پیت بێت)
    if ":" not in msg or len(msg) < 30:
        await update.message.reply_text("❌ **تۆکێن هەڵەیە!**\nتکایە تۆکێنی ڕاست دابنێ."); return

    new_token = msg
    status_msg = await update.message.reply_text("⏳ **پشکنین و کارپێکردن...**")

    # پشکنین و بەستنەوەی وەبهووک
    try:
        # ١. پشکنین بزانین تۆکێنەکە ئیش دەکات؟
        test_bot = Bot(token=new_token)
        bot_info = await test_bot.get_me()
        
        # ٢. دانانی وەبهووک بۆ بۆتە نوێیەکە
        # بەستنەوەی بە ڕاوتەری تایبەتی خۆمانەوە (/api/child_bot)
        if not PROJECT_URL:
             await status_msg.edit_text("❌ هەڵە لە سێرڤەر: `PROJECT_URL` دانەنراوە."); return

        webhook_url = f"{PROJECT_URL}/api/child_bot?token={new_token}"
        await test_bot.set_webhook(url=webhook_url)

        await status_msg.edit_text(
            f"✅ **پیرۆزە! بۆتەکەت کارا کرا.**\n\n"
            f"🤖 **ناوی بۆت:** {bot_info.first_name}\n"
            f"🔗 **یوزەر:** @{bot_info.username}\n\n"
            f"🚀 ئێستا بۆتەکەت چالاکە! هەر نامەیەکی بۆ بنێریت وەڵامت دەداتەوە (Echo Bot).\n"
            f"تێبینی: ئەمە نموونەیە، دەتوانیت لە داهاتوودا فەرمانی تری بۆ زیاد بکەیت."
        )

    except InvalidToken:
        await status_msg.edit_text("❌ **تۆکێنەکە هەڵەیە!** تێلیگرام ڕەتی کردەوە.")
    except Exception as e:
        await status_msg.edit_text(f"❌ **هەڵەیەک ڕوویدا:**\n{str(e)}")


# دروستکردنی ئەپلیکەیشنی بۆتە سەرەکییەکە
master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", start_command))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token_message))


# ==============================================================================
# ── 2. CHILD BOT LOGIC (بۆتە دروستکراوەکان)
# ==============================================================================

async def process_child_update(token: str, body: dict):
    """
    ئەم فەنکشنە بەرپرسە لە وەڵامدانەوەی ئەو بۆتانەی خەڵک دروستیان کردووە.
    لێرەدا دەتوانیت دیاری بکەیت بۆتە دروستکراوەکان چی بکەن.
    لە ئێستادا کردوومانە بە (Echo Bot) واتە هەمان نامە دەنیریتەوە.
    """
    try:
        # دروستکردنی بۆتێکی کاتی بەو تۆکێنەی هاتوە
        child_bot = Bot(token=token)
        update = Update.de_json(body, child_bot)

        if update.message and update.message.text:
            user_text = update.message.text
            chat_id = update.message.chat_id
            
            # نموونە: وەڵامدانەوەی نامەکان
            if user_text == "/start":
                await child_bot.send_message(chat_id, "👋 **سڵاو! من کاردەکەم.**\nمن لەڕێگەی بۆت مەیکەرەوە دروستکراوم.")
            else:
                await child_bot.send_message(chat_id, f"تۆ وتت: {user_text}")
                
    except Exception as e:
        logger.error(f"Child bot error: {e}")


# ==============================================================================
# ── 3. FASTAPI ROUTES (ڕاوتەرەکان)
# ==============================================================================

@app.post("/api/main")
async def master_webhook(request: Request):
    """وەبەهووک بۆ بۆتە سەرەکییەکە (Bot Maker)"""
    try:
        if not master_app.running:
            await master_app.initialize()
        
        data = await request.json()
        await master_app.process_update(Update.de_json(data, master_app.bot))
        return {"ok": True}
    except Exception as e:
        logger.error(f"Master Error: {e}")
        return {"ok": False}


@app.post("/api/child_bot")
async def child_webhook(request: Request, token: str, background_tasks: BackgroundTasks):
    """
    وەبەهووک بۆ هەموو بۆتە دروستکراوەکان.
    Vercel پارامیتەری ?token=... دەنێرێت بۆ ئێرە، ئێمەش دەزانین هی کێیە.
    """
    try:
        data = await request.json()
        # بەکارهێنانی BackgroundTasks بۆ ئەوەی Vercel Time-out نەکات
        background_tasks.add_task(process_child_update, token, data)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/main")
async def health():
    return {"status": "Bot Maker is Running", "master": "Active"}
