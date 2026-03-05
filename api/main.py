import os, logging, httpx, asyncio, random, html, re
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

# ══════════════════════════════════════════════════════════════════════════════
# ── ڕێکخستنەکان
# ══════════════════════════════════════════════════════════════════════════════
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
app    = FastAPI()

# ══════════════════════════════════════════════════════════════════════════════
# ── داتابەیس
# ══════════════════════════════════════════════════════════════════════════════
def fb_url(path): return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def db_get(path):
    if not DB_URL: return None
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(fb_url(path))
            return r.json() if r.status_code == 200 else None
        except: return None

async def db_put(path, data):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as c:
        try: await c.put(fb_url(path), json=data)
        except: pass

async def db_patch(path, data):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as c:
        try: await c.patch(fb_url(path), json=data)
        except: pass

async def db_del(path):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as c:
        try: await c.delete(fb_url(path))
        except: pass

# ══════════════════════════════════════════════════════════════════════════════
# ── KEEP-ALIVE
# ══════════════════════════════════════════════════════════════════════════════
async def keep_alive_loop():
    await asyncio.sleep(30)
    while True:
        try:
            safe = (PROJECT_URL or "").rstrip('/')
            if safe:
                async with httpx.AsyncClient(timeout=15) as c:
                    await c.get(f"{safe}/ping")
                    logger.info("Keep-alive OK")
        except Exception as e:
            logger.warning(f"Keep-alive err: {e}")
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive_loop())

@app.get("/ping")
async def ping(): return {"ok": True}

# ══════════════════════════════════════════════════════════════════════════════
# ── کیبۆردەکان
# ══════════════════════════════════════════════════════════════════════════════

def kb_main(uid: int) -> ReplyKeyboardMarkup:
    if uid == OWNER_ID:
        return ReplyKeyboardMarkup([
            [KeyboardButton("➕ دروستکردنی بۆتی نوێ"),  KeyboardButton("📂 بۆتەکانم")],
            [KeyboardButton("👑 پانێلی سەرەکی"),         KeyboardButton("📊 ئامارەکان")],
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ دروستکردنی بۆتی نوێ"), KeyboardButton("📂 بۆتەکانم")],
    ], resize_keyboard=True)


def kb_control(uid: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton("▶️ دەستپێکردن"),      KeyboardButton("⏸ وەستاندن")],
        [KeyboardButton("🔄 نوێکردنەوە"),       KeyboardButton("📋 زانیاری بۆت")],
        [KeyboardButton("✏️ گۆڕینی بەخێرهاتن"), KeyboardButton("📨 پەیام بۆ بەکارهێنەران")],
        [KeyboardButton("🗑 سڕینەوەی بۆت"),     KeyboardButton("🔙 گەڕانەوە بۆ لیست")],
    ]
    if uid == OWNER_ID:
        rows.insert(3, [KeyboardButton("🔑 گۆڕینی تۆکێن"), KeyboardButton("🔗 نوێکردنەوەی وەبهووک")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


KB_OWNER = ReplyKeyboardMarkup([
    [KeyboardButton("👥 هەموو بەکارهێنەرەکان"), KeyboardButton("🤖 هەموو بۆتەکان")],
    [KeyboardButton("📨 بڵاوکردنەوە بۆ هەموو"),  KeyboardButton("🗑 سڕینەوەی بۆت بە ID")],
    [KeyboardButton("🚫 بلۆک کردنی بەکارهێنەر"), KeyboardButton("✅ لابردنی بلۆک")],
    [KeyboardButton("📊 ئامارەکان"),              KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")],
], resize_keyboard=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── یارمەتیدەرەکان
# ══════════════════════════════════════════════════════════════════════════════
async def is_blocked(uid: int) -> bool:
    v = await db_get(f"blocked/{uid}")
    return v is True

async def send_tg(token: str, method: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=12) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        return r.json()

# ══════════════════════════════════════════════════════════════════════════════
# ── /start
# ══════════════════════════════════════════════════════════════════════════════
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = html.escape(update.effective_user.first_name or "بەکارهێنەر")

    if await is_blocked(uid):
        await update.message.reply_text("🚫 دەستت لە بۆتەکە گرتراوە.")
        return

    await db_del(f"users/{uid}/state")
    await db_patch(f"users/{uid}", {
        "name":     update.effective_user.first_name or "",
        "username": update.effective_user.username   or "",
        "active":   True,
    })

    if uid == OWNER_ID:
        txt = (
            f"👑 <b>بەخێربێیت خاوەنی سیستەم، {name}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 دروستکردن و کۆنترۆڵی بۆت\n"
            "👑 پانێلی سەرەکی — بەڕێوەبردنی تەواو\n"
            "📊 ئامارەکانی سیستەم\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 هەڵبژاردنێک بکە:"
        )
    else:
        txt = (
            f"👋 <b>بەخێربێیت، {name}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 دروستکردنی بۆتی تایبەتی خۆت\n"
            "⚙️ کۆنترۆڵی تەواوی بۆتەکەت\n"
            "📨 ناردنی پەیام بۆ بەکارهێنەرانی بۆتەکەت\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 لە کیبۆردی خوارەوە هەڵبژێرە:"
        )

    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main(uid))

# ══════════════════════════════════════════════════════════════════════════════
# ── handler ی سەرەکی
# ══════════════════════════════════════════════════════════════════════════════
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt   = update.message.text.strip()
    uid   = update.effective_user.id
    state = await db_get(f"users/{uid}/state") or ""

    if await is_blocked(uid):
        await update.message.reply_text("🚫 دەستت لە بۆتەکە گرتراوە.")
        return

    # ── ناڤیگەیشن ──────────────────────────────────────────────────────────
    if txt == "🔙 گەڕانەوە بۆ سەرەتا":
        await db_del(f"users/{uid}/state")
        await master_start(update, ctx)
        return

    if txt == "🔙 گەڕانەوە بۆ لیست":
        await db_del(f"users/{uid}/state")
        await show_bot_list(update, uid)
        return

    # ── دروستکردنی بۆتی نوێ ───────────────────────────────────────────────
    if txt == "➕ دروستکردنی بۆتی نوێ":
        kb = ReplyKeyboardMarkup([
            [KeyboardButton("🍓 بۆتی ڕیاکشن")],
            [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")],
        ], resize_keyboard=True)
        await update.message.reply_text(
            "🤖 <b>جۆری بۆت هەڵبژێرە:</b>\n\n"
            "🍓 <b>بۆتی ڕیاکشن</b> — بۆ هەموو نامەیەک ئیموجی دەنێرێت ❤️",
            parse_mode="HTML", reply_markup=kb,
        )
        return

    if txt == "🍓 بۆتی ڕیاکشن":
        await db_put(f"users/{uid}/state", "await_token")
        kb = ReplyKeyboardMarkup([[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text(
            "🍓 <b>دروستکردنی بۆتی ڕیاکشن</b>\n\n"
            "📋 <b>مامەڵەکە:</b>\n"
            "١. بچۆ بۆ @BotFather لە تێلیگرام\n"
            "٢. بنووسە /newbot\n"
            "٣. ناوی بۆتەکەت دابنێ\n"
            "٤. تۆکێنەکەی کۆپی بکە و لێرە بینێرە\n\n"
            "⬇️ <b>تۆکێنەکەت لێرە بینێرە:</b>",
            parse_mode="HTML", reply_markup=kb,
        )
        return

    # ── لیستی بۆتەکانم ───────────────────────────────────────────────────
    if txt == "📂 بۆتەکانم":
        await show_bot_list(update, uid)
        return

    # ── هەڵبژاردنی بۆت ───────────────────────────────────────────────────
    if re.match(r"^[🟢🔴⚪] @\S+$", txt):
        uname = re.sub(r"^[🟢🔴⚪] @", "", txt).strip()
        all_b = await db_get("managed_bots") or {}
        bid   = next((k for k, v in all_b.items()
                      if v.get("owner") == uid and v.get("bot_username") == uname), None)
        if not bid:
            await update.message.reply_text("❌ بۆتەکە نەدۆزرایەوە!", reply_markup=kb_main(uid))
            return
        await db_put(f"users/{uid}/selected_bot", bid)
        await show_bot_control(update, uid, bid, all_b[bid])
        return

    # ── دوگمەکانی کۆنترۆڵ ────────────────────────────────────────────────
    CTRL = {
        "▶️ دەستپێکردن", "⏸ وەستاندن", "🔄 نوێکردنەوە",
        "📋 زانیاری بۆت", "✏️ گۆڕینی بەخێرهاتن",
        "📨 پەیام بۆ بەکارهێنەران", "🗑 سڕینەوەی بۆت",
        "🔑 گۆڕینی تۆکێن", "🔗 نوێکردنەوەی وەبهووک",
    }
    if txt in CTRL:
        await handle_control(update, uid, txt)
        return

    # ── ئامار ─────────────────────────────────────────────────────────────
    if txt == "📊 ئامارەکان":
        await show_stats(update, uid)
        return

    # ── پانێلی سەرەکی ────────────────────────────────────────────────────
    if txt == "👑 پانێلی سەرەکی":
        if uid != OWNER_ID:
            await update.message.reply_text("❌ مافت نییە!", reply_markup=kb_main(uid))
            return
        all_b = await db_get("managed_bots") or {}
        all_u = await db_get("users")         or {}
        run   = sum(1 for v in all_b.values() if v.get("status") == "running")
        msg   = (
            "👑 <b>پانێلی سەرەکی</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👥 بەکارهێنەران: <b>{len(all_u)}</b>\n"
            f"🤖 بۆتەکان: <b>{len(all_b)}</b>  (🟢 {run}  🔴 {len(all_b)-run})\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_OWNER)
        return

    # ── دوگمەکانی پانێلی سەرەکی ──────────────────────────────────────────
    if uid == OWNER_ID:
        if txt == "👥 هەموو بەکارهێنەرەکان":
            await owner_list_users(update)
            return
        if txt == "🤖 هەموو بۆتەکان":
            await owner_list_bots(update)
            return
        if txt == "📨 بڵاوکردنەوە بۆ هەموو":
            await db_put(f"users/{uid}/state", "broadcast")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text(
                "📨 <b>بڵاوکردنەوە بۆ هەموو بەکارهێنەران</b>\n\nپەیامەکەت بنووسە:",
                parse_mode="HTML", reply_markup=kb,
            )
            return
        if txt == "🗑 سڕینەوەی بۆت بە ID":
            await db_put(f"users/{uid}/state", "owner_del_bot")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بۆتەکە بنووسە:", reply_markup=kb)
            return
        if txt == "🚫 بلۆک کردنی بەکارهێنەر":
            await db_put(f"users/{uid}/state", "owner_block")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return
        if txt == "✅ لابردنی بلۆک":
            await db_put(f"users/{uid}/state", "owner_unblock")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return

    # ── دۆخەکانی چاوەڕوانی ────────────────────────────────────────────────
    await handle_states(update, uid, txt, state)


# ══════════════════════════════════════════════════════════════════════════════
# ── نیشاندانی لیست و کۆنترۆڵ
# ══════════════════════════════════════════════════════════════════════════════
async def show_bot_list(update: Update, uid: int):
    all_b = await db_get("managed_bots") or {}
    mine  = {k: v for k, v in all_b.items() if v.get("owner") == uid}
    if not mine:
        await update.message.reply_text(
            "📭 <b>هیچ بۆتێکت دروست نەکردووە!</b>\n\nکلیک لە '➕ دروستکردنی بۆتی نوێ' بکە.",
            parse_mode="HTML", reply_markup=kb_main(uid),
        )
        return
    rows = []
    for _, info in mine.items():
        st = "🟢" if info.get("status") == "running" else "🔴"
        rows.append([KeyboardButton(f"{st} @{info.get('bot_username','Bot')}")])
    rows.append([KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")])
    await update.message.reply_text(
        f"📂 <b>بۆتەکانت ({len(mine)} بۆت):</b>\n🟢 کاردەکات  |  🔴 ڕاگیراوە",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True),
    )


async def show_bot_control(update: Update, uid: int, bid: str, info: dict):
    st   = "🟢 کاردەکات" if info.get("status") == "running" else "🔴 ڕاگیراوە"
    name = html.escape(info.get("bot_name", "ناسناو"))
    un   = info.get("bot_username", "ناسناو")
    msg  = (
        "⚙️ <b>پانێلی کۆنترۆڵ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 ناو: {name}\n"
        f"🔗 یوزەر: @{un}\n"
        f"📊 دۆخ: {st}\n"
        f"🆔 ID: <code>{bid}</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "لە کیبۆردی خوارەوە کۆنترۆڵی بکە:"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb_control(uid))


async def show_stats(update: Update, uid: int):
    all_b = await db_get("managed_bots") or {}
    all_u = await db_get("users")         or {}
    mine  = {k: v for k, v in all_b.items() if v.get("owner") == uid}
    run_m = sum(1 for v in mine.values() if v.get("status") == "running")
    if uid == OWNER_ID:
        run_a = sum(1 for v in all_b.values() if v.get("status") == "running")
        txt = (
            "📊 <b>ئامارەکانی سیستەم</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👥 هەموو بەکارهێنەران: <b>{len(all_u)}</b>\n"
            f"🤖 هەموو بۆتەکان: <b>{len(all_b)}</b>\n"
            f"🟢 چالاک: <b>{run_a}</b>  🔴 ڕاگیراو: <b>{len(all_b)-run_a}</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"📁 بۆتەکانی خۆت: <b>{len(mine)}</b>  (🟢 {run_m})"
        )
    else:
        txt = (
            "📊 <b>ئامارەکانت</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 بۆتی دروستکردوو: <b>{len(mine)}</b>\n"
            f"🟢 چالاک: <b>{run_m}</b>  🔴 ڕاگیراو: <b>{len(mine)-run_m}</b>"
        )
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main(uid))


# ══════════════════════════════════════════════════════════════════════════════
# ── کۆنترۆڵی بۆت
# ══════════════════════════════════════════════════════════════════════════════
async def handle_control(update: Update, uid: int, txt: str):
    bid = await db_get(f"users/{uid}/selected_bot")
    if not bid:
        await update.message.reply_text("⚠️ تکایە سەرەتا بۆتێک هەڵبژێرە.", reply_markup=kb_main(uid))
        return
    info = await db_get(f"managed_bots/{bid}")
    if not info:
        await db_del(f"users/{uid}/selected_bot")
        await update.message.reply_text("❌ بۆتەکە سڕاوەتەوە.", reply_markup=kb_main(uid))
        return

    un    = info.get("bot_username", "Bot")
    token = info.get("token", "")

    if txt == "▶️ دەستپێکردن":
        info["status"] = "running"
        await db_put(f"managed_bots/{bid}", info)
        await update.message.reply_text(f"✅ بۆتی @{un} دەستی پێکرد 🟢", reply_markup=kb_control(uid))

    elif txt == "⏸ وەستاندن":
        info["status"] = "stopped"
        await db_put(f"managed_bots/{bid}", info)
        await update.message.reply_text(f"🛑 بۆتی @{un} وەستاندرا 🔴", reply_markup=kb_control(uid))

    elif txt == "🔄 نوێکردنەوە":
        info["status"] = "running"
        await db_put(f"managed_bots/{bid}", info)
        await update.message.reply_text(f"🔄 بۆتی @{un} نوێکرایەوە ✅", reply_markup=kb_control(uid))

    elif txt == "📋 زانیاری بۆت":
        await show_bot_control(update, uid, bid, info)

    elif txt == "✏️ گۆڕینی بەخێرهاتن":
        await db_put(f"users/{uid}/state", f"edit_welcome:{bid}")
        cur = info.get("welcome_msg", "")
        kb  = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
        await update.message.reply_text(
            "✏️ <b>گۆڕینی نامەی بەخێرهاتن</b>\n\n"
            f"📝 نامەی ئێستا:\n<code>{html.escape(cur) if cur else '(بەتاڵ — بەکار دەهێنرێت بەشی پێش‌ڕێکخراو)'}</code>\n\n"
            "نامەی نوێت بنووسە (HTML پشتگیری دەکات):\n"
            "💡 <code>{name}</code> بەکاربهێنە بۆ ناوی بەکارهێنەر",
            parse_mode="HTML", reply_markup=kb,
        )

    elif txt == "📨 پەیام بۆ بەکارهێنەران":
        bot_users = await db_get(f"bot_users/{bid}") or {}
        if not bot_users:
            await update.message.reply_text(
                "📭 هیچ بەکارهێنەرێک بۆتەکەت بەکار نەهێناوە تا ئێستا.",
                reply_markup=kb_control(uid),
            )
            return
        await db_put(f"users/{uid}/state", f"bot_broadcast:{bid}")
        kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
        await update.message.reply_text(
            f"📨 <b>ناردنی پەیام بۆ بەکارهێنەرانی @{un}</b>\n\n"
            f"👥 ژمارەی بەکارهێنەران: <b>{len(bot_users)}</b>\n\n"
            "پەیامەکەت بنووسە:",
            parse_mode="HTML", reply_markup=kb,
        )

    elif txt == "🔗 نوێکردنەوەی وەبهووک" and uid == OWNER_ID:
        if token:
            safe = (PROJECT_URL or "").rstrip('/')
            r    = await send_tg(token, "setWebhook", {
                "url": f"{safe}/api/bot/{token}",
                "allowed_updates": ["message", "channel_post"],
            })
            if r.get("ok"):
                await update.message.reply_text(f"✅ وەبهووکی @{un} نوێکرایەوە!", reply_markup=kb_control(uid))
            else:
                await update.message.reply_text(f"❌ هەڵە: {r.get('description','')}", reply_markup=kb_control(uid))
        else:
            await update.message.reply_text("❌ تۆکێن نەدۆزرایەوە.", reply_markup=kb_control(uid))

    elif txt == "🔑 گۆڕینی تۆکێن" and uid == OWNER_ID:
        await db_put(f"users/{uid}/state", f"change_token:{bid}")
        kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
        await update.message.reply_text("🔑 تۆکێنی نوێ بنووسە:", reply_markup=kb)

    elif txt == "🗑 سڕینەوەی بۆت":
        await db_put(f"users/{uid}/state", f"confirm_del:{bid}")
        kb = ReplyKeyboardMarkup([
            [KeyboardButton(f"✅ بەڵێ، @{un} بسڕەوە")],
            [KeyboardButton("❌ نەخێر، دەرچوون")],
        ], resize_keyboard=True)
        await update.message.reply_text(
            f"⚠️ <b>دڵنیایت؟</b>\n\nبۆتی @{un} بە تەواوی دەسڕیتەوە!",
            parse_mode="HTML", reply_markup=kb,
        )


# ══════════════════════════════════════════════════════════════════════════════
# ── دۆخەکانی چاوەڕوانی (State Machine)
# ══════════════════════════════════════════════════════════════════════════════
async def handle_states(update: Update, uid: int, txt: str, state: str):

    if txt == "❌ هەڵوەشاندنەوە":
        await db_del(f"users/{uid}/state")
        await update.message.reply_text("↩️ هەڵوەشاندرایەوە.", reply_markup=kb_main(uid))
        return

    # ── چاوەڕوانی تۆکێن ───────────────────────────────────────────────────
    if state == "await_token":
        if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", txt):
            await activate_token(update, uid, txt)
        else:
            await update.message.reply_text(
                "⚠️ تۆکێنەکە دروست نییە.\nتۆکێنی دروست وەک ئەمە دێت:\n<code>123456789:ABCxyz...</code>",
                parse_mode="HTML",
            )
        return

    # ── دڵنیاکردنەوەی سڕینەوە ─────────────────────────────────────────────
    if state.startswith("confirm_del:"):
        bid = state.split(":", 1)[1]
        if txt.startswith("✅ بەڵێ،"):
            await do_delete_bot(update, uid, bid)
        else:
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("↩️ گەڕایتەوە.", reply_markup=kb_control(uid))
        return

    # ── گۆڕینی نامەی بەخێرهاتن ───────────────────────────────────────────
    if state.startswith("edit_welcome:"):
        bid  = state.split(":", 1)[1]
        info = await db_get(f"managed_bots/{bid}")
        if not info:
            await update.message.reply_text("❌ بۆتەکە نەدۆزرایەوە.", reply_markup=kb_main(uid))
            await db_del(f"users/{uid}/state")
            return
        info["welcome_msg"] = txt
        await db_put(f"managed_bots/{bid}", info)
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(
            "✅ <b>نامەی بەخێرهاتن نوێکرا!</b>",
            parse_mode="HTML", reply_markup=kb_control(uid),
        )
        return

    # ── بڵاوکردنەوەی بۆت ─────────────────────────────────────────────────
    if state.startswith("bot_broadcast:"):
        bid       = state.split(":", 1)[1]
        info      = await db_get(f"managed_bots/{bid}") or {}
        token     = info.get("token", "")
        bot_users = await db_get(f"bot_users/{bid}") or {}
        sm        = await update.message.reply_text(f"⏳ ناردن بۆ {len(bot_users)} بەکارهێنەر...")
        sent = fail = 0
        for cid in bot_users.keys():
            try:
                r = await send_tg(token, "sendMessage", {"chat_id": int(cid), "text": txt, "parse_mode": "HTML"})
                if r.get("ok"): sent += 1
                else:           fail += 1
            except: fail += 1
            await asyncio.sleep(0.05)
        await db_del(f"users/{uid}/state")
        await sm.edit_text(f"✅ <b>ناردن تەواو!</b>\n📤 ناردرا: {sent}  ❌ هەڵە: {fail}", parse_mode="HTML")
        await update.message.reply_text(".", reply_markup=kb_control(uid))
        return

    # ── گۆڕینی تۆکێن (Owner) ─────────────────────────────────────────────
    if state.startswith("change_token:") and uid == OWNER_ID:
        bid = state.split(":", 1)[1]
        if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", txt):
            res = await send_tg(txt, "getMe", {})
            if not res.get("ok"):
                await update.message.reply_text("❌ تۆکێنەکە هەڵەیە.", reply_markup=kb_control(uid))
                await db_del(f"users/{uid}/state")
                return
            info = await db_get(f"managed_bots/{bid}") or {}
            info["token"]        = txt
            info["bot_username"] = res["result"]["username"]
            info["bot_name"]     = res["result"]["first_name"]
            await db_put(f"managed_bots/{bid}", info)
            safe = (PROJECT_URL or "").rstrip('/')
            await send_tg(txt, "setWebhook", {"url": f"{safe}/api/bot/{txt}", "allowed_updates": ["message","channel_post"]})
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ تۆکێن گۆڕدرا و وەبهووکیش نوێکرایەوە!", reply_markup=kb_control(uid))
        else:
            await update.message.reply_text("⚠️ تۆکێنەکە دروست نییە.")
        return

    # ── بڵاوکردنەوەی گشتی (Owner) ────────────────────────────────────────
    if state == "broadcast" and uid == OWNER_ID:
        all_u = await db_get("users") or {}
        sm    = await update.message.reply_text(f"⏳ ناردن بۆ {len(all_u)} بەکارهێنەر...")
        sent = fail = 0
        for u_id in all_u.keys():
            try:
                r = await send_tg(MASTER_TOKEN, "sendMessage", {"chat_id": int(u_id), "text": txt, "parse_mode": "HTML"})
                if r.get("ok"): sent += 1
                else:           fail += 1
            except: fail += 1
            await asyncio.sleep(0.05)
        await db_del(f"users/{uid}/state")
        await sm.edit_text(f"✅ <b>ناردن تەواو!</b>\n📤 ناردرا: {sent}  ❌ هەڵە: {fail}", parse_mode="HTML")
        await update.message.reply_text(".", reply_markup=KB_OWNER)
        return

    # ── سڕینەوەی بۆت بە ID (Owner) ───────────────────────────────────────
    if state == "owner_del_bot" and uid == OWNER_ID:
        info = await db_get(f"managed_bots/{txt.strip()}")
        if not info:
            await update.message.reply_text("❌ بۆتێک بەم ID ەیە نەدۆزرایەوە.", reply_markup=KB_OWNER)
        else:
            await do_delete_bot(update, uid, txt.strip(), owner_panel=True)
        await db_del(f"users/{uid}/state")
        return

    # ── بلۆک (Owner) ─────────────────────────────────────────────────────
    if state == "owner_block" and uid == OWNER_ID:
        try:
            target = int(txt.strip())
            await db_put(f"blocked/{target}", True)
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"🚫 بەکارهێنەری <code>{target}</code> بلۆک کرا.", parse_mode="HTML", reply_markup=KB_OWNER)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    # ── لابردنی بلۆک (Owner) ─────────────────────────────────────────────
    if state == "owner_unblock" and uid == OWNER_ID:
        try:
            target = int(txt.strip())
            await db_del(f"blocked/{target}")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"✅ بلۆکی <code>{target}</code> لابرا.", parse_mode="HTML", reply_markup=KB_OWNER)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    # ── تۆکێنی ڕاستەوخۆ (بەبێ دۆخ) ─────────────────────────────────────
    if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", txt):
        await update.message.reply_text(
            "⚠️ تکایە لەسەرەتاوە کلیک لە '➕ دروستکردنی بۆتی نوێ' بکە.",
            reply_markup=kb_main(uid),
        )
        return

    await update.message.reply_text("تکایە لە کیبۆردی خوارەوە هەڵبژێرە 👇", reply_markup=kb_main(uid))


# ══════════════════════════════════════════════════════════════════════════════
# ── چالاككردنی تۆکێن
# ══════════════════════════════════════════════════════════════════════════════
async def activate_token(update: Update, uid: int, token: str):
    sm = await update.message.reply_text("⏳ خەریکی پشکنین و چالاككردنم...")
    try:
        res = await send_tg(token, "getMe", {})
        if not res.get("ok"):
            await sm.edit_text("❌ تۆکێنەکە هەڵەیە یان کار ناکات.")
            return

        bi  = res["result"]
        bid = str(bi["id"])
        bun = bi["username"]
        bnm = bi["first_name"]

        exists = await db_get(f"managed_bots/{bid}")
        if exists:
            await sm.edit_text(f"⚠️ بۆتی @{bun} پێشتر تۆمارکراوە!")
            return

        safe = (PROJECT_URL or "").rstrip('/')
        wh   = await send_tg(token, "setWebhook", {
            "url": f"{safe}/api/bot/{token}",
            "allowed_updates": ["message", "channel_post"],
        })
        if not wh.get("ok"):
            await sm.edit_text("❌ هەڵەیەک ڕوویدا لە بەستنەوەی وەبهووک.")
            return

        await db_put(f"managed_bots/{bid}", {
            "token":        token,
            "owner":        uid,
            "bot_username": bun,
            "bot_name":     bnm,
            "status":       "running",
            "type":         "reaction",
            "welcome_msg":  "",
        })
        await db_del(f"users/{uid}/state")

        await sm.edit_text(
            f"✅ <b>بۆتەکەت سەرکەوتووانە دروست کرا!</b>\n\n"
            f"🤖 ناو: {html.escape(bnm)}\n"
            f"🔗 یوزەر: @{bun}\n"
            f"🆔 ID: <code>{bid}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📌 بۆتەکەت ئێستا چالاکە!\n"
            "زیادی بکە بۆ گروپ/کانالت و ئادمینی بکە ✅",
            parse_mode="HTML",
        )
        await update.message.reply_text(
            "📂 لە 'بۆتەکانم' کۆنترۆڵی بکە:",
            reply_markup=kb_main(uid),
        )
    except Exception as e:
        logger.error(f"activate_token: {e}")
        await sm.edit_text(f"❌ هەڵەیەکی چاوەڕواننەکراو:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# ── سڕینەوەی بۆت
# ══════════════════════════════════════════════════════════════════════════════
async def do_delete_bot(update: Update, uid: int, bid: str, owner_panel: bool = False):
    info  = await db_get(f"managed_bots/{bid}") or {}
    un    = info.get("bot_username", "ناسناو")
    token = info.get("token", "")
    if token:
        try: await send_tg(token, "deleteWebhook", {})
        except: pass
    await db_del(f"managed_bots/{bid}")
    await db_del(f"users/{uid}/selected_bot")
    await db_del(f"users/{uid}/state")
    kb = KB_OWNER if owner_panel else kb_main(uid)
    await update.message.reply_text(
        f"🗑 <b>بۆتی @{un} بە تەواوی سڕایەوە!</b>",
        parse_mode="HTML", reply_markup=kb,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ── Owner — لیستی بەکارهێنەران و بۆتەکان
# ══════════════════════════════════════════════════════════════════════════════
async def owner_list_users(update: Update):
    all_u = await db_get("users") or {}
    if not all_u:
        await update.message.reply_text("📭 هیچ بەکارهێنەرێک نییە.", reply_markup=KB_OWNER)
        return
    lines = [f"👥 <b>بەکارهێنەران ({len(all_u)}):</b>\n"]
    for u_id, ud in list(all_u.items())[:40]:
        name = html.escape(ud.get("name", "ناسناو"))
        un   = f"@{ud['username']}" if ud.get("username") else "—"
        lines.append(f"• <a href='tg://user?id={u_id}'>{name}</a> {un}  <code>{u_id}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_OWNER)


async def owner_list_bots(update: Update):
    all_b = await db_get("managed_bots") or {}
    if not all_b:
        await update.message.reply_text("📭 هیچ بۆتێک نییە.", reply_markup=KB_OWNER)
        return
    lines = [f"🤖 <b>هەموو بۆتەکان ({len(all_b)}):</b>\n"]
    for bid, bd in list(all_b.items())[:40]:
        st  = "🟢" if bd.get("status") == "running" else "🔴"
        own = bd.get("owner", "؟")
        lines.append(f"{st} @{bd.get('bot_username','—')}  خاوەن: <code>{own}</code>  ID: <code>{bid}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_OWNER)


# ══════════════════════════════════════════════════════════════════════════════
# ── بۆتی منداڵ (Child Bot)
# ══════════════════════════════════════════════════════════════════════════════
async def process_child_update(token: str, body: dict):
    try:
        bid  = token.split(":")[0]
        info = await db_get(f"managed_bots/{bid}")
        if not info or info.get("status") != "running":
            return

        bun  = info.get("bot_username", "UnknownBot")
        bnm  = info.get("bot_name",     "Reaction Bot")
        wlcm = info.get("welcome_msg",  "")

        msg = body.get("message") or body.get("channel_post")
        if not msg: return

        chat_id    = msg["chat"]["id"]
        message_id = msg["message_id"]
        txt        = msg.get("text", "")

        from_user = msg.get("from") or msg.get("sender_chat") or {}
        user_name = html.escape(from_user.get("first_name") or from_user.get("title") or "بەکارهێنەر")
        user_id   = from_user.get("id", chat_id)

        # تۆمارکردنی بەکارهێنەر بۆ bot_users
        if from_user.get("id"):
            await db_patch(f"bot_users/{bid}/{user_id}", {
                "name":    from_user.get("first_name", ""),
                "chat_id": chat_id,
            })

        async with httpx.AsyncClient(timeout=10) as c:
            if txt.startswith("/start"):
                if wlcm:
                    caption = wlcm.replace("{name}", user_name)
                else:
                    caption = (
                        f"سڵاو، <a href='tg://user?id={user_id}'>{user_name}</a> 👋\n\n"
                        f"من بۆتی ڕیاکشنم 🍓 ناوم <b>{html.escape(bnm)}</b>ە\n\n"
                        f"کارەکەم ئەوەیە کە بۆ هەموو نامەیەک ڕیاکشن بنێرم:\n"
                        f"{' '.join(EMOJIS)}\n\n"
                        "دەتوانم لە گروپ، کانال و چاتی تایبەتدا کار بکەم 🌼\n"
                        "تەنها زیادم بکە بۆ گروپ یان کانالەکەت و ئادمینم بکە ☘️\n"
                        "ئینجا بۆ هەموو نامەیەک ئیموجی دەنێرم 💗"
                    )

                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📢 کانالی بەڕێوەبەر", "url": f"https://t.me/{CHANNEL_USER}"}],
                        [
                            {"text": "➕ زیادکردن بۆ گروپ",  "url": f"https://t.me/{bun}?startgroup=new"},
                            {"text": "➕ زیادکردن بۆ کانال", "url": f"https://t.me/{bun}?startchannel=new"},
                        ],
                        [{"text": "👨‍💻 بەرنامەنووس", "url": f"tg://user?id={OWNER_ID}"}],
                    ]
                }
                await c.post(f"https://api.telegram.org/bot{token}/sendPhoto", json={
                    "chat_id":             chat_id,
                    "photo":               PHOTO_URL,
                    "caption":             caption,
                    "parse_mode":          "HTML",
                    "reply_markup":        keyboard,
                    "reply_to_message_id": message_id,
                })
            else:
                emoji = random.choice(EMOJIS)
                await c.post(f"https://api.telegram.org/bot{token}/setMessageReaction", json={
                    "chat_id":    chat_id,
                    "message_id": message_id,
                    "reaction":   [{"type": "emoji", "emoji": emoji}],
                    "is_big":     False,
                })
    except Exception as e:
        logger.error(f"Child: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ── ڕاوتەرەکان
# ══════════════════════════════════════════════════════════════════════════════
master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


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
    return {"status": "active", "message": "بۆتی سەرەکی چالاکە 🚀", "keep_alive": "✅"}
