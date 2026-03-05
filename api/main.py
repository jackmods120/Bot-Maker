import os, logging, httpx, asyncio, random, html, re
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ── ڕێکخستنەکان ─────────────────────────────────────────────────────────────
MASTER_TOKEN = os.getenv("BOT_TOKEN")
PROJECT_URL  = os.getenv("PROJECT_URL")
DB_URL       = os.getenv("DB_URL")
DB_SECRET    = os.getenv("DB_SECRET")

OWNER_ID     = 5977475208
CHANNEL_USER = "j4ck_721s"
EMOJIS       = ["❤️", "🔥", "🎉", "👏", "🤩", "💯", "😍", "🫶", "⚡", "🌟"]
PHOTO_URL    = "https://jobin-bro-143-02-7e44d11483ed.herokuapp.com//dl/24585?code=21c8667075cad1c405c844a32363059fc6f15bd353cfbea4"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ══════════════════════════════════════════════════════════════════════════════
# ── کیبۆردەکان ────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def main_menu_kb(user_id: int):
    """کیبۆردی سەرەکی — بەپێی ئەوەی خاوەنی سیستەمە یان نەخێر جیاوازە"""
    if user_id == OWNER_ID:
        return ReplyKeyboardMarkup([
            [KeyboardButton("➕ دروستکردنی بۆتی نوێ"), KeyboardButton("📂 بۆتەکانم")],
            [KeyboardButton("👑 پانێلی سەرەکی"), KeyboardButton("📊 ئامارەکان")]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ دروستکردنی بۆتی نوێ"), KeyboardButton("📂 بۆتەکانم")]
    ], resize_keyboard=True)

CONTROL_PANEL = ReplyKeyboardMarkup([
    [KeyboardButton("▶️ دەستپێکردن"), KeyboardButton("⏸ وەستاندن")],
    [KeyboardButton("🔄 نوێکردنەوە"), KeyboardButton("📋 زانیاری بۆت")],
    [KeyboardButton("🗑 سڕینەوە"), KeyboardButton("🔙 گەڕانەوە بۆ لیست")]
], resize_keyboard=True)

OWNER_PANEL = ReplyKeyboardMarkup([
    [KeyboardButton("👥 هەموو بەکارهێنەرەکان"), KeyboardButton("🤖 هەموو بۆتەکان")],
    [KeyboardButton("📨 ناردنی پەیام بۆ هەموو"), KeyboardButton("🗑 سڕینەوەی بۆت بە ID")],
    [KeyboardButton("📊 ئامارەکان"), KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]
], resize_keyboard=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── هەلپەرەکانی داتابەیس ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def fb_url(path): return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def db_get(path):
    if not DB_URL: return None
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(fb_url(path))
            return r.json() if r.status_code == 200 else None
        except: return None

async def db_put(path, data):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as client:
        try: await client.put(fb_url(path), json=data)
        except: pass

async def db_patch(path, data):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as client:
        try: await client.patch(fb_url(path), json=data)
        except: pass

async def db_del(path):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as client:
        try: await client.delete(fb_url(path))
        except: pass

# ══════════════════════════════════════════════════════════════════════════════
# ── KEEP-ALIVE: بۆ ئەوەی بۆتەکە هەرگیز نەخەوێت ──────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

async def keep_alive_loop():
    """هەر ١٠ خولەک یەک جار سێرڤەرەکە ping دەکات تا نەخەوێت"""
    await asyncio.sleep(30)  # کاتی دەستپێکردنی سیستەم
    while True:
        try:
            safe_url = (PROJECT_URL or "").rstrip('/')
            if safe_url:
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.get(f"{safe_url}/ping")
                    logger.info("✅ Keep-alive ping ناردرا")
        except Exception as e:
            logger.warning(f"⚠️ Keep-alive هەڵە: {e}")
        await asyncio.sleep(600)  # ١٠ خولەک

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive_loop())
    logger.info("🚀 Keep-alive چالاک کرا")

@app.get("/ping")
async def ping():
    return {"status": "alive", "message": "بۆتەکە کاردەکات! 🟢"}

# ══════════════════════════════════════════════════════════════════════════════
# ── ١. بۆتی سەرەکی (Master Bot)
# ══════════════════════════════════════════════════════════════════════════════

async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id   = update.effective_user.id
    user_name = html.escape(update.effective_user.first_name or "بەکارهێنەر")

    await db_del(f"users/{user_id}/state")

    # خەزنکردنی بەکارهێنەر لە داتابەیس
    await db_patch(f"users/{user_id}", {
        "name": update.effective_user.first_name or "",
        "username": update.effective_user.username or "",
        "joined": True
    })

    if user_id == OWNER_ID:
        msg = (
            f"👑 <b>بەخێربێیت خاوەنی سیستەم، {user_name}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 پانێلی دروستکردنی بۆت چالاکە\n"
            "📊 دەتوانیت هەموو بەکارهێنەران و بۆتەکان بپشکنیت\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 هەڵبژاردنێک بکە:"
        )
    else:
        msg = (
            f"👋 <b>بەخێربێیت، {user_name}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 لێرە دەتوانیت بۆتی تایبەتی خۆت دروست بکەیت\n"
            "⚡ خێرا، ئاسان و بێ پێچیلەتی\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 لە کیبۆردی خوارەوە هەڵبژێرە:"
        )

    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_menu_kb(user_id))


async def handle_text_commands(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text.strip()
    user_id = update.effective_user.id

    # ── گەڕانەوە بۆ سەرەتا ──────────────────────────────────────────────────
    if text == "🔙 گەڕانەوە بۆ سەرەتا":
        await db_del(f"users/{user_id}/state")
        await master_start(update, ctx)
        return

    # ── مینیوی جۆری بۆت ─────────────────────────────────────────────────────
    if text == "➕ دروستکردنی بۆتی نوێ":
        kb = ReplyKeyboardMarkup([
            [KeyboardButton("🍓 بۆتی ڕیاکشن")],
            [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]
        ], resize_keyboard=True)
        await update.message.reply_text(
            "🤖 <b>جۆری بۆت هەڵبژێرە:</b>\n\n"
            "🍓 <b>بۆتی ڕیاکشن</b> — بۆتێکی دڵخوازە کە بۆ هەموو نامەیەک ئیموجی دەنێرێت",
            parse_mode="HTML", reply_markup=kb
        )
        return

    # ── هەڵبژاردنی بۆتی ڕیاکشن ──────────────────────────────────────────────
    if text == "🍓 بۆتی ڕیاکشن":
        await db_put(f"users/{user_id}/state", "waiting_reaction_token")
        kb = ReplyKeyboardMarkup([[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text(
            "🍓 <b>دروستکردنی بۆتی ڕیاکشن</b>\n\n"
            "📋 <b>مامەڵەکە:</b>\n"
            "١. بچۆ بۆ @BotFather لە تێلیگرام\n"
            "٢. بنووسە /newbot\n"
            "٣. ناوی بۆتەکەت دابنێ\n"
            "٤. تۆکێنەکەی کۆپی بکە و لێرە بینێرە\n\n"
            "⬇️ <b>تۆکێنەکەت بنێرە:</b>",
            parse_mode="HTML", reply_markup=kb
        )
        return

    # ── لیستی بۆتەکانم ──────────────────────────────────────────────────────
    if text in ["📂 بۆتەکانم", "🔙 گەڕانەوە بۆ لیست"]:
        all_bots  = await db_get("managed_bots") or {}
        user_bots = {k: v for k, v in all_bots.items() if v.get("owner") == user_id}

        if not user_bots:
            await update.message.reply_text(
                "📭 <b>هیچ بۆتێکت دروست نەکردووە!</b>\n\n"
                "کلیک لە '➕ دروستکردنی بۆتی نوێ' بکە",
                parse_mode="HTML", reply_markup=main_menu_kb(user_id)
            )
            return

        bot_buttons = []
        for b_id, info in user_bots.items():
            username = info.get("bot_username", "Bot")
            status   = "🟢" if info.get("status") == "running" else "🔴"
            bot_buttons.append([KeyboardButton(f"{status} @{username}")])

        bot_buttons.append([KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")])
        await update.message.reply_text(
            f"📂 <b>بۆتەکانت ({len(user_bots)} بۆت):</b>\n\nکام بۆتە دەتەوێت کۆنترۆڵ بکەیت؟\n🟢 کاردەکات  |  🔴 ڕاگیراوە",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(bot_buttons, resize_keyboard=True)
        )
        return

    # ── هەڵبژاردنی بۆتێک بۆ کۆنترۆڵ ────────────────────────────────────────
    if re.match(r"^[🟢🔴] @\S+$", text):
        selected_username = re.sub(r"^[🟢🔴] @", "", text).strip()
        all_bots = await db_get("managed_bots") or {}

        bot_id = None
        for k, v in all_bots.items():
            if v.get("owner") == user_id and v.get("bot_username") == selected_username:
                bot_id = k
                break

        if bot_id:
            await db_put(f"users/{user_id}/selected_bot", bot_id)
            info        = all_bots[bot_id]
            status      = info.get("status", "running")
            status_text = "🟢 کاردەکات" if status == "running" else "🔴 ڕاگیراوە"
            bot_name    = html.escape(info.get("bot_name", "ناسناو"))

            msg = (
                f"⚙️ <b>پانێلی کۆنترۆڵ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 ناو: {bot_name}\n"
                f"🔗 یوزەر: @{selected_username}\n"
                f"📊 دۆخ: {status_text}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"لە کیبۆردی خوارەوە کۆنترۆڵی بکە:"
            )
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=CONTROL_PANEL)
        else:
            await update.message.reply_text("❌ ئەم بۆتە نەدۆزرایەوە!", reply_markup=main_menu_kb(user_id))
        return

    # ── دوگمەکانی کۆنترۆڵ ────────────────────────────────────────────────────
    if text in ["▶️ دەستپێکردن", "⏸ وەستاندن", "🔄 نوێکردنەوە", "🗑 سڕینەوە", "📋 زانیاری بۆت"]:
        selected_bot_id = await db_get(f"users/{user_id}/selected_bot")
        if not selected_bot_id:
            await update.message.reply_text("⚠️ تکایە سەرەتا بۆتێک هەڵبژێرە.", reply_markup=main_menu_kb(user_id))
            return

        bot_data = await db_get(f"managed_bots/{selected_bot_id}")
        if not bot_data:
            await update.message.reply_text("❌ بۆتەکە سڕاوەتەوە.", reply_markup=main_menu_kb(user_id))
            return

        username = bot_data.get("bot_username", "Bot")
        bot_name = html.escape(bot_data.get("bot_name", "ناسناو"))

        if text == "▶️ دەستپێکردن":
            bot_data["status"] = "running"
            await db_put(f"managed_bots/{selected_bot_id}", bot_data)
            await update.message.reply_text(f"✅ بۆتی @{username} دەستی پێکرد.\n🟢 ئێستا کاردەکات!", reply_markup=CONTROL_PANEL)

        elif text == "⏸ وەستاندن":
            bot_data["status"] = "stopped"
            await db_put(f"managed_bots/{selected_bot_id}", bot_data)
            await update.message.reply_text(f"🛑 بۆتی @{username} وەستاندرا.\n🔴 ئێستا ڕاگیراوەیە.", reply_markup=CONTROL_PANEL)

        elif text == "🔄 نوێکردنەوە":
            bot_data["status"] = "running"
            await db_put(f"managed_bots/{selected_bot_id}", bot_data)
            # نوێکردنەوەی وەبهووک
            token    = bot_data.get("token", "")
            safe_url = (PROJECT_URL or "").rstrip('/')
            if token and safe_url:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(f"https://api.telegram.org/bot{token}/setWebhook",
                                      json={"url": f"{safe_url}/api/bot/{token}"})
            await update.message.reply_text(f"🔄 بۆتی @{username} نوێکرایەوە.\n✅ وەبهووکیش نوێکرایەوە!", reply_markup=CONTROL_PANEL)

        elif text == "📋 زانیاری بۆت":
            status_text = "🟢 کاردەکات" if bot_data.get("status") == "running" else "🔴 ڕاگیراوە"
            token_short = bot_data.get("token", "")[:10] + "..."
            msg = (
                f"📋 <b>زانیاری بۆت</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 ناو: {bot_name}\n"
                f"🔗 یوزەر: @{username}\n"
                f"📊 دۆخ: {status_text}\n"
                f"🆔 ID: <code>{selected_bot_id}</code>\n"
                f"🔑 تۆکێن: <code>{token_short}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=CONTROL_PANEL)

        elif text == "🗑 سڕینەوە":
            # داواکردنی دڵنیاکردنەوە
            await db_put(f"users/{user_id}/state", f"confirm_delete:{selected_bot_id}")
            confirm_kb = ReplyKeyboardMarkup([
                [KeyboardButton(f"✅ بەڵێ، بۆتی @{username} بسڕەوە")],
                [KeyboardButton("❌ نەخێر، دەرچوون")]
            ], resize_keyboard=True)
            await update.message.reply_text(
                f"⚠️ <b>دڵنیایت؟</b>\n\n"
                f"بۆتی @{username} بە تەواوی دەسڕیتەوە و ناتوانیت دووبارەی بگەڕێنیتەوە!",
                parse_mode="HTML", reply_markup=confirm_kb
            )
        return

    # ── دڵنیاکردنەوەی سڕینەوە ────────────────────────────────────────────────
    state = await db_get(f"users/{user_id}/state")
    if state and str(state).startswith("confirm_delete:"):
        bot_id_to_del = state.split(":", 1)[1]
        if text.startswith("✅ بەڵێ، بۆتی @"):
            bot_data = await db_get(f"managed_bots/{bot_id_to_del}") or {}
            username = bot_data.get("bot_username", "Bot")
            # سڕینەوەی وەبهووک
            token = bot_data.get("token", "")
            if token:
                async with httpx.AsyncClient(timeout=10) as client:
                    try: await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
                    except: pass
            await db_del(f"managed_bots/{bot_id_to_del}")
            await db_del(f"users/{user_id}/selected_bot")
            await db_del(f"users/{user_id}/state")
            await update.message.reply_text(
                f"🗑 <b>بۆتی @{username} بە تەواوی سڕایەوە!</b>",
                parse_mode="HTML", reply_markup=main_menu_kb(user_id)
            )
        elif text == "❌ نەخێر، دەرچوون":
            await db_del(f"users/{user_id}/state")
            await update.message.reply_text("↩️ گەڕایتەوە بۆ پانێڵ.", reply_markup=CONTROL_PANEL)
        return

    # ── پانێلی سەرەکی (تەنها بۆ OWNER) ─────────────────────────────────────
    if text == "👑 پانێلی سەرەکی":
        if user_id != OWNER_ID:
            await update.message.reply_text("❌ مافت نییە!", reply_markup=main_menu_kb(user_id))
            return
        all_bots  = await db_get("managed_bots") or {}
        all_users = await db_get("users") or {}
        running   = sum(1 for v in all_bots.values() if v.get("status") == "running")
        msg = (
            f"👑 <b>پانێلی سەرەکی — خاوەنی سیستەم</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👥 کۆی بەکارهێنەران: <b>{len(all_users)}</b>\n"
            f"🤖 کۆی بۆتەکان: <b>{len(all_bots)}</b>\n"
            f"🟢 بۆتی چالاک: <b>{running}</b>\n"
            f"🔴 بۆتی ڕاگیراو: <b>{len(all_bots) - running}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=OWNER_PANEL)
        return

    # ── ئامارەکان ─────────────────────────────────────────────────────────────
    if text == "📊 ئامارەکان":
        all_bots  = await db_get("managed_bots") or {}
        all_users = await db_get("users") or {}
        user_bots = {k: v for k, v in all_bots.items() if v.get("owner") == user_id}
        running   = sum(1 for v in user_bots.values() if v.get("status") == "running")

        if user_id == OWNER_ID:
            all_running = sum(1 for v in all_bots.values() if v.get("status") == "running")
            msg = (
                f"📊 <b>ئامارەکانی سیستەم</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👥 هەموو بەکارهێنەران: <b>{len(all_users)}</b>\n"
                f"🤖 هەموو بۆتەکان: <b>{len(all_bots)}</b>\n"
                f"🟢 چالاک: <b>{all_running}</b>  🔴 ڕاگیراو: <b>{len(all_bots) - all_running}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📁 بۆتەکانی خۆت: <b>{len(user_bots)}</b>"
            )
        else:
            msg = (
                f"📊 <b>ئامارەکانت</b>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🤖 بۆتی دروستکردوو: <b>{len(user_bots)}</b>\n"
                f"🟢 چالاک: <b>{running}</b>\n"
                f"🔴 ڕاگیراو: <b>{len(user_bots) - running}</b>\n"
                f"━━━━━━━━━━━━━━━━━"
            )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_menu_kb(user_id))
        return

    # ── هەموو بەکارهێنەران (OWNER) ────────────────────────────────────────────
    if text == "👥 هەموو بەکارهێنەران":
        if user_id != OWNER_ID:
            await update.message.reply_text("❌ مافت نییە!")
            return
        all_users = await db_get("users") or {}
        if not all_users:
            await update.message.reply_text("📭 هیچ بەکارهێنەرێک نییە.", reply_markup=OWNER_PANEL)
            return
        lines = [f"👥 <b>لیستی بەکارهێنەران ({len(all_users)}):</b>\n"]
        for uid, udata in list(all_users.items())[:30]:
            name     = html.escape(udata.get("name", "ناسناو"))
            username = udata.get("username", "")
            un_text  = f"@{username}" if username else "نییە"
            lines.append(f"• <a href='tg://user?id={uid}'>{name}</a> ({un_text}) — <code>{uid}</code>")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=OWNER_PANEL)
        return

    # ── هەموو بۆتەکان (OWNER) ─────────────────────────────────────────────────
    if text == "🤖 هەموو بۆتەکان":
        if user_id != OWNER_ID:
            await update.message.reply_text("❌ مافت نییە!")
            return
        all_bots = await db_get("managed_bots") or {}
        if not all_bots:
            await update.message.reply_text("📭 هیچ بۆتێک نییە.", reply_markup=OWNER_PANEL)
            return
        lines = [f"🤖 <b>هەموو بۆتەکان ({len(all_bots)}):</b>\n"]
        for bid, bdata in list(all_bots.items())[:30]:
            uname  = bdata.get("bot_username", "ناسناو")
            status = "🟢" if bdata.get("status") == "running" else "🔴"
            owner  = bdata.get("owner", "؟")
            lines.append(f"{status} @{uname} — خاوەن: <code>{owner}</code>")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=OWNER_PANEL)
        return

    # ── ناردنی پەیام بۆ هەموو (OWNER) ────────────────────────────────────────
    if text == "📨 ناردنی پەیام بۆ هەموو":
        if user_id != OWNER_ID:
            await update.message.reply_text("❌ مافت نییە!")
            return
        await db_put(f"users/{user_id}/state", "broadcast")
        kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
        await update.message.reply_text(
            "📨 <b>ناردنی پەیام بۆ هەموو بەکارهێنەران</b>\n\nپەیامەکەت بنووسە:",
            parse_mode="HTML", reply_markup=kb
        )
        return

    if state == "broadcast" and user_id == OWNER_ID:
        if text == "❌ هەڵوەشاندنەوە":
            await db_del(f"users/{user_id}/state")
            await update.message.reply_text("↩️ هەڵوەشاندرایەوە.", reply_markup=OWNER_PANEL)
            return
        all_users = await db_get("users") or {}
        sent = 0
        fail = 0
        status_msg = await update.message.reply_text(f"⏳ ناردن بۆ {len(all_users)} بەکارهێنەر...")
        async with httpx.AsyncClient(timeout=10) as client:
            for uid in all_users.keys():
                try:
                    r = await client.post(
                        f"https://api.telegram.org/bot{MASTER_TOKEN}/sendMessage",
                        json={"chat_id": int(uid), "text": text, "parse_mode": "HTML"}
                    )
                    if r.json().get("ok"): sent += 1
                    else: fail += 1
                except: fail += 1
                await asyncio.sleep(0.05)
        await db_del(f"users/{user_id}/state")
        await status_msg.edit_text(f"✅ ناردن تەواو بوو!\n📤 ناردرا: {sent}\n❌ هەڵە: {fail}", reply_markup=OWNER_PANEL)
        return

    # ── سڕینەوەی بۆت بە ID (OWNER) ────────────────────────────────────────────
    if text == "🗑 سڕینەوەی بۆت بە ID":
        if user_id != OWNER_ID:
            await update.message.reply_text("❌ مافت نییە!")
            return
        await db_put(f"users/{user_id}/state", "admin_delete_bot")
        kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
        await update.message.reply_text("🆔 ID ی بۆتەکە بنووسە (ئەو ژمارەیەی لە داتابەیسدایە):", reply_markup=kb)
        return

    if state == "admin_delete_bot" and user_id == OWNER_ID:
        if text == "❌ هەڵوەشاندنەوە":
            await db_del(f"users/{user_id}/state")
            await update.message.reply_text("↩️ هەڵوەشاندرایەوە.", reply_markup=OWNER_PANEL)
            return
        bot_data = await db_get(f"managed_bots/{text.strip()}")
        if not bot_data:
            await update.message.reply_text("❌ بۆتێک بەم ID ەیە نەدۆزرایەوە.", reply_markup=OWNER_PANEL)
        else:
            uname = bot_data.get("bot_username", "ناسناو")
            token = bot_data.get("token", "")
            if token:
                async with httpx.AsyncClient(timeout=10) as client:
                    try: await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
                    except: pass
            await db_del(f"managed_bots/{text.strip()}")
            await update.message.reply_text(f"🗑 بۆتی @{uname} سڕایەوە!", reply_markup=OWNER_PANEL)
        await db_del(f"users/{user_id}/state")
        return

    # ── وەرگرتن و چالاككردنی تۆکێن ────────────────────────────────────────────
    if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", text):
        cur_state = await db_get(f"users/{user_id}/state")
        if cur_state != "waiting_reaction_token":
            await update.message.reply_text(
                "⚠️ تکایە لەسەرەتاوە کلیک لە '➕ دروستکردنی بۆتی نوێ' بکە.",
                reply_markup=main_menu_kb(user_id)
            )
            return

        status_msg = await update.message.reply_text("⏳ خەریکی چالاككردنی بۆتەکەم، کەمێک چاوەڕێ بکە...")

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                # ١. پشکنینی تۆکێن
                res = await client.get(f"https://api.telegram.org/bot{text}/getMe")
                if res.status_code != 200 or not res.json().get("ok"):
                    await status_msg.edit_text("❌ تۆکێنەکە هەڵەیە یان کار ناکات.\nتکایە دووبارە پشکنیتەوە.")
                    return

                bot_info      = res.json()["result"]
                bot_id_str    = str(bot_info["id"])
                bot_username  = bot_info["username"]
                bot_first     = bot_info["first_name"]

                # پشکنین ئایا پێشتر تۆمارکراوە
                exists = await db_get(f"managed_bots/{bot_id_str}")
                if exists:
                    await status_msg.edit_text(
                        f"⚠️ بۆتی @{bot_username} پێشتر تۆمارکراوە!\n"
                        f"ئەگەر خاوەنی ئەمەیت، لە '📂 بۆتەکانم' دەتبینیتەوە."
                    )
                    return

                # ٢. بەستنەوەی وەبهووک
                safe_url    = (PROJECT_URL or "").rstrip('/')
                webhook_url = f"{safe_url}/api/bot/{text}"
                res2 = await client.post(
                    f"https://api.telegram.org/bot{text}/setWebhook",
                    json={"url": webhook_url, "allowed_updates": ["message", "channel_post", "callback_query"]}
                )
                if res2.status_code != 200 or not res2.json().get("ok"):
                    await status_msg.edit_text("❌ هەڵەیەک ڕوویدا لە بەستنەوەی وەبهووک.\nتکایە PROJECT_URL پشکنیتەوە.")
                    return

                # ٣. پاشەکەوتکردن لە داتابەیس
                await db_put(f"managed_bots/{bot_id_str}", {
                    "token": text,
                    "owner": user_id,
                    "bot_username": bot_username,
                    "bot_name": bot_first,
                    "status": "running",
                    "type": "reaction"
                })
                await db_del(f"users/{user_id}/state")

                msg = (
                    f"✅ <b>بۆتەکەت سەرکەوتووانە دروست کرا!</b>\n\n"
                    f"🤖 ناو: {html.escape(bot_first)}\n"
                    f"🔗 یوزەر: @{bot_username}\n"
                    f"🆔 ID: <code>{bot_id_str}</code>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 <b>ئێستا بۆتەکەت چالاکە!</b>\n"
                    f"زیادیکە بۆ گروپ یان کانالت و ئادمینی بکە\n"
                    f"بۆتەکە بۆ هەموو نامەیەک ئیموجی دەنێرێت ❤️\n"
                    f"━━━━━━━━━━━━━━━━━━━"
                )
                await status_msg.edit_text(msg, parse_mode="HTML")
                await update.message.reply_text(
                    "⬇️ ئێستا دەتوانیت لە '📂 بۆتەکانم' کۆنترۆڵیبکەیت:",
                    reply_markup=main_menu_kb(user_id)
                )

            except Exception as e:
                logger.error(f"Token activation error: {e}")
                await status_msg.edit_text(f"❌ هەڵەیەکی چاوەڕواننەکراو ڕوویدا:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")
        return

    # ── هەر شتێکی تر ─────────────────────────────────────────────────────────
    await update.message.reply_text(
        "تکایە لە کیبۆردی خوارەوە هەڵبژێرە 👇",
        reply_markup=main_menu_kb(user_id)
    )


# ══════════════════════════════════════════════════════════════════════════════
# ── ٢. بۆتی منداڵ (Child Bot Logic)
# ══════════════════════════════════════════════════════════════════════════════

async def process_child_update(token: str, body: dict):
    try:
        bot_id_str = token.split(":")[0]
        bot_data   = await db_get(f"managed_bots/{bot_id_str}")

        if not bot_data or bot_data.get("status") != "running":
            return

        bot_username = bot_data.get("bot_username", "UnknownBot")
        bot_name     = bot_data.get("bot_name", "Reaction Bot")

        # دۆزینەوەی پەیامەکە
        msg = body.get("message") or body.get("channel_post")
        if not msg:
            return

        chat_id    = msg["chat"]["id"]
        message_id = msg["message_id"]
        text       = msg.get("text", "")

        from_user = msg.get("from") or msg.get("sender_chat") or {}
        user_name = html.escape(from_user.get("first_name") or from_user.get("title") or "بەکارهێنەر")
        user_id   = from_user.get("id", chat_id)

        async with httpx.AsyncClient(timeout=10) as client:
            if text.startswith('/start'):
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📢 کانالی بەڕێوەبەر", "url": f"https://t.me/{CHANNEL_USER}"}],
                        [
                            {"text": "➕ زیادکردن بۆ گروپ", "url": f"https://t.me/{bot_username}?startgroup=new"},
                            {"text": "➕ زیادکردن بۆ کانال", "url": f"https://t.me/{bot_username}?startchannel=new"}
                        ],
                        [{"text": "👨‍💻 بەرنامەنووس", "url": f"tg://user?id={OWNER_ID}"}]
                    ]
                }

                caption = (
                    f"سڵاو، <a href='tg://user?id={user_id}'>{user_name}</a> 👋\n\n"
                    f"من بۆتی ڕیاکشنم 🍓 ناوم <b>{html.escape(bot_name)}</b>ە\n\n"
                    f"کارەکەم ئەوەیە کە بۆ هەموو نامەیەک ڕیاکشن بنێرم:\n"
                    f"{' '.join(EMOJIS)}\n\n"
                    f"دەتوانم لە گروپ، کانال و چاتی تایبەتدا کار بکەم 🌼\n"
                    f"تەنها زیادم بکە بۆ گروپ یان کانالەکەت و ئادمینم بکە ☘️\n"
                    f"ئینجا بۆ هەموو نامەیەک ئیموجی دەنێرم 💗"
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
                # ڕیاکشن ئیموجی بۆ هەموو نامەیەک
                emoji   = random.choice(EMOJIS)
                payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reaction": [{"type": "emoji", "emoji": emoji}],
                    "is_big": False
                }
                await client.post(f"https://api.telegram.org/bot{token}/setMessageReaction", json=payload)

    except Exception as e:
        logger.error(f"Child Bot Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ── ٣. ڕاوتەرەکان (Routes)
# ══════════════════════════════════════════════════════════════════════════════

master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_commands))


@app.post("/api/main")
async def master_route(request: Request):
    if not master_app.running:
        await master_app.initialize()
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
    return {
        "status": "active",
        "message": "بۆتی سەرەکی چالاکە! 🚀",
        "keep_alive": "enabled ✅"
    }
