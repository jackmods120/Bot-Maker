import os, logging, httpx, asyncio, random, html, re, json
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ══════════════════════════════════════════════════════════════════════════════
# ── ڕێکخستنەکان
# ══════════════════════════════════════════════════════════════════════════════
MASTER_TOKEN = os.getenv("BOT_TOKEN")
PROJECT_URL  = os.getenv("PROJECT_URL")
DB_URL       = os.getenv("DB_URL")
DB_SECRET    = os.getenv("DB_SECRET")

OWNER_ID     = 5977475208
CHANNEL_USER = "j4ck_721s"
EMOJIS       = ["❤️","🔥","🎉","👏","🤩","💯","😍","🫶","⚡","🌟"]
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
                    logger.info("✅ Keep-alive")
        except Exception as e:
            logger.warning(f"Keep-alive: {e}")
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive_loop())
    logger.info("🚀 سێرڤەر دەستی پێکرد")

@app.get("/ping")
async def ping(): return {"ok": True, "status": "alive"}

# ══════════════════════════════════════════════════════════════════════════════
# ── یارمەتیدەر
# ══════════════════════════════════════════════════════════════════════════════
async def send_tg(token: str, method: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=12) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        return r.json()

async def is_blocked(uid: int) -> bool:
    return await db_get(f"blocked/{uid}") is True

async def is_vip(uid: int) -> bool:
    data = await db_get(f"vip/{uid}")
    if not data: return False
    exp = data.get("expires", "")
    if exp == "lifetime": return True
    try: return datetime.strptime(exp, "%Y-%m-%d") >= datetime.now()
    except: return False

async def is_admin(uid: int) -> bool:
    """پشکنینی ئەیا بەکارهێنەر ئەدمینی سیستەمە"""
    if uid == OWNER_ID: return True
    admins = await db_get("admins") or {}
    return str(uid) in admins

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

# ══════════════════════════════════════════════════════════════════════════════
# ── پشکنینی جۆینی ناچاری کەناڵ
# ══════════════════════════════════════════════════════════════════════════════
async def check_force_join(uid: int) -> tuple[bool, list]:
    """پشکنین ئەیا بەکارهێنەر ئەندامی هەموو کانالە داواکراوەکانە"""
    fj = await db_get("system/force_join")
    if not fj: return True, []
    req_chs = await db_get("system/req_channels") or {}
    if not req_chs: return True, []
    not_joined = []
    for ch in req_chs:
        try:
            res = await send_tg(MASTER_TOKEN, "getChatMember", {"chat_id": f"@{ch}", "user_id": uid})
            status = res.get("result", {}).get("status", "left")
            if status not in ("member", "administrator", "creator"):
                not_joined.append(ch)
        except:
            not_joined.append(ch)
    return len(not_joined) == 0, not_joined

async def send_force_join_msg(update: Update, not_joined: list):
    """ناردنی پەیامی داوای جۆین"""
    lines = ["‼️ <b>تکایە سەرەتا ئەندامی کانالەکانمان بە:</b>\n"]
    keyboard_rows = []
    for ch in not_joined:
        lines.append(f"📢 @{ch}")
        keyboard_rows.append([{"text": f"➕ ئەندامبوون لە @{ch}", "url": f"https://t.me/{ch}"}])
    keyboard_rows.append([{"text": "✅ پشکنینی ئەندامبوون", "callback_data": "check_join"}])
    msg = "\n".join(lines) + "\n\n📌 دوای ئەندامبوون، دووبارە /start بنووسە"
    await update.message.reply_text(msg, parse_mode="HTML",
        reply_markup={"inline_keyboard": keyboard_rows} if False else None)
    # بە سادەیی بێ inline keyboard پەیامەکە دەنێرین
    kb = ReplyKeyboardMarkup([[KeyboardButton("🔄 پشکنینی دووبارە")]], resize_keyboard=True)
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)

# ══════════════════════════════════════════════════════════════════════════════
# ██  کیبۆردەکان
# ══════════════════════════════════════════════════════════════════════════════

# ── مینیوی سەرەکی ──────────────────────────────────────────────────────────
def kb_main(uid: int) -> ReplyKeyboardMarkup:
    if uid == OWNER_ID:
        return ReplyKeyboardMarkup([
            [KeyboardButton("➕ دروستکردنی بۆتی نوێ"),  KeyboardButton("📂 بۆتەکانم")],
            [KeyboardButton("👑 پانێلی سەرەکی"),         KeyboardButton("📊 ئامارەکان")],
        ], resize_keyboard=True)
    # پشکنینی ئەیا ئەدمینە
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ دروستکردنی بۆتی نوێ"), KeyboardButton("📂 بۆتەکانم")],
        [KeyboardButton("📊 ئامارەکانم")],
    ], resize_keyboard=True)

def kb_main_admin(uid: int) -> ReplyKeyboardMarkup:
    """کیبۆردی ئەدمین"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ دروستکردنی بۆتی نوێ"),  KeyboardButton("📂 بۆتەکانم")],
        [KeyboardButton("🛡 پانێلی ئەدمین"),          KeyboardButton("📊 ئامارەکانم")],
    ], resize_keyboard=True)

# ── کۆنترۆڵی بۆت ─────────────────────────────────────────────────────────
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

# ── پانێلی سەرەکی (Owner) — مینیو ─────────────────────────────────────────
KB_OWNER_MAIN = ReplyKeyboardMarkup([
    [KeyboardButton("👥 بەشی بەکارهێنەران"),   KeyboardButton("🤖 بەشی بۆتەکان")],
    [KeyboardButton("📨 بەشی پەیام"),           KeyboardButton("💎 بەشی VIP")],
    [KeyboardButton("🛡 بەشی ئەمنیەت"),         KeyboardButton("📢 جۆینی ناچاری")],
    [KeyboardButton("⚙️ بەشی سیستەم"),          KeyboardButton("📊 ئامارەکان")],
    [KeyboardButton("👨‍💼 بەشی ئەدمینەکان"),     KeyboardButton("🔔 بەشی ئاگادارکردنەوە")],
    [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")],
], resize_keyboard=True)

# ── پانێلی ئەدمین ──────────────────────────────────────────────────────────
KB_ADMIN_PANEL = ReplyKeyboardMarkup([
    [KeyboardButton("👥 لیستی بەکارهێنەران"),   KeyboardButton("🤖 لیستی بۆتەکان")],
    [KeyboardButton("💎 بەشی VIP"),              KeyboardButton("🚫 بلۆک بەکارهێنەر")],
    [KeyboardButton("📨 بڵاوکردنەوە بۆ هەموو"), KeyboardButton("🔔 ئاگادارکردنەوە")],
    [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")],
], resize_keyboard=True)

# ── بەشی ئەدمینەکان ────────────────────────────────────────────────────────
KB_ADMINS = ReplyKeyboardMarkup([
    [KeyboardButton("👨‍💼 لیستی ئەدمینەکان"),    KeyboardButton("➕ زیادکردنی ئەدمین")],
    [KeyboardButton("➖ لابردنی ئەدمین"),        KeyboardButton("📊 ئامارەکانی ئەدمینەکان")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ── بەشی ئاگادارکردنەوە ────────────────────────────────────────────────────
KB_NOTIF = ReplyKeyboardMarkup([
    [KeyboardButton("🔔 ئاگادارکردنەوەی بەکارهێنەران")],
    [KeyboardButton("📢 ئاگادارکردنەوەی بۆتی سەرەکی")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

KB_NOTIF_USER = ReplyKeyboardMarkup([
    [KeyboardButton("🔔 ئاگادارکردنەوەکانم"),    KeyboardButton("🔕 کوژاندنەوەی ئاگادارکردنەوە")],
    [KeyboardButton("📋 مێژووی ئاگادارکردنەوە")],
    [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")],
], resize_keyboard=True)

# ── بەشی بەکارهێنەران ──────────────────────────────────────────────────────
KB_USERS = ReplyKeyboardMarkup([
    [KeyboardButton("👥 لیستی هەموو بەکارهێنەران"), KeyboardButton("🔍 گەڕان بۆ بەکارهێنەر")],
    [KeyboardButton("📋 زانیاری بەکارهێنەر بە ID"), KeyboardButton("📊 ئامارەکانی بەکارهێنەران")],
    [KeyboardButton("🗑 سڕینەوەی بەکارهێنەر"),     KeyboardButton("📤 هەناردەکردنی لیست")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ── بەشی بۆتەکان ───────────────────────────────────────────────────────────
KB_BOTS = ReplyKeyboardMarkup([
    [KeyboardButton("🤖 لیستی هەموو بۆتەکان"),   KeyboardButton("🟢 بۆتە چالاکەکان")],
    [KeyboardButton("🔴 بۆتە ڕاگیراوەکان"),       KeyboardButton("📊 ئامارەکانی بۆتەکان")],
    [KeyboardButton("▶️ دەستپێکردنی هەموو"),       KeyboardButton("⏸ وەستاندنی هەموو")],
    [KeyboardButton("🗑 سڕینەوەی بۆت بە ID"),      KeyboardButton("🔍 گەڕان بۆ بۆت")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ── بەشی پەیام ─────────────────────────────────────────────────────────────
KB_MSG = ReplyKeyboardMarkup([
    [KeyboardButton("📨 بڵاوکردنەوە بۆ هەموو"),    KeyboardButton("📨 بڵاوکردنەوە بۆ VIP")],
    [KeyboardButton("📨 بڵاوکردنەوە بۆ نا-VIP"),   KeyboardButton("📬 پەیام بۆ بەکارهێنەرێک")],
    [KeyboardButton("📌 دانانی پەیامی سیستەم"),     KeyboardButton("🗑 سڕینەوەی پەیامی سیستەم")],
    [KeyboardButton("📋 پەیامی سیستەمی ئێستا"),     KeyboardButton("📜 مێژووی بڵاوکردنەوە")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ── بەشی VIP ───────────────────────────────────────────────────────────────
KB_VIP = ReplyKeyboardMarkup([
    [KeyboardButton("💎 لیستی VIPەکان"),            KeyboardButton("➕ زیادکردنی VIP")],
    [KeyboardButton("➖ لابردنی VIP"),               KeyboardButton("📊 ئامارەکانی VIP")],
    [KeyboardButton("💎 VIP بۆ کاتی دیاریکراو"),    KeyboardButton("💎 VIP بۆ هەمیشەیی")],
    [KeyboardButton("🔍 پشکنینی VIP بەکارهێنەر"),   KeyboardButton("🗑 سڕینەوەی هەموو VIP")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ── بەشی ئەمنیەت ───────────────────────────────────────────────────────────
KB_SEC = ReplyKeyboardMarkup([
    [KeyboardButton("🚫 بلۆک کردنی بەکارهێنەر"),    KeyboardButton("✅ لابردنی بلۆک")],
    [KeyboardButton("📋 لیستی بلۆکەکان"),            KeyboardButton("🗑 سڕینەوەی هەموو بلۆک")],
    [KeyboardButton("⚠️ ئاگادارکردنەوەی بەکارهێنەر"),KeyboardButton("🔒 قەدەغەکردنی فیچەر")],
    [KeyboardButton("🛡 مۆدی ئاگادارکردنەوە"),       KeyboardButton("📋 لیستی ئاگادارکراوەکان")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ── بەشی کانال (جۆینی ناچاری) ─────────────────────────────────────────────
KB_CHAN = ReplyKeyboardMarkup([
    [KeyboardButton("📢 گۆڕینی کانالی سەرەکی"),      KeyboardButton("🔔 چالاككردنی جۆینی ناچاری")],
    [KeyboardButton("🔕 لەکارخستنی جۆینی ناچاری"),   KeyboardButton("➕ زیادکردنی کانالی داواکراو")],
    [KeyboardButton("➖ لابردنی کانالی داواکراو"),    KeyboardButton("📋 لیستی کانالەکان")],
    [KeyboardButton("🔍 پشکنینی ئەندامی کانال"),     KeyboardButton("📊 ئامارەکانی کانال")],
    [KeyboardButton("🗑 سڕینەوەی هەموو کانالی داواکراو")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ── بەشی سیستەم ────────────────────────────────────────────────────────────
KB_SYS = ReplyKeyboardMarkup([
    [KeyboardButton("⚙️ زانیاری سیستەم"),            KeyboardButton("🔄 نوێکردنەوەی هەموو وەبهووک")],
    [KeyboardButton("🗑 پاككردنی داتابەیس"),          KeyboardButton("💾 پشتگیری داتابەیس")],
    [KeyboardButton("📝 گۆڕینی بۆتی سەرەکی"),        KeyboardButton("🌐 گۆڕینی PROJECT URL")],
    [KeyboardButton("📋 لۆگەکان"),                    KeyboardButton("🔃 ڕیستارتی سیستەم")],
    [KeyboardButton("📢 گۆڕینی کانالی بەڕێوەبەر"),   KeyboardButton("🖼 گۆڕینی وێنەی بەخێرهاتن")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ══════════════════════════════════════════════════════════════════════════════
# ██  /start
# ══════════════════════════════════════════════════════════════════════════════
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = html.escape(update.effective_user.first_name or "بەکارهێنەر")

    if await is_blocked(uid):
        await update.message.reply_text("🚫 دەستت لە بۆتەکە گرتراوە.")
        return

    # پشکنینی جۆینی ناچاری کەناڵ بۆ بەکارهێنەرانی ئاسایی
    if uid != OWNER_ID and not await is_admin(uid):
        joined, not_joined = await check_force_join(uid)
        if not joined:
            await send_force_join_msg(update, not_joined)
            return

    await db_del(f"users/{uid}/state")
    await db_patch(f"users/{uid}", {
        "name":     update.effective_user.first_name or "",
        "username": update.effective_user.username   or "",
        "active":   True,
        "last_seen": now_str(),
    })

    vip_badge = " 💎" if await is_vip(uid) else ""
    admin_badge = " 🛡" if (await is_admin(uid) and uid != OWNER_ID) else ""

    if uid == OWNER_ID:
        # خێراکردن بۆ خاوەنی بۆت - داتا لە یەک جار دەگرین
        all_b = await db_get("managed_bots") or {}
        all_u = await db_get("users") or {}
        run   = sum(1 for v in all_b.values() if v.get("status") == "running")
        admins = await db_get("admins") or {}
        txt = (
            f"‏‼️ <b>بەخێربێیت خاوەنی سیستەم، {name}!</b>\n\n"
            f"‏━━━━━━━━━━━━━━━━━━━━━━\n"
            f"‏👥 بەکارهێنەران: <b>{len(all_u)}</b>\n"
            f"‏🤖 بۆتەکان: <b>{len(all_b)}</b>  (🟢{run}  🔴{len(all_b)-run})\n"
            f"‏👨‍💼 ئەدمینەکان: <b>{len(admins)}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"‏🎛 پانێلی سەرەکی — کۆنترۆڵی تەواوی سیستەم\n"
            f"‏👇 هەڵبژاردنێک بکە:"
        )
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main(uid))
    elif await is_admin(uid):
        txt = (
            f"‏‼️ <b>بەخێربێیت، ئەدمین {name}{admin_badge}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛡 دەستتە بۆ پانێلی ئەدمین\n"
            "🤖 دروستکردنی بۆتی تایبەتی خۆت\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 لە کیبۆردی خوارەوە هەڵبژێرە:"
        )
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main_admin(uid))
    else:
        vip_speed = "⚡ خێرا" if await is_vip(uid) else "🐢 ئاسایی"
        txt = (
            f"‏‼️ <b>بەخێربێیت، {name}{vip_badge}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 دروستکردنی بۆتی تایبەتی خۆت\n"
            "⚙️ کۆنترۆڵی تەواوی بۆتەکەت\n"
            "📨 ناردنی پەیام بۆ بەکارهێنەرانی بۆتەکەت\n"
            f"🚀 خێرایی: {vip_speed}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 لە کیبۆردی خوارەوە هەڵبژێرە:"
        )
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main(uid))

# ══════════════════════════════════════════════════════════════════════════════
# ██  handler ی سەرەکی
# ══════════════════════════════════════════════════════════════════════════════
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt   = update.message.text.strip()
    uid   = update.effective_user.id
    state = await db_get(f"users/{uid}/state") or ""

    if await is_blocked(uid):
        await update.message.reply_text("🚫 دەستت لە بۆتەکە گرتراوە.")
        return

    # پشکنینی دووبارەی جۆینی کەناڵ
    if txt == "🔄 پشکنینی دووبارە":
        if uid != OWNER_ID and not await is_admin(uid):
            joined, not_joined = await check_force_join(uid)
            if not joined:
                await send_force_join_msg(update, not_joined)
            else:
                await master_start(update, ctx)
        else:
            await master_start(update, ctx)
        return

    # ── ناڤیگەیشنی گشتی ───────────────────────────────────────────────────
    if txt == "🔙 گەڕانەوە بۆ سەرەتا":
        await db_del(f"users/{uid}/state")
        await master_start(update, ctx)
        return

    if txt == "🔙 گەڕانەوە بۆ لیست":
        await db_del(f"users/{uid}/state")
        await show_bot_list(update, uid)
        return

    if txt == "🔙 گەڕانەوە بۆ پانێلی سەرەکی" and uid == OWNER_ID:
        await db_del(f"users/{uid}/state")
        await show_owner_main(update)
        return

    if txt == "🔙 گەڕانەوە بۆ پانێلی سەرەکی" and await is_admin(uid):
        await db_del(f"users/{uid}/state")
        await update.message.reply_text("🛡 پانێلی ئەدمین:", reply_markup=KB_ADMIN_PANEL)
        return

    # ── دروستکردنی بۆتی نوێ ───────────────────────────────────────────────
    if txt == "➕ دروستکردنی بۆتی نوێ":
        # پشکنینی جۆینی ناچاری کەناڵ
        if uid != OWNER_ID and not await is_admin(uid):
            joined, not_joined = await check_force_join(uid)
            if not joined:
                await send_force_join_msg(update, not_joined)
                return
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

    # ── لیستی بۆتەکانم ────────────────────────────────────────────────────
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
        "▶️ دەستپێکردن","⏸ وەستاندن","🔄 نوێکردنەوە","📋 زانیاری بۆت",
        "✏️ گۆڕینی بەخێرهاتن","📨 پەیام بۆ بەکارهێنەران",
        "🗑 سڕینەوەی بۆت","🔑 گۆڕینی تۆکێن","🔗 نوێکردنەوەی وەبهووک",
    }
    if txt in CTRL:
        await handle_control(update, uid, txt)
        return

    # ── ئامار ─────────────────────────────────────────────────────────────
    if txt in ("📊 ئامارەکان","📊 ئامارەکانم"):
        await show_stats(update, uid)
        return

    # ── پانێلی ئەدمین (بۆ ئەدمینەکان) ───────────────────────────────────
    if txt == "🛡 پانێلی ئەدمین" and await is_admin(uid) and uid != OWNER_ID:
        await update.message.reply_text("🛡 <b>پانێلی ئەدمین</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_ADMIN_PANEL)
        return

    # ── بەشی ئاگادارکردنەوە (بۆ بەکارهێنەران) ──────────────────────────
    if txt == "🔔 ئاگادارکردنەوەکانم":
        await show_user_notifications(update, uid)
        return

    # ════════════════════════════════════════════════════════════════════════
    # پانێلی سەرەکی و بەشەکانی (تەنها Owner)
    # ════════════════════════════════════════════════════════════════════════
    if uid == OWNER_ID:
        # ── مینیوی سەرەکی ─────────────────────────────────────────────────
        if txt == "👑 پانێلی سەرەکی":
            await show_owner_main(update)
            return

        # ════ بەشی بەکارهێنەران ════════════════════════════════════════════
        if txt == "👥 بەشی بەکارهێنەران":
            await update.message.reply_text("👥 <b>بەشی بەکارهێنەران</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_USERS)
            return
        if txt == "👥 لیستی هەموو بەکارهێنەران":
            await owner_list_users(update, full=True)
            return
        if txt == "🔍 گەڕان بۆ بەکارهێنەر":
            await db_put(f"users/{uid}/state", "search_user")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🔍 ناو یان یوزەرنەیم یان ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return
        if txt == "📋 زانیاری بەکارهێنەر بە ID":
            await db_put(f"users/{uid}/state", "user_info_id")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return
        if txt == "📊 ئامارەکانی بەکارهێنەران":
            await owner_user_stats(update)
            return
        if txt == "🗑 سڕینەوەی بەکارهێنەر":
            await db_put(f"users/{uid}/state", "del_user")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە تا بیسڕیتەوە:", reply_markup=kb)
            return
        if txt == "📤 هەناردەکردنی لیست":
            await owner_export_users(update)
            return

        # ════ بەشی بۆتەکان ════════════════════════════════════════════════
        if txt == "🤖 بەشی بۆتەکان":
            await update.message.reply_text("🤖 <b>بەشی بۆتەکان</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_BOTS)
            return
        if txt == "🤖 لیستی هەموو بۆتەکان":
            await owner_list_bots(update, filter_status=None)
            return
        if txt == "🟢 بۆتە چالاکەکان":
            await owner_list_bots(update, filter_status="running")
            return
        if txt == "🔴 بۆتە ڕاگیراوەکان":
            await owner_list_bots(update, filter_status="stopped")
            return
        if txt == "📊 ئامارەکانی بۆتەکان":
            await owner_bot_stats(update)
            return
        if txt == "▶️ دەستپێکردنی هەموو":
            await owner_all_bots_action(update, "running")
            return
        if txt == "⏸ وەستاندنی هەموو":
            await owner_all_bots_action(update, "stopped")
            return
        if txt == "🗑 سڕینەوەی بۆت بە ID":
            await db_put(f"users/{uid}/state", "owner_del_bot")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بۆتەکە بنووسە:", reply_markup=kb)
            return
        if txt == "🔍 گەڕان بۆ بۆت":
            await db_put(f"users/{uid}/state", "search_bot")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🔍 یوزەرنەیم یان ID ی بۆتەکە بنووسە:", reply_markup=kb)
            return

        # ════ بەشی پەیام ══════════════════════════════════════════════════
        if txt == "📨 بەشی پەیام":
            await update.message.reply_text("📨 <b>بەشی پەیام</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_MSG)
            return
        if txt == "📨 بڵاوکردنەوە بۆ هەموو":
            await db_put(f"users/{uid}/state", "bc_all")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("📨 <b>بڵاوکردنەوە بۆ هەموو</b>\n\nپەیامەکەت بنووسە:", parse_mode="HTML", reply_markup=kb)
            return
        if txt == "📨 بڵاوکردنەوە بۆ VIP":
            await db_put(f"users/{uid}/state", "bc_vip")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("💎 <b>بڵاوکردنەوە بۆ VIPەکان تەنها</b>\n\nپەیامەکەت بنووسە:", parse_mode="HTML", reply_markup=kb)
            return
        if txt == "📨 بڵاوکردنەوە بۆ نا-VIP":
            await db_put(f"users/{uid}/state", "bc_nonvip")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("📨 <b>بڵاوکردنەوە بۆ نا-VIPەکان</b>\n\nپەیامەکەت بنووسە:", parse_mode="HTML", reply_markup=kb)
            return
        if txt == "📬 پەیام بۆ بەکارهێنەرێک":
            await db_put(f"users/{uid}/state", "msg_one_id")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return
        if txt == "📌 دانانی پەیامی سیستەم":
            await db_put(f"users/{uid}/state", "set_sys_msg")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text(
                "📌 <b>دانانی پەیامی سیستەم</b>\n\n"
                "ئەم پەیامە بە هەموو بەکارهێنەرانەوە نیشاندەدرێت کاتێک دەستی پێدەکەن.\n"
                "پەیامەکەت بنووسە (HTML پشتگیری دەکات):",
                parse_mode="HTML", reply_markup=kb,
            )
            return
        if txt == "🗑 سڕینەوەی پەیامی سیستەم":
            await db_del("system/notice")
            await update.message.reply_text("✅ پەیامی سیستەم سڕایەوە.", reply_markup=KB_MSG)
            return
        if txt == "📋 پەیامی سیستەمی ئێستا":
            msg_now = await db_get("system/notice")
            if msg_now:
                await update.message.reply_text(f"📌 <b>پەیامی سیستەمی ئێستا:</b>\n\n{msg_now}", parse_mode="HTML", reply_markup=KB_MSG)
            else:
                await update.message.reply_text("📭 هیچ پەیامی سیستەمێک دانەنراوە.", reply_markup=KB_MSG)
            return
        if txt == "📜 مێژووی بڵاوکردنەوە":
            await owner_broadcast_history(update)
            return

        # ════ بەشی VIP ════════════════════════════════════════════════════
        if txt == "💎 بەشی VIP":
            await update.message.reply_text("💎 <b>بەشی VIP</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_VIP)
            return
        if txt == "💎 لیستی VIPەکان":
            await owner_list_vips(update)
            return
        if txt == "➕ زیادکردنی VIP":
            await db_put(f"users/{uid}/state", "add_vip")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return
        if txt == "➖ لابردنی VIP":
            await db_put(f"users/{uid}/state", "del_vip")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی VIP بنووسە:", reply_markup=kb)
            return
        if txt == "📊 ئامارەکانی VIP":
            await owner_vip_stats(update)
            return
        if txt == "💎 VIP بۆ کاتی دیاریکراو":
            await db_put(f"users/{uid}/state", "add_vip_date")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەر بنووسە، ئینجا بەرواری بەسەرچوون:\nنموونە: <code>123456789 2025-12-31</code>", parse_mode="HTML", reply_markup=kb)
            return
        if txt == "💎 VIP بۆ هەمیشەیی":
            await db_put(f"users/{uid}/state", "add_vip_life")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەر بنووسە (VIP بۆ هەمیشە دەبێت):", reply_markup=kb)
            return
        if txt == "🔍 پشکنینی VIP بەکارهێنەر":
            await db_put(f"users/{uid}/state", "check_vip")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەر بنووسە:", reply_markup=kb)
            return
        if txt == "🗑 سڕینەوەی هەموو VIP":
            await db_put(f"users/{uid}/state", "confirm_del_all_vip")
            kb = ReplyKeyboardMarkup([
                [KeyboardButton("✅ بەڵێ، هەموو VIP بسڕەوە")],
                [KeyboardButton("❌ هەڵوەشاندنەوە")],
            ], resize_keyboard=True)
            await update.message.reply_text("⚠️ <b>دڵنیایت؟</b> هەموو VIPەکان دەسڕیتەوە!", parse_mode="HTML", reply_markup=kb)
            return

        # ════ بەشی ئەمنیەت ════════════════════════════════════════════════
        if txt == "🛡 بەشی ئەمنیەت":
            await update.message.reply_text("🛡 <b>بەشی ئەمنیەت</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_SEC)
            return
        if txt == "🚫 بلۆک کردنی بەکارهێنەر":
            await db_put(f"users/{uid}/state", "block_user")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return
        if txt == "✅ لابردنی بلۆک":
            await db_put(f"users/{uid}/state", "unblock_user")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەرەکە بنووسە:", reply_markup=kb)
            return
        if txt == "📋 لیستی بلۆکەکان":
            await owner_list_blocked(update)
            return
        if txt == "🗑 سڕینەوەی هەموو بلۆک":
            await db_del("blocked")
            await update.message.reply_text("✅ هەموو بلۆکەکان سڕایەوە.", reply_markup=KB_SEC)
            return
        if txt == "⚠️ ئاگادارکردنەوەی بەکارهێنەر":
            await db_put(f"users/{uid}/state", "warn_user_id")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەر بنووسە:", reply_markup=kb)
            return
        if txt == "🔒 قەدەغەکردنی فیچەر":
            await db_put(f"users/{uid}/state", "restrict_feat")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text(
                "🔒 ناوی فیچەر بنووسە کە دەتەوێت قەدەغە بکەیت:\n"
                "نموونە: <code>create_bot</code> یان <code>broadcast</code>",
                parse_mode="HTML", reply_markup=kb,
            )
            return
        if txt == "🛡 مۆدی ئاگادارکردنەوە":
            await owner_toggle_alert_mode(update, uid)
            return
        if txt == "📋 لیستی ئاگادارکراوەکان":
            await owner_list_warned(update)
            return

        # ════ بەشی کانال ══════════════════════════════════════════════════
        if txt == "📢 جۆینی ناچاری":
            fj = await db_get("system/force_join") or False
            req_chs = await db_get("system/req_channels") or {}
            await update.message.reply_text(
                f"📢 <b>بەشی جۆینی ناچاری</b>\n\n"
                f"📋 کانالە داواکراوەکان: <b>{len(req_chs)}</b>\n"
                f"🔔 دۆخ: <b>{'✅ چالاک' if fj else '❌ لەکارخراو'}</b>\n\n"
                "هەڵبژاردنێک بکە:",
                parse_mode="HTML", reply_markup=KB_CHAN
            )
            return
        if txt == "📢 گۆڕینی کانالی سەرەکی":
            await db_put(f"users/{uid}/state", "change_main_channel")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("📢 یوزەرنەیمی کانالی نوێ بنووسە (بەبێ @):", reply_markup=kb)
            return
        if txt == "🔔 چالاككردنی جۆینی ناچاری":
            await db_put("system/force_join", True)
            await update.message.reply_text("✅ جۆینی ناچاری چالاک کرا!\n\nئێستا بەکارهێنەران پێش بەکارهێنانی بۆت دەبێت ئەندامی کانالەکان بن.", reply_markup=KB_CHAN)
            return
        if txt == "🔕 لەکارخستنی جۆینی ناچاری":
            await db_put("system/force_join", False)
            await update.message.reply_text("❌ جۆینی ناچاری لەکارخرا.", reply_markup=KB_CHAN)
            return
        if txt == "➕ زیادکردنی کانالی داواکراو":
            await db_put(f"users/{uid}/state", "add_req_channel")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text(
                "➕ یوزەرنەیمی کانالەکە بنووسە (بەبێ @):\n\n"
                "💡 تێبینی: بۆتی سەرەکی دەبێت ئەدمینی ئەم کانالە بێت",
                reply_markup=kb,
            )
            return
        if txt == "➖ لابردنی کانالی داواکراو":
            await db_put(f"users/{uid}/state", "del_req_channel")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("➖ یوزەرنەیمی کانالەکە بنووسە (بەبێ @):", reply_markup=kb)
            return
        if txt == "📋 لیستی کانالەکان":
            await owner_list_channels(update)
            return
        if txt == "🗑 سڕینەوەی هەموو کانالی داواکراو":
            await db_del("system/req_channels")
            await update.message.reply_text("🗑 هەموو کانالە داواکراوەکان سڕایەوە.", reply_markup=KB_CHAN)
            return
        if txt == "🔍 پشکنینی ئەندامی کانال":
            await db_put(f"users/{uid}/state", "check_member")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی بەکارهێنەر بنووسە:", reply_markup=kb)
            return
        if txt == "📊 ئامارەکانی کانال":
            await owner_channel_stats(update)
            return

        # ════ بەشی ئەدمینەکان ═════════════════════════════════════════════
        if txt == "👨‍💼 بەشی ئەدمینەکان":
            await update.message.reply_text("👨‍💼 <b>بەشی ئەدمینەکان</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_ADMINS)
            return
        if txt == "👨‍💼 لیستی ئەدمینەکان":
            await owner_list_admins(update)
            return
        if txt == "➕ زیادکردنی ئەدمین":
            await db_put(f"users/{uid}/state", "add_admin")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text(
                "👨‍💼 <b>زیادکردنی ئەدمینی نوێ</b>\n\n"
                "🆔 ID ی بەکارهێنەرەکە بنووسە کە دەتەوێت ئەدمینی بکەیت:",
                parse_mode="HTML", reply_markup=kb,
            )
            return
        if txt == "➖ لابردنی ئەدمین":
            await db_put(f"users/{uid}/state", "del_admin")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🆔 ID ی ئەدمینەکە بنووسە تا لابیبریت:", reply_markup=kb)
            return
        if txt == "📊 ئامارەکانی ئەدمینەکان":
            await owner_admin_stats(update)
            return

        # ════ بەشی ئاگادارکردنەوە ═════════════════════════════════════════
        if txt == "🔔 بەشی ئاگادارکردنەوە":
            R = "\u200f"
            notif_users = await db_get("system/notif_users_enabled") or True
            notif_main  = await db_get("system/notif_main_enabled")  or True
            await update.message.reply_text(
                f"{R}🔔 <b>بەشی ئاگادارکردنەوە</b>\n\n"
                f"{R}👥 ئاگادارکردنەوەی بەکارهێنەران: <b>{'✅ چالاک' if notif_users else '❌ لەکارخراو'}</b>\n"
                f"{R}📢 ئاگادارکردنەوەی بۆتی سەرەکی: <b>{'✅ چالاک' if notif_main else '❌ لەکارخراو'}</b>\n\n"
                f"{R}👇 هەڵبژێرە:",
                parse_mode="HTML", reply_markup=KB_NOTIF
            )
            return
        if txt == "🔔 ئاگادارکردنەوەی بەکارهێنەران":
            await db_put(f"users/{uid}/state", "notif_all")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            R = "\u200f"
            await update.message.reply_text(
                f"{R}🔔 <b>ئاگادارکردنەوەی بەکارهێنەران</b>\n\n"
                f"{R}📨 ئەم نامەیە دەچێت بۆ هەموو بەکارهێنەرانی بۆتەکەت\n\n"
                f"{R}⬇️ نامەکەت بنووسە:",
                parse_mode="HTML", reply_markup=kb
            )
            return
        if txt == "📢 ئاگادارکردنەوەی بۆتی سەرەکی":
            await db_put(f"users/{uid}/state", "notif_master")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            R = "\u200f"
            await update.message.reply_text(
                f"{R}📢 <b>ئاگادارکردنەوەی بۆتی سەرەکی</b>\n\n"
                f"{R}📨 ئەم نامەیە دەچێت بۆ هەموو بەکارهێنەرانی بۆتی سەرەکی (دروستکەرانی بۆت)\n\n"
                f"{R}⬇️ نامەکەت بنووسە:",
                parse_mode="HTML", reply_markup=kb
            )
            return

        # ════ بەشی سیستەم ═════════════════════════════════════════════════
        if txt == "⚙️ بەشی سیستەم":
            await update.message.reply_text("⚙️ <b>بەشی سیستەم</b>\n\nهەڵبژاردنێک بکە:", parse_mode="HTML", reply_markup=KB_SYS)
            return
        if txt == "⚙️ زانیاری سیستەم":
            await owner_sys_info(update)
            return
        if txt == "🔄 نوێکردنەوەی هەموو وەبهووک":
            await owner_refresh_all_webhooks(update)
            return
        if txt == "🗑 پاككردنی داتابەیس":
            await db_put(f"users/{uid}/state", "confirm_clear_db")
            kb = ReplyKeyboardMarkup([
                [KeyboardButton("✅ بەڵێ، پاک بکەرەوە")],
                [KeyboardButton("❌ هەڵوەشاندنەوە")],
            ], resize_keyboard=True)
            await update.message.reply_text("⚠️ <b>دڵنیایت؟</b> هەموو داتاکان دەسڕیتەوە!", parse_mode="HTML", reply_markup=kb)
            return
        if txt == "💾 پشتگیری داتابەیس":
            await owner_backup_db(update)
            return
        if txt == "📝 گۆڕینی بۆتی سەرەکی":
            await db_put(f"users/{uid}/state", "change_master_token")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🔑 تۆکێنی نوێی بۆتی سەرەکی بنووسە:", reply_markup=kb)
            return
        if txt == "🌐 گۆڕینی PROJECT URL":
            await db_put(f"users/{uid}/state", "change_project_url")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            cur = await db_get("system/project_url") or PROJECT_URL or "نییە"
            await update.message.reply_text(f"🌐 URL ی ئێستا: <code>{cur}</code>\n\nURL ی نوێ بنووسە:", parse_mode="HTML", reply_markup=kb)
            return
        if txt == "📋 لۆگەکان":
            await owner_show_logs(update)
            return
        if txt == "🔃 ڕیستارتی سیستەم":
            await db_put(f"users/{uid}/state", "confirm_restart")
            kb = ReplyKeyboardMarkup([
                [KeyboardButton("✅ بەڵێ، ڕیستارت بکە")],
                [KeyboardButton("❌ هەڵوەشاندنەوە")],
            ], resize_keyboard=True)
            await update.message.reply_text("⚠️ دڵنیایت لە ڕیستارتکردنی سیستەم؟", reply_markup=kb)
            return
        if txt == "📢 گۆڕینی کانالی بەڕێوەبەر":
            await db_put(f"users/{uid}/state", "change_dev_channel")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("📢 یوزەرنەیمی کانالی بەڕێوەبەری نوێ بنووسە (بەبێ @):", reply_markup=kb)
            return
        if txt == "🖼 گۆڕینی وێنەی بەخێرهاتن":
            await db_put(f"users/{uid}/state", "change_photo_url")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text("🖼 لینکی وێنەی نوێ بنووسە:", reply_markup=kb)
            return

    # ════════════════════════════════════════════════════════════════════════
    # دۆخەکانی چاوەڕوانی
    # ════════════════════════════════════════════════════════════════════════
    await handle_states(update, uid, txt, state)


# ══════════════════════════════════════════════════════════════════════════════
# ── نیشاندانی Owner Main
# ══════════════════════════════════════════════════════════════════════════════
async def show_owner_main(update: Update):
    all_b  = await db_get("managed_bots") or {}
    all_u  = await db_get("users")         or {}
    all_v  = await db_get("vip")           or {}
    all_bl = await db_get("blocked")       or {}
    admins = await db_get("admins")        or {}
    run    = sum(1 for v in all_b.values() if v.get("status") == "running")
    notif_on = await db_get("system/notifications_enabled")
    fj       = await db_get("system/force_join") or False
    msg = (
        "‏‼️ <b>پانێلی سەرەکی</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"‏👥 بەکارهێنەران:   <b>{len(all_u)}</b>\n"
        f"‏🤖 بۆتەکان:        <b>{len(all_b)}</b>  (🟢{run}  🔴{len(all_b)-run})\n"
        f"‏💎 VIPەکان:        <b>{len(all_v)}</b>\n"
        f"‏🚫 بلۆکەکان:       <b>{len(all_bl)}</b>\n"
        f"‏👨‍💼 ئەدمینەکان:     <b>{len(admins)}</b>\n"
        f"‏🔔 ئاگادارکردنەوە: <b>{'چالاک ✅' if notif_on else 'لەکارخراو ❌'}</b>\n"
        f"‏📢 جۆینی ناچاری:   <b>{'چالاک ✅' if fj else 'لەکارخراو ❌'}</b>\n"        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "‏📌 بەشێک هەڵبژێرە:"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_OWNER_MAIN)


# ══════════════════════════════════════════════════════════════════════════════
# ── نیشاندانی لیست / کۆنترۆڵ
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
        f"‏📂 <b>بۆتەکانت ({len(mine)}):</b>\n‏🟢 کاردەکات  |  🔴 ڕاگیراوە",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True),
    )


async def show_bot_control(update: Update, uid: int, bid: str, info: dict):
    R = "\u200f"  # RTL mark
    st_icon = "🟢" if info.get("status") == "running" else "🔴"
    st_txt  = f"{R}چالاک ✅" if info.get("status") == "running" else f"{R}ڕاگیراوە ❌"
    name    = html.escape(info.get("bot_name", "ناسناو"))
    un      = info.get("bot_username", "ناسناو")
    bu      = await db_get(f"bot_users/{bid}") or {}
    wlcm    = info.get("welcome_msg", "")
    owner_id = info.get("owner", "")

    msg = (
        f"{R}⚙️ <b>پانێلی کۆنترۆڵ</b>\n"
        f"{R}━━━━━━━━━━━━━━━━━━━\n"
        f"{R}🤖 <b>ناو:</b> {name}\n"
        f"{R}🔗 <b>یوزەر:</b> @{un}\n"
        f"{R}🆔 <b>ID:</b> <code>{bid}</code>\n"
        f"{R}━━━━━━━━━━━━━━━━━━━\n"
        f"{R}{st_icon} <b>دۆخ:</b> {st_txt}\n"
        f"{R}👥 <b>بەکارهێنەران:</b> <b>{len(bu)}</b> کەس\n"
        f"{R}✉️ <b>بەخێرهاتن:</b> {'✅ دانراوە' if wlcm else '❌ بەتاڵ'}\n"
        f"{R}━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb_control(uid))


async def show_stats(update: Update, uid: int):
    all_b = await db_get("managed_bots") or {}
    all_u = await db_get("users")         or {}
    mine  = {k: v for k, v in all_b.items() if v.get("owner") == uid}
    run_m = sum(1 for v in mine.values() if v.get("status") == "running")
    if uid == OWNER_ID:
        run_a = sum(1 for v in all_b.values() if v.get("status") == "running")
        all_v = await db_get("vip") or {}
        admins = await db_get("admins") or {}
        txt   = (
            "‏📊 <b>ئامارەکانی سیستەم</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👥 هەموو بەکارهێنەران: <b>{len(all_u)}</b>\n"
            f"🤖 هەموو بۆتەکان:      <b>{len(all_b)}</b>\n"
            f"🟢 چالاک: <b>{run_a}</b>  🔴 ڕاگیراو: <b>{len(all_b)-run_a}</b>\n"
            f"💎 VIPەکان: <b>{len(all_v)}</b>\n"
            f"👨‍💼 ئەدمینەکان: <b>{len(admins)}</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"📁 بۆتەکانی خۆت: <b>{len(mine)}</b>  (🟢{run_m})"
        )
    else:
        bu_count = 0
        for k, v in mine.items():
            bu = await db_get(f"bot_users/{k}") or {}
            bu_count += len(bu)
        vip_badge = "💎 VIP" if await is_vip(uid) else "👤 ئاسایی"
        txt = (
            "‏📊 <b>ئامارەکانت</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"🎖 دۆخ: <b>{vip_badge}</b>\n"
            f"🤖 بۆتی دروستکردوو: <b>{len(mine)}</b>\n"
            f"🟢 چالاک: <b>{run_m}</b>  🔴 ڕاگیراو: <b>{len(mine)-run_m}</b>\n"
            f"👥 کۆی بەکارهێنەرانی بۆتەکانت: <b>{bu_count}</b>"
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
    un    = info.get("bot_username","Bot")
    token = info.get("token","")

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
        cur = info.get("welcome_msg","")
        kb  = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
        await update.message.reply_text(
            "✏️ <b>گۆڕینی نامەی بەخێرهاتن</b>\n\n"
            f"📝 نامەی ئێستا:\n<code>{html.escape(cur) if cur else '(بەتاڵ)'}</code>\n\n"
            "نامەی نوێت بنووسە:\n💡 <code>{name}</code> بەکاربهێنە بۆ ناوی بەکارهێنەر",
            parse_mode="HTML", reply_markup=kb,
        )

    elif txt == "📨 پەیام بۆ بەکارهێنەران":
        bu = await db_get(f"bot_users/{bid}") or {}
        if not bu:
            await update.message.reply_text("📭 هیچ بەکارهێنەرێک بۆتەکەت بەکار نەهێناوە.", reply_markup=kb_control(uid))
            return
        await db_put(f"users/{uid}/state", f"bot_bc:{bid}")
        kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
        await update.message.reply_text(
            f"📨 <b>بڵاوکردنەوە بۆ بەکارهێنەرانی @{un}</b>\n\n"
            f"👥 ژمارە: <b>{len(bu)}</b>\n\nپەیامەکەت بنووسە:",
            parse_mode="HTML", reply_markup=kb,
        )

    elif txt == "🔗 نوێکردنەوەی وەبهووک" and uid == OWNER_ID:
        if token:
            safe = (PROJECT_URL or "").rstrip('/')
            r    = await send_tg(token,"setWebhook",{"url":f"{safe}/api/bot/{token}","allowed_updates":["message","channel_post"]})
            resp = "✅ وەبهووک نوێکرایەوە!" if r.get("ok") else f"❌ هەڵە: {r.get('description','')}"
            await update.message.reply_text(resp, reply_markup=kb_control(uid))
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
# ── دۆخەکانی چاوەڕوانی
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
            await update.message.reply_text("⚠️ تۆکێنەکە دروست نییە.\nنموونە: <code>123456789:ABCxyz...</code>", parse_mode="HTML")
        return

    # ── دڵنیاکردنەوەی سڕینەوەی بۆت ──────────────────────────────────────
    if state.startswith("confirm_del:"):
        bid = state.split(":",1)[1]
        if txt.startswith("✅ بەڵێ،"):
            await do_delete_bot(update, uid, bid)
        else:
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("↩️ گەڕایتەوە.", reply_markup=kb_control(uid))
        return

    # ── گۆڕینی بەخێرهاتن ──────────────────────────────────────────────────
    if state.startswith("edit_welcome:"):
        bid  = state.split(":",1)[1]
        info = await db_get(f"managed_bots/{bid}")
        if not info:
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("❌ بۆتەکە نەدۆزرایەوە.", reply_markup=kb_main(uid))
            return
        info["welcome_msg"] = txt
        await db_put(f"managed_bots/{bid}", info)
        await db_del(f"users/{uid}/state")
        await update.message.reply_text("✅ <b>نامەی بەخێرهاتن نوێکرا!</b>", parse_mode="HTML", reply_markup=kb_control(uid))
        return

    # ── بڵاوکردنەوەی بۆت ─────────────────────────────────────────────────
    if state.startswith("bot_bc:"):
        bid   = state.split(":",1)[1]
        info  = await db_get(f"managed_bots/{bid}") or {}
        token = info.get("token","")
        bu    = await db_get(f"bot_users/{bid}") or {}
        # خێراکردن بەپێی VIP
        vip_user = await is_vip(uid)
        delay = 0.02 if vip_user else 0.05
        sm    = await update.message.reply_text(f"⏳ ناردن بۆ {len(bu)} بەکارهێنەر...")
        sent=fail=0
        for cid in bu.keys():
            try:
                r = await send_tg(token,"sendMessage",{"chat_id":int(cid),"text":txt,"parse_mode":"HTML"})
                if r.get("ok"): sent+=1
                else: fail+=1
            except: fail+=1
            await asyncio.sleep(delay)
        await db_del(f"users/{uid}/state")
        await sm.edit_text(f"✅ <b>تەواو!</b> 📤{sent}  ❌{fail}", parse_mode="HTML")
        await update.message.reply_text(".", reply_markup=kb_control(uid))
        return

    # ── گۆڕینی تۆکێن ─────────────────────────────────────────────────────
    if state.startswith("change_token:") and uid == OWNER_ID:
        bid = state.split(":",1)[1]
        if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", txt):
            res = await send_tg(txt,"getMe",{})
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
            await send_tg(txt,"setWebhook",{"url":f"{safe}/api/bot/{txt}","allowed_updates":["message","channel_post"]})
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ تۆکێن گۆڕدرا!", reply_markup=kb_control(uid))
        else:
            await update.message.reply_text("⚠️ تۆکێنەکە دروست نییە.")
        return

    # ══════════════════════════════════════════════════════════════════════
    # دۆخەکانی Owner
    # ══════════════════════════════════════════════════════════════════════
    if uid != OWNER_ID and not await is_admin(uid):
        if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", txt):
            await update.message.reply_text("⚠️ تکایە لەسەرەتاوە '➕ دروستکردنی بۆتی نوێ' بکلیک بکە.", reply_markup=kb_main(uid))
        else:
            await update.message.reply_text("تکایە لە کیبۆردی خوارەوە هەڵبژێرە 👇", reply_markup=kb_main(uid))
        return

    # ── بڵاوکردنەوەی گشتی ────────────────────────────────────────────────
    if state in ("bc_all","bc_vip","bc_nonvip","notif_all","notif_vip","notif_master"):
        R = "\u200f"
        all_u   = await db_get("users") or {}
        all_v   = await db_get("vip")   or {}
        vip_ids = set(all_v.keys())
        is_notif = state.startswith("notif_")

        if state in ("bc_all", "notif_all"):
            targets = list(all_u.keys())
        elif state in ("bc_vip", "notif_vip"):
            targets = [i for i in all_u if i in vip_ids]
        elif state == "notif_master":
            targets = list(all_u.keys())  # هەموو بەکارهێنەرانی بۆتی سەرەکی
        else:
            targets = [i for i in all_u if i not in vip_ids]

        prefix = f"{R}🔔 <b>ئاگادارکردنەوە:</b>\n\n" if is_notif else ""
        sm   = await update.message.reply_text(f"⏳ ناردن بۆ {len(targets)} بەکارهێنەر...")
        sent=fail=0
        for u_id in targets:
            try:
                r = await send_tg(MASTER_TOKEN,"sendMessage",{"chat_id":int(u_id),"text":prefix+txt,"parse_mode":"HTML"})
                if r.get("ok"): sent+=1
                else: fail+=1
            except: fail+=1
            await asyncio.sleep(0.05)
        await db_del(f"users/{uid}/state")
        hist_key = "system/notif_history" if is_notif else "system/bc_history"
        hist = await db_get(hist_key) or []
        if isinstance(hist, dict): hist = []
        hist.insert(0, {"time": now_str(), "sent": sent, "fail": fail, "type": state})
        await db_put(hist_key, hist[:20])
        await sm.edit_text(f"✅ <b>تەواو!</b>\n{R}📤 نێردرا: <b>{sent}</b>\n{R}❌ شکستهێنا: <b>{fail}</b>", parse_mode="HTML")
        reply_kb = KB_NOTIF if is_notif else KB_MSG
        await update.message.reply_text(".", reply_markup=reply_kb)
        return

    # ── پەیام بۆ بەکارهێنەرێک ────────────────────────────────────────────
    if state == "msg_one_id":
        try:
            target = int(txt.strip())
            await db_put(f"users/{uid}/state", f"msg_one_text:{target}")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text(f"✅ ID: <code>{target}</code>\n\nئێستا پەیامەکەت بنووسە:", parse_mode="HTML", reply_markup=kb)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state.startswith("msg_one_text:"):
        target = int(state.split(":",1)[1])
        r = await send_tg(MASTER_TOKEN,"sendMessage",{"chat_id":target,"text":txt,"parse_mode":"HTML"})
        await db_del(f"users/{uid}/state")
        if r.get("ok"):
            await update.message.reply_text(f"✅ پەیام بۆ <code>{target}</code> نێردرا!", parse_mode="HTML", reply_markup=KB_MSG)
        else:
            await update.message.reply_text(f"❌ هەڵە: {r.get('description','')}", reply_markup=KB_MSG)
        return

    # ── پەیامی سیستەم ────────────────────────────────────────────────────
    if state == "set_sys_msg":
        await db_put("system/notice", txt)
        await db_del(f"users/{uid}/state")
        await update.message.reply_text("✅ پەیامی سیستەم دانرا.", reply_markup=KB_MSG)
        return

    # ── VIP ───────────────────────────────────────────────────────────────
    if state == "add_vip":
        try:
            target = int(txt.strip())
            await db_put(f"vip/{target}", {"expires":"lifetime","added_by":uid,"date":now_str()})
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"💎 بەکارهێنەری <code>{target}</code> بوو بە VIP هەمیشەیی!", parse_mode="HTML", reply_markup=KB_VIP)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "add_vip_life":
        try:
            target = int(txt.strip())
            await db_put(f"vip/{target}", {"expires":"lifetime","added_by":uid,"date":now_str()})
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"💎 <code>{target}</code> بوو بە VIP هەمیشەیی!", parse_mode="HTML", reply_markup=KB_VIP)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "add_vip_date":
        parts = txt.strip().split()
        if len(parts) == 2:
            try:
                target = int(parts[0])
                datetime.strptime(parts[1], "%Y-%m-%d")
                await db_put(f"vip/{target}", {"expires":parts[1],"added_by":uid,"date":now_str()})
                await db_del(f"users/{uid}/state")
                await update.message.reply_text(f"💎 <code>{target}</code> بوو بە VIP تا <b>{parts[1]}</b>!", parse_mode="HTML", reply_markup=KB_VIP)
            except:
                await update.message.reply_text("⚠️ فۆرمات هەڵەیە. نموونە: <code>123456789 2025-12-31</code>", parse_mode="HTML")
        else:
            await update.message.reply_text("⚠️ فۆرمات هەڵەیە. نموونە: <code>123456789 2025-12-31</code>", parse_mode="HTML")
        return

    if state == "del_vip":
        try:
            target = int(txt.strip())
            await db_del(f"vip/{target}")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"✅ VIPی <code>{target}</code> لابرا.", parse_mode="HTML", reply_markup=KB_VIP)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "check_vip":
        try:
            target  = int(txt.strip())
            vd      = await db_get(f"vip/{target}")
            await db_del(f"users/{uid}/state")
            if vd:
                exp = vd.get("expires","نییە")
                await update.message.reply_text(f"💎 بەکارهێنەری <code>{target}</code> VIPە.\n⏰ بەسەرچوون: <b>{exp}</b>", parse_mode="HTML", reply_markup=KB_VIP)
            else:
                await update.message.reply_text(f"❌ بەکارهێنەری <code>{target}</code> VIP نییە.", parse_mode="HTML", reply_markup=KB_VIP)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "confirm_del_all_vip":
        if txt == "✅ بەڵێ، هەموو VIP بسڕەوە":
            await db_del("vip")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ هەموو VIPەکان سڕایەوە.", reply_markup=KB_VIP)
        else:
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("↩️ هەڵوەشاندرایەوە.", reply_markup=KB_VIP)
        return

    # ── ئەمنیەت ───────────────────────────────────────────────────────────
    if state == "block_user":
        try:
            target = int(txt.strip())
            await db_put(f"blocked/{target}", True)
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"🚫 بەکارهێنەری <code>{target}</code> بلۆک کرا.", parse_mode="HTML", reply_markup=KB_SEC)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "unblock_user":
        try:
            target = int(txt.strip())
            await db_del(f"blocked/{target}")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"✅ بلۆکی <code>{target}</code> لابرا.", parse_mode="HTML", reply_markup=KB_SEC)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "warn_user_id":
        try:
            target = int(txt.strip())
            await db_put(f"users/{uid}/state", f"warn_user_msg:{target}")
            kb = ReplyKeyboardMarkup([[KeyboardButton("❌ هەڵوەشاندنەوە")]], resize_keyboard=True)
            await update.message.reply_text(f"⚠️ نامەی ئاگادارکردنەوە بنووسە بۆ <code>{target}</code>:", parse_mode="HTML", reply_markup=kb)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state.startswith("warn_user_msg:"):
        target = int(state.split(":",1)[1])
        warns  = await db_get(f"warnings/{target}") or 0
        new_w  = warns + 1
        await db_put(f"warnings/{target}", new_w)
        r = await send_tg(MASTER_TOKEN,"sendMessage",{"chat_id":target,"text":f"⚠️ <b>ئاگادارکردنەوە #{new_w}</b>\n\n{txt}","parse_mode":"HTML"})
        await db_del(f"users/{uid}/state")
        if r.get("ok"):
            await update.message.reply_text(f"✅ ئاگادارکردنەوە #{new_w} نێردرا.", reply_markup=KB_SEC)
        else:
            await update.message.reply_text(f"❌ هەڵە لە ناردن: {r.get('description','')}", reply_markup=KB_SEC)
        return

    if state == "restrict_feat":
        await db_put(f"system/restricted/{txt.strip()}", True)
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(f"🔒 فیچەری <code>{txt}</code> قەدەغەکرا.", parse_mode="HTML", reply_markup=KB_SEC)
        return

    if state == "del_user":
        try:
            target = int(txt.strip())
            await db_del(f"users/{target}")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text(f"🗑 بەکارهێنەری <code>{target}</code> سڕایەوە.", parse_mode="HTML", reply_markup=KB_USERS)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "search_user":
        all_u = await db_get("users") or {}
        results = []
        for u_id, ud in all_u.items():
            if (txt.lower() in ud.get("name","").lower() or
                txt.lower() in ud.get("username","").lower() or
                txt == u_id):
                results.append((u_id, ud))
        await db_del(f"users/{uid}/state")
        if not results:
            await update.message.reply_text("❌ بەکارهێنەرێک نەدۆزرایەوە.", reply_markup=KB_USERS)
            return
        lines = [f"🔍 <b>ئەنجامی گەڕان ({len(results)}):</b>\n"]
        for u_id, ud in results[:10]:
            n  = html.escape(ud.get("name","ناسناو"))
            un = f"@{ud['username']}" if ud.get("username") else "—"
            lines.append(f"• <a href='tg://user?id={u_id}'>{n}</a> {un} <code>{u_id}</code>")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_USERS)
        return

    if state == "user_info_id":
        try:
            target = int(txt.strip())
            ud     = await db_get(f"users/{target}") or {}
            await db_del(f"users/{uid}/state")
            vd     = await db_get(f"vip/{target}")
            bl     = await db_get(f"blocked/{target}")
            warns  = await db_get(f"warnings/{target}") or 0
            adm    = await db_get(f"admins/{target}")
            vip_txt= f"💎 VIP ({vd.get('expires','')})" if vd else "❌ نا-VIP"
            bl_txt = "🚫 بلۆک" if bl else "✅ ئازاد"
            adm_txt = "🛡 ئەدمین" if adm else "👤 ئاسایی"
            msg    = (
                f"👤 <b>زانیاری بەکارهێنەر</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 ID: <code>{target}</code>\n"
                f"📛 ناو: {html.escape(ud.get('name','ناسناو'))}\n"
                f"🔗 یوزەر: @{ud.get('username','—')}\n"
                f"💎 دۆخ: {vip_txt}\n"
                f"🛡 ئەدمین: {adm_txt}\n"
                f"🚫 بلۆک: {bl_txt}\n"
                f"⚠️ ئاگادارکردنەوە: {warns}\n"
                f"🕐 کاتی دوایین چالاکی: {ud.get('last_seen','نییە')}"
            )
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_USERS)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "search_bot":
        all_b = await db_get("managed_bots") or {}
        results = [(k,v) for k,v in all_b.items()
                   if txt.lower() in v.get("bot_username","").lower() or txt == k]
        await db_del(f"users/{uid}/state")
        if not results:
            await update.message.reply_text("❌ بۆتێک نەدۆزرایەوە.", reply_markup=KB_BOTS)
            return
        lines = [f"🔍 <b>ئەنجامی گەڕان ({len(results)}):</b>\n"]
        for bid, bd in results[:10]:
            st  = "🟢" if bd.get("status") == "running" else "🔴"
            own = bd.get("owner","؟")
            lines.append(f"{st} @{bd.get('bot_username','—')}  خاوەن: <code>{own}</code>  ID: <code>{bid}</code>")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_BOTS)
        return

    if state == "owner_del_bot":
        info = await db_get(f"managed_bots/{txt.strip()}")
        await db_del(f"users/{uid}/state")
        if not info:
            await update.message.reply_text("❌ بۆتێک بەم ID ەیە نەدۆزرایەوە.", reply_markup=KB_BOTS)
        else:
            await do_delete_bot(update, uid, txt.strip(), back_kb=KB_BOTS)
        return

    # ── ئەدمین ────────────────────────────────────────────────────────────
    if state == "add_admin" and uid == OWNER_ID:
        try:
            target = int(txt.strip())
            if target == OWNER_ID:
                await update.message.reply_text("⚠️ خاوەنی بۆت پێشەکی ئەدمینی گەورەیە.", reply_markup=KB_ADMINS)
                await db_del(f"users/{uid}/state")
                return
            ud = await db_get(f"users/{target}") or {}
            await db_put(f"admins/{target}", {
                "added_by": uid,
                "date": now_str(),
                "name": ud.get("name","ناسناو"),
            })
            await db_del(f"users/{uid}/state")
            # ئاگادارکردنەوەی ئەدمینی نوێ
            await send_tg(MASTER_TOKEN,"sendMessage",{
                "chat_id": target,
                "text": "‼️ <b>پیرۆزبێت!</b> 🎉\n\nتۆ بوویت بە ئەدمینی بۆتی سیستەم.\n🛡 ئێستا دەستتە بۆ پانێلی ئەدمین.",
                "parse_mode": "HTML"
            })
            await update.message.reply_text(f"✅ بەکارهێنەری <code>{target}</code> بوو بە ئەدمین! 🛡", parse_mode="HTML", reply_markup=KB_ADMINS)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    if state == "del_admin" and uid == OWNER_ID:
        try:
            target = int(txt.strip())
            adm = await db_get(f"admins/{target}")
            await db_del(f"users/{uid}/state")
            if adm:
                await db_del(f"admins/{target}")
                # ئاگادارکردنەوەی ئەدمینی لابراو
                await send_tg(MASTER_TOKEN,"sendMessage",{
                    "chat_id": target,
                    "text": "⚠️ دەستێوەردانی ئەدمینەکەت لابرا.",
                    "parse_mode": "HTML"
                })
                await update.message.reply_text(f"✅ ئەدمینی <code>{target}</code> لابرا.", parse_mode="HTML", reply_markup=KB_ADMINS)
            else:
                await update.message.reply_text(f"❌ بەکارهێنەری <code>{target}</code> ئەدمین نییە.", parse_mode="HTML", reply_markup=KB_ADMINS)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    # ── کانال ────────────────────────────────────────────────────────────
    if state == "change_main_channel":
        await db_put("system/channel", txt.strip().lstrip("@"))
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(f"✅ کانالی سەرەکی گۆڕدرا بۆ: @{txt.strip().lstrip('@')}", reply_markup=KB_CHAN)
        return

    if state == "add_req_channel":
        ch = txt.strip().lstrip("@")
        await db_put(f"system/req_channels/{ch}", True)
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(f"✅ کانالی @{ch} زیادکرا.", reply_markup=KB_CHAN)
        return

    if state == "del_req_channel":
        ch = txt.strip().lstrip("@")
        await db_del(f"system/req_channels/{ch}")
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(f"✅ کانالی @{ch} لابرا.", reply_markup=KB_CHAN)
        return

    if state == "check_member":
        try:
            target  = int(txt.strip())
            req_chs = await db_get("system/req_channels") or {}
            if not req_chs:
                await update.message.reply_text("📭 هیچ کانالی داواکراوێک تۆمار نەکراوە.", reply_markup=KB_CHAN)
                await db_del(f"users/{uid}/state")
                return
            lines = [f"🔍 <b>پشکنینی ئەندامی بەکارهێنەری <code>{target}</code></b>\n"]
            for ch in req_chs:
                res = await send_tg(MASTER_TOKEN,"getChatMember",{"chat_id":f"@{ch}","user_id":target})
                status = res.get("result",{}).get("status","unknown")
                ok = status in ("member","administrator","creator")
                lines.append(f"{'✅' if ok else '❌'} @{ch}: {status}")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_CHAN)
        except:
            await update.message.reply_text("⚠️ ID ی دروست بنووسە.")
        return

    # ── سیستەم ───────────────────────────────────────────────────────────
    if state == "change_project_url":
        await db_put("system/project_url", txt.strip())
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(f"✅ PROJECT URL گۆڕدرا بۆ:\n<code>{txt.strip()}</code>", parse_mode="HTML", reply_markup=KB_SYS)
        return

    if state == "change_dev_channel":
        await db_put("system/dev_channel", txt.strip().lstrip("@"))
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(f"✅ کانالی بەڕێوەبەر گۆڕدرا بۆ @{txt.strip().lstrip('@')}", reply_markup=KB_SYS)
        return

    if state == "change_photo_url":
        await db_put("system/photo_url", txt.strip())
        await db_del(f"users/{uid}/state")
        await update.message.reply_text("✅ وێنەی بەخێرهاتن گۆڕدرا!", reply_markup=KB_SYS)
        return

    if state == "change_master_token":
        await db_put("system/master_token_note", txt.strip()[:10]+"...")
        await db_del(f"users/{uid}/state")
        await update.message.reply_text(
            "⚠️ تۆکێنی سەرەکی لە Vercel Environment Variables دەگۆڕێت، نەک لێرە.\n"
            "تۆکێنەکەت تۆمارکرا، تکایە لە Vercel گۆڕی.",
            reply_markup=KB_SYS,
        )
        return

    if state == "confirm_clear_db":
        if txt == "✅ بەڵێ، پاک بکەرەوە":
            await db_del("users")
            await db_del("managed_bots")
            await db_del("bot_users")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ داتابەیس پاک کرایەوە.", reply_markup=KB_SYS)
        else:
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("↩️ هەڵوەشاندرایەوە.", reply_markup=KB_SYS)
        return

    if state == "confirm_restart":
        await db_del(f"users/{uid}/state")
        if txt == "✅ بەڵێ، ڕیستارت بکە":
            await update.message.reply_text("🔃 ڕیستارت ئەنجامدرا...\n\n⚠️ تێبینی: ڕیستارتی ڕاستەقینە پێویستی بە Vercel CLI ئەکات.", reply_markup=KB_SYS)
        else:
            await update.message.reply_text("↩️ هەڵوەشاندرایەوە.", reply_markup=KB_SYS)
        return

    # ── هەر شتێکی تر ──────────────────────────────────────────────────────
    await update.message.reply_text("تکایە لە کیبۆردی خوارەوە هەڵبژێرە 👇", reply_markup=kb_main(uid))


# ══════════════════════════════════════════════════════════════════════════════
# ── فەنکشنەکانی Owner
# ══════════════════════════════════════════════════════════════════════════════

async def owner_list_users(update: Update, full: bool = False):
    all_u = await db_get("users") or {}
    if not all_u:
        await update.message.reply_text("📭 هیچ بەکارهێنەرێک نییە.", reply_markup=KB_USERS)
        return
    lines = [f"👥 <b>لیستی بەکارهێنەران ({len(all_u)}):</b>\n"]
    for u_id, ud in list(all_u.items())[:50]:
        n  = html.escape(ud.get("name","ناسناو"))
        un = f"@{ud['username']}" if ud.get("username") else "—"
        lines.append(f"• <a href='tg://user?id={u_id}'>{n}</a> {un} <code>{u_id}</code>")
    if len(all_u) > 50:
        lines.append(f"\n... و {len(all_u)-50} بەکارهێنەری تری دیکە")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_USERS)


async def owner_user_stats(update: Update):
    all_u  = await db_get("users")   or {}
    all_v  = await db_get("vip")     or {}
    all_bl = await db_get("blocked") or {}
    all_w  = await db_get("warnings") or {}
    admins = await db_get("admins")  or {}
    vip_ids= set(all_v.keys())
    msg    = (
        "📊 <b>ئامارەکانی بەکارهێنەران</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👥 کۆی بەکارهێنەران: <b>{len(all_u)}</b>\n"
        f"💎 VIPەکان: <b>{len(all_v)}</b>\n"
        f"👨‍💼 ئەدمینەکان: <b>{len(admins)}</b>\n"
        f"🚫 بلۆکەکان: <b>{len(all_bl)}</b>\n"
        f"⚠️ ئاگادارکراوەکان: <b>{len(all_w)}</b>\n"
        f"👤 نا-VIP: <b>{len(all_u) - len([i for i in all_u if i in vip_ids])}</b>"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_USERS)


async def owner_export_users(update: Update):
    all_u = await db_get("users") or {}
    lines = ["ID | ناو | یوزەر | کاتی دوایین چالاکی"]
    for u_id, ud in all_u.items():
        lines.append(f"{u_id} | {ud.get('name','')} | @{ud.get('username','')} | {ud.get('last_seen','')}")
    txt = "\n".join(lines)
    msg = f"📤 <b>لیستی بەکارهێنەران ({len(all_u)}):</b>\n\n<code>{html.escape(txt[:3500])}</code>"
    if len(all_u) > 60:
        msg += f"\n\n... و {len(all_u)-60} بەکارهێنەری دیکە"
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_USERS)


async def owner_list_bots(update: Update, filter_status=None):
    all_b = await db_get("managed_bots") or {}
    if filter_status:
        all_b = {k:v for k,v in all_b.items() if v.get("status") == filter_status}
    if not all_b:
        await update.message.reply_text("📭 هیچ بۆتێک نییە.", reply_markup=KB_BOTS)
        return
    lines = [f"🤖 <b>بۆتەکان ({len(all_b)}):</b>\n"]
    for bid, bd in list(all_b.items())[:40]:
        st  = "🟢" if bd.get("status") == "running" else "🔴"
        own = bd.get("owner","؟")
        bu  = await db_get(f"bot_users/{bid}") or {}
        lines.append(f"{st} @{bd.get('bot_username','—')}  👥{len(bu)}  خاوەن:<code>{own}</code>  ID:<code>{bid}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_BOTS)


async def owner_bot_stats(update: Update):
    all_b = await db_get("managed_bots") or {}
    run   = sum(1 for v in all_b.values() if v.get("status") == "running")
    total_users = 0
    for bid in all_b:
        bu = await db_get(f"bot_users/{bid}") or {}
        total_users += len(bu)
    msg = (
        "📊 <b>ئامارەکانی بۆتەکان</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 کۆی بۆتەکان: <b>{len(all_b)}</b>\n"
        f"🟢 چالاک: <b>{run}</b>\n"
        f"🔴 ڕاگیراو: <b>{len(all_b)-run}</b>\n"
        f"👥 کۆی بەکارهێنەران: <b>{total_users}</b>"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_BOTS)


async def owner_all_bots_action(update: Update, new_status: str):
    all_b = await db_get("managed_bots") or {}
    count = 0
    for bid, bd in all_b.items():
        bd["status"] = new_status
        await db_put(f"managed_bots/{bid}", bd)
        count += 1
    icon = "🟢" if new_status == "running" else "🔴"
    await update.message.reply_text(f"{icon} <b>{count}</b> بۆت {('دەستی پێکرد' if new_status=='running' else 'وەستاندرا')}.", parse_mode="HTML", reply_markup=KB_BOTS)


async def owner_list_vips(update: Update):
    all_v = await db_get("vip") or {}
    if not all_v:
        await update.message.reply_text("📭 هیچ VIPێک نییە.", reply_markup=KB_VIP)
        return
    lines = [f"💎 <b>لیستی VIPەکان ({len(all_v)}):</b>\n"]
    for v_id, vd in list(all_v.items())[:40]:
        exp = vd.get("expires","نییە")
        lines.append(f"• <code>{v_id}</code> ⏰ {exp}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_VIP)


async def owner_vip_stats(update: Update):
    all_v = await db_get("vip") or {}
    life  = sum(1 for v in all_v.values() if v.get("expires") == "lifetime")
    timed = len(all_v) - life
    msg   = (
        "📊 <b>ئامارەکانی VIP</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"💎 کۆی VIPەکان: <b>{len(all_v)}</b>\n"
        f"♾ هەمیشەیی: <b>{life}</b>\n"
        f"⏰ کاتی دیاریکراو: <b>{timed}</b>"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_VIP)


async def owner_list_blocked(update: Update):
    all_bl = await db_get("blocked") or {}
    if not all_bl:
        await update.message.reply_text("📭 هیچ بلۆکێک نییە.", reply_markup=KB_SEC)
        return
    lines = [f"🚫 <b>بلۆکەکان ({len(all_bl)}):</b>\n"]
    for bid in list(all_bl.keys())[:40]:
        lines.append(f"• <code>{bid}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_SEC)


async def owner_list_warned(update: Update):
    all_w = await db_get("warnings") or {}
    if not all_w:
        await update.message.reply_text("📭 هیچ ئاگادارکراوێک نییە.", reply_markup=KB_SEC)
        return
    lines = [f"⚠️ <b>ئاگادارکراوەکان ({len(all_w)}):</b>\n"]
    for w_id, cnt in list(all_w.items())[:40]:
        lines.append(f"• <code>{w_id}</code> — ⚠️ {cnt} جار")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_SEC)


async def owner_toggle_alert_mode(update: Update, uid: int):
    cur = await db_get("system/alert_mode") or False
    await db_put("system/alert_mode", not cur)
    state = "چالاک ✅" if not cur else "لەکارخراو ❌"
    await update.message.reply_text(f"🛡 مۆدی ئاگادارکردنەوە: <b>{state}</b>", parse_mode="HTML", reply_markup=KB_SEC)


async def owner_list_channels(update: Update):
    main_ch = await db_get("system/channel") or CHANNEL_USER
    req_chs = await db_get("system/req_channels") or {}
    fj      = await db_get("system/force_join") or False
    msg     = (
        "📢 <b>زانیاری جۆینی ناچاری</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📢 کانالی سەرەکی بۆتەکان: @{main_ch}\n"
        f"🔔 دۆخی جۆینی ناچاری: <b>{'✅ چالاک' if fj else '❌ لەکارخراو'}</b>\n\n"
        f"📋 <b>کانالە داواکراوەکان ({len(req_chs)}):</b>\n"
    )
    if req_chs:
        for i, ch in enumerate(req_chs, 1):
            msg += f"  {i}. 🔗 @{ch} — <a href='https://t.me/{ch}'>لینک</a>\n"
    else:
        msg += "  📭 هیچ کانالێک زیادنەکراوە\n"
    msg += "\n💡 جۆینی ناچاری کاردەکات کاتێک بەکارهێنەر /start بکات"
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_CHAN)


async def owner_channel_stats(update: Update):
    req_chs = await db_get("system/req_channels") or {}
    fj      = await db_get("system/force_join")   or False
    all_u   = await db_get("users") or {}
    msg     = (
        "📊 <b>ئامارەکانی جۆینی ناچاری</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 دۆخ: <b>{'✅ چالاک' if fj else '❌ لەکارخراو'}</b>\n"
        f"📋 کانالە داواکراوەکان: <b>{len(req_chs)}</b>\n"
        f"👥 کۆی بەکارهێنەران: <b>{len(all_u)}</b>\n\n"
        f"📌 کاتێک چالاکە: هەر بەکارهێنەرێک /start بکات، پشکنینی دەکرێت"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_CHAN)


# ── فەنکشنەکانی ئەدمین ───────────────────────────────────────────────────────
async def owner_list_admins(update: Update):
    admins = await db_get("admins") or {}
    if not admins:
        await update.message.reply_text("📭 هیچ ئەدمینێک نییە.", reply_markup=KB_ADMINS)
        return
    lines = [f"👨‍💼 <b>لیستی ئەدمینەکان ({len(admins)}):</b>\n"]
    for a_id, ad in list(admins.items())[:40]:
        name = html.escape(ad.get("name","ناسناو"))
        date = ad.get("date","نییە")
        lines.append(f"• <a href='tg://user?id={a_id}'>{name}</a> <code>{a_id}</code> — زیادکرا: {date}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_ADMINS)


async def owner_admin_stats(update: Update):
    admins = await db_get("admins") or {}
    msg = (
        "📊 <b>ئامارەکانی ئەدمینەکان</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💼 کۆی ئەدمینەکان: <b>{len(admins)}</b>\n"
        f"👑 خاوەنی سیستەم: <b>1</b> (سەرەکی)"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_ADMINS)


# ── فەنکشنەکانی ئاگادارکردنەوە ──────────────────────────────────────────────
async def owner_notif_history(update: Update):
    hist = await db_get("system/notif_history") or []
    if not hist:
        await update.message.reply_text("📭 هیچ مێژووی ئاگادارکردنەوەیەک نییە.", reply_markup=KB_NOTIF)
        return
    if isinstance(hist, dict): hist = list(hist.values())
    lines = ["📋 <b>مێژووی ئاگادارکردنەوە:</b>\n"]
    for h in hist[:15]:
        tp   = h.get("type","—")
        sent = h.get("sent",0)
        fail = h.get("fail",0)
        tm   = h.get("time","—")
        lines.append(f"🔔 {tm} | {tp} | ✅{sent} ❌{fail}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_NOTIF)


async def show_user_notifications(update: Update, uid: int):
    """نیشاندانی ئاگادارکردنەوەکانی بەکارهێنەر"""
    notif_on = await db_get("system/notifications_enabled")
    user_notif = await db_get(f"users/{uid}/notifications_off") or False
    msg = (
        "🔔 <b>ئاگادارکردنەوەکانت</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📢 دۆخی سیستەم: {'✅ چالاک' if notif_on else '❌ لەکارخراو'}\n"
        f"👤 ئاگادارکردنەوەی تۆ: {'❌ کوژاوە' if user_notif else '✅ چالاک'}\n"
    )
    kb = ReplyKeyboardMarkup([
        [KeyboardButton("🔕 کوژاندنەوەی ئاگادارکردنەوەم" if not user_notif else "🔔 چالاككردنی ئاگادارکردنەوەم")],
        [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")],
    ], resize_keyboard=True)
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)


async def owner_sys_info(update: Update):
    all_b  = await db_get("managed_bots") or {}
    all_u  = await db_get("users")         or {}
    admins = await db_get("admins")        or {}
    run    = sum(1 for v in all_b.values() if v.get("status") == "running")
    purl   = await db_get("system/project_url") or PROJECT_URL or "نەدۆزرایەوە"
    fj     = await db_get("system/force_join")  or False
    am     = await db_get("system/alert_mode")  or False
    notif  = await db_get("system/notifications_enabled") or False
    msg    = (
        f"⚙️ <b>زانیاری سیستەم</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 PROJECT URL: <code>{purl}</code>\n"
        f"👥 بەکارهێنەران: <b>{len(all_u)}</b>\n"
        f"🤖 بۆتەکان: <b>{len(all_b)}</b>  (🟢{run})\n"
        f"👨‍💼 ئەدمینەکان: <b>{len(admins)}</b>\n"
        f"📢 جۆینی ناچاری: <b>{'چالاک' if fj else 'لەکارخراو'}</b>\n"
        f"🛡 مۆدی ئاگادارکردنەوە: <b>{'چالاک' if am else 'لەکارخراو'}</b>\n"
        f"🔔 ئاگادارکردنەوەکان: <b>{'چالاک' if notif else 'لەکارخراو'}</b>\n"
        f"⏰ کاتی ئێستا: <b>{now_str()}</b>"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_SYS)


async def owner_refresh_all_webhooks(update: Update):
    all_b = await db_get("managed_bots") or {}
    sm    = await update.message.reply_text(f"⏳ نوێکردنەوەی {len(all_b)} وەبهووک...")
    ok=fail=0
    safe  = (PROJECT_URL or "").rstrip('/')
    for bid, bd in all_b.items():
        if bd.get("status") != "running": continue
        token = bd.get("token","")
        if not token: continue
        r = await send_tg(token,"setWebhook",{"url":f"{safe}/api/bot/{token}","allowed_updates":["message","channel_post"]})
        if r.get("ok"): ok+=1
        else: fail+=1
        await asyncio.sleep(0.1)
    await sm.edit_text(f"✅ وەبهووک نوێکرایەوە!\n✅ سەرکەوتوو: {ok}  ❌ هەڵە: {fail}", reply_markup=KB_SYS)


async def owner_backup_db(update: Update):
    all_b  = await db_get("managed_bots") or {}
    all_u  = await db_get("users")         or {}
    all_v  = await db_get("vip")           or {}
    admins = await db_get("admins")        or {}
    backup = {
        "time":         now_str(),
        "users_count":  len(all_u),
        "bots_count":   len(all_b),
        "vip_count":    len(all_v),
        "admin_count":  len(admins),
        "bot_usernames":[v.get("bot_username","") for v in all_b.values()],
    }
    msg = (
        "💾 <b>پشتگیری داتابەیس</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ کات: {backup['time']}\n"
        f"👥 بەکارهێنەران: {backup['users_count']}\n"
        f"🤖 بۆتەکان: {backup['bots_count']}\n"
        f"💎 VIPەکان: {backup['vip_count']}\n"
        f"👨‍💼 ئەدمینەکان: {backup['admin_count']}\n"
        f"🤖 ناوی بۆتەکان:\n<code>{', '.join(backup['bot_usernames'][:20])}</code>"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_SYS)


async def owner_show_logs(update: Update):
    logs = await db_get("system/logs") or []
    if not logs:
        await update.message.reply_text("📭 هیچ لۆگێک نییە.", reply_markup=KB_SYS)
        return
    if isinstance(logs, dict): logs = list(logs.values())
    lines = ["📋 <b>دوایین لۆگەکان:</b>\n"]
    for log in logs[:15]:
        lines.append(f"• {log}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_SYS)


async def owner_broadcast_history(update: Update):
    hist = await db_get("system/bc_history") or []
    if not hist:
        await update.message.reply_text("📭 هیچ مێژووی بڵاوکردنەوە نییە.", reply_markup=KB_MSG)
        return
    if isinstance(hist, dict): hist = list(hist.values())
    lines = ["📜 <b>مێژووی بڵاوکردنەوە:</b>\n"]
    for h in hist[:15]:
        tp   = h.get("type","—")
        sent = h.get("sent",0)
        fail = h.get("fail",0)
        tm   = h.get("time","—")
        lines.append(f"📤 {tm} | {tp} | ✅{sent} ❌{fail}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=KB_MSG)


# ══════════════════════════════════════════════════════════════════════════════
# ── چالاككردنی تۆکێن
# ══════════════════════════════════════════════════════════════════════════════
async def activate_token(update: Update, uid: int, token: str):
    sm = await update.message.reply_text("⏳ خەریکی پشکنین و چالاككردنم...")
    try:
        res = await send_tg(token,"getMe",{})
        if not res.get("ok"):
            await sm.edit_text("❌ تۆکێنەکە هەڵەیە یان کار ناکات.")
            return
        bi  = res["result"]
        bid = str(bi["id"])
        bun = bi["username"]
        bnm = bi["first_name"]
        if await db_get(f"managed_bots/{bid}"):
            await sm.edit_text(f"⚠️ بۆتی @{bun} پێشتر تۆمارکراوە!")
            return
        safe = (PROJECT_URL or "").rstrip('/')
        wh   = await send_tg(token,"setWebhook",{"url":f"{safe}/api/bot/{token}","allowed_updates":["message","channel_post"]})
        if not wh.get("ok"):
            await sm.edit_text("❌ هەڵەیەک ڕوویدا لە بەستنەوەی وەبهووک.")
            return
        await db_put(f"managed_bots/{bid}",{
            "token":token,"owner":uid,"bot_username":bun,
            "bot_name":bnm,"status":"running","type":"reaction","welcome_msg":"",
        })
        await db_del(f"users/{uid}/state")
        await sm.edit_text(
            f"‏✅ <b>بۆتەکەت سەرکەوتووانە دروست کرا!</b>\n\n"
            f"🤖 ناو: {html.escape(bnm)}\n🔗 یوزەر: @{bun}\n🆔 ID: <code>{bid}</code>\n\n"
            "📌 زیادی بکە بۆ گروپ/کانالت و ئادمینی بکە ✅",
            parse_mode="HTML",
        )
        await update.message.reply_text("📂 لە 'بۆتەکانم' کۆنترۆڵی بکە:", reply_markup=kb_main(uid))
    except Exception as e:
        logger.error(f"activate: {e}")
        await sm.edit_text(f"❌ هەڵەیەکی چاوەڕواننەکراو:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# ── سڕینەوەی بۆت
# ══════════════════════════════════════════════════════════════════════════════
async def do_delete_bot(update: Update, uid: int, bid: str, back_kb=None):
    info  = await db_get(f"managed_bots/{bid}") or {}
    un    = info.get("bot_username","ناسناو")
    token = info.get("token","")
    if token:
        try: await send_tg(token,"deleteWebhook",{})
        except: pass
    await db_del(f"managed_bots/{bid}")
    await db_del(f"users/{uid}/selected_bot")
    await db_del(f"users/{uid}/state")
    kb = back_kb if back_kb else kb_main(uid)
    await update.message.reply_text(f"🗑 <b>بۆتی @{un} بە تەواوی سڕایەوە!</b>", parse_mode="HTML", reply_markup=kb)


# ══════════════════════════════════════════════════════════════════════════════
# ── بۆتی منداڵ (Child Bot)
# ══════════════════════════════════════════════════════════════════════════════
async def process_child_update(token: str, body: dict):
    try:
        bid  = token.split(":")[0]
        info = await db_get(f"managed_bots/{bid}")
        if not info or info.get("status") != "running": return

        bun  = info.get("bot_username","UnknownBot")
        bnm  = info.get("bot_name","Reaction Bot")
        wlcm = info.get("welcome_msg","")

        sys_photo = await db_get("system/photo_url") or PHOTO_URL
        sys_chan  = await db_get("system/channel")   or CHANNEL_USER
        req_chs   = await db_get("system/req_channels") or {}
        fj        = await db_get("system/force_join") or False

        msg = body.get("message") or body.get("channel_post")
        if not msg: return

        chat_id    = msg["chat"]["id"]
        message_id = msg["message_id"]
        txt        = msg.get("text","")

        from_user = msg.get("from") or msg.get("sender_chat") or {}
        user_name = html.escape(from_user.get("first_name") or from_user.get("title") or "بەکارهێنەر")
        user_id   = from_user.get("id", chat_id)

        if from_user.get("id"):
            is_new_user = not await db_get(f"bot_users/{bid}/{user_id}")
            await db_patch(f"bot_users/{bid}/{user_id}", {"name": from_user.get("first_name",""), "chat_id": chat_id})
            # ئاگادارکردنەوەی خاوەنی بۆت کاتی بەکارهێنەری نوێ
            if is_new_user and txt.startswith("/start"):
                owner_uid = info.get("owner")
                if owner_uid:
                    R = "\u200f"
                    uname_str = f"@{from_user.get('username')}" if from_user.get("username") else "—"
                    notif_msg = (
                        f"{R}🔔 <b>بەکارهێنەری نوێ!</b>\n"
                        f"{R}━━━━━━━━━━━━━━━━━━━\n"
                        f"{R}👤 ناو: <a href='tg://user?id={user_id}'>{user_name}</a>\n"
                        f"{R}🆔 ID: <code>{user_id}</code>\n"
                        f"{R}🔗 یوزەر: {uname_str}\n"
                        f"{R}🤖 بۆت: @{bun}\n"
                        f"{R}⏰ کات: {now_str()}\n"
                        f"{R}━━━━━━━━━━━━━━━━━━━"
                    )
                    try:
                        await send_tg(MASTER_TOKEN, "sendMessage", {
                            "chat_id": owner_uid,
                            "text": notif_msg,
                            "parse_mode": "HTML"
                        })
                    except: pass

        async with httpx.AsyncClient(timeout=10) as c:
            if txt.startswith("/start"):
                # پشکنینی جۆینی ناچاری کەناڵ
                if fj and req_chs and from_user.get("id"):
                    not_joined = []
                    for ch in req_chs:
                        try:
                            res = await send_tg(token, "getChatMember", {"chat_id": f"@{ch}", "user_id": user_id})
                            status = res.get("result", {}).get("status", "left")
                            if status not in ("member","administrator","creator"):
                                not_joined.append(ch)
                        except:
                            not_joined.append(ch)
                    if not_joined:
                        kb_rows = [[{"text": f"📢 ئەندامبوون لە @{ch}", "url": f"https://t.me/{ch}"}] for ch in not_joined]
                        join_msg = "‼️ <b>تکایە سەرەتا ئەندامی کانالەکانمان بە:</b>\n\n"
                        for ch in not_joined:
                            join_msg += f"• @{ch}\n"
                        await c.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                            "chat_id": chat_id,
                            "text": join_msg,
                            "parse_mode": "HTML",
                            "reply_markup": {"inline_keyboard": kb_rows},
                        })
                        return

                notice = await db_get("system/notice")

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
                if notice:
                    caption += f"\n\n📌 <b>تێبینی:</b> {notice}"

                keyboard = {"inline_keyboard": [
                    [{"text":"📢 کانالی بەڕێوەبەر","url":f"https://t.me/{sys_chan}"}],
                    [
                        {"text":"➕ زیادکردن بۆ گروپ", "url":f"https://t.me/{bun}?startgroup=new"},
                        {"text":"➕ زیادکردن بۆ کانال","url":f"https://t.me/{bun}?startchannel=new"},
                    ],
                    [{"text":"👨‍💻 بەرنامەنووس","url":f"tg://user?id={OWNER_ID}"}],
                ]}
                await c.post(f"https://api.telegram.org/bot{token}/sendPhoto", json={
                    "chat_id":chat_id,"photo":sys_photo,"caption":caption,
                    "parse_mode":"HTML","reply_markup":keyboard,"reply_to_message_id":message_id,
                })
            else:
                emoji = random.choice(EMOJIS)
                await c.post(f"https://api.telegram.org/bot{token}/setMessageReaction", json={
                    "chat_id":chat_id,"message_id":message_id,
                    "reaction":[{"type":"emoji","emoji":emoji}],"is_big":False,
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
    return {"status":"active","keep_alive":"✅"}
