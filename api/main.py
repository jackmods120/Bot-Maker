import os, logging, httpx, asyncio, random, html, re, json
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
EMOJIS       =["❤️","🔥","🎉","👏","🤩","💯","😍","🫶","⚡","🌟"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app    = FastAPI()

# ══════════════════════════════════════════════════════════════════════════════
# ── داتابەیس و خێرایی (Optimized)
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
# ── KEEP-ALIVE (بۆ ئەوەی هەرگیز بۆتەکە نەخەوێت)
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
    if uid == OWNER_ID: return True
    admins = await db_get("system/admins") or {}
    return str(uid) in admins

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

async def check_force_join(uid: int, bot_obj):
    # VIP و ئەدمین پێویستیان بە جۆین نییە (خێرایی زیاتر)
    if await is_admin(uid) or await is_vip(uid): return True,[]
    
    req_chs = await db_get("system/req_channels") or {}
    is_active = await db_get("system/force_join")
    if not is_active or not req_chs: return True, []
    
    missing =[]
    for ch in req_chs.keys():
        try:
            member = await bot_obj.get_chat_member(f"@{ch}", uid)
            if member.status in ['left', 'kicked', 'banned']:
                missing.append(ch)
        except: pass
    return len(missing) == 0, missing

# ══════════════════════════════════════════════════════════════════════════════
# ██  کیبۆردەکان (بە کوردی پەتی و ڕێکخراو)
# ══════════════════════════════════════════════════════════════════════════════

def kb_main(uid: int, is_adm: bool, notif_on: bool) -> ReplyKeyboardMarkup:
    notif_btn = "🔔 ئاگادارکردنەوە: چالاک" if notif_on else "🔕 ئاگادارکردنەوە: ناچالاک"
    if is_adm:
        return ReplyKeyboardMarkup([[KeyboardButton("➕ دروستکردنی بۆتی نوێ"),  KeyboardButton("📂 بۆتەکانم")],[KeyboardButton("👑 پانێلی سەرەکی"),         KeyboardButton("📊 ئامارەکان")],
            [KeyboardButton(notif_btn)]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([[KeyboardButton("➕ دروستکردنی بۆتی نوێ"), KeyboardButton("📂 بۆتەکانم")],[KeyboardButton("📊 ئامارەکانم"), KeyboardButton(notif_btn)],
    ], resize_keyboard=True)

def kb_control(is_adm: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton("▶️ دەستپێکردن"),      KeyboardButton("⏸ وەستاندن")],[KeyboardButton("🔄 نوێکردنەوە"),       KeyboardButton("📋 زانیاری بۆت")],[KeyboardButton("✏️ گۆڕینی بەخێرهاتن"), KeyboardButton("📨 پەیام بۆ بەکارهێنەران")],[KeyboardButton("🗑 سڕینەوەی بۆت"),     KeyboardButton("🔙 گەڕانەوە بۆ لیست")],
    ]
    if is_adm:
        rows.insert(3,[KeyboardButton("🔑 گۆڕینی تۆکێن"), KeyboardButton("🔗 نوێکردنەوەی وەبهووک")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

KB_OWNER_MAIN = ReplyKeyboardMarkup([[KeyboardButton("👥 بەشی بەکارهێنەران"),   KeyboardButton("🤖 بەشی بۆتەکان")],[KeyboardButton("📨 بەشی پەیام"),           KeyboardButton("💎 بەشی VIP")],[KeyboardButton("🛡 بەشی ئەمنیەت"),         KeyboardButton("📢 بەشی کانال")],[KeyboardButton("⚙️ بەشی سیستەم"),          KeyboardButton("📊 ئامارەکان")],
    [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")],
], resize_keyboard=True)

KB_USERS = ReplyKeyboardMarkup([[KeyboardButton("👥 لیستی هەموو بەکارهێنەران"), KeyboardButton("🔍 گەڕان بۆ بەکارهێنەر")],[KeyboardButton("📋 زانیاری بەکارهێنەر بە ID"), KeyboardButton("📊 ئامارەکانی بەکارهێنەران")],[KeyboardButton("🗑 سڕینەوەی بەکارهێنەر"),     KeyboardButton("📤 هەناردەکردنی لیست")],[KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

KB_BOTS = ReplyKeyboardMarkup([[KeyboardButton("🤖 لیستی هەموو بۆتەکان"),   KeyboardButton("🟢 بۆتە چالاکەکان")],[KeyboardButton("🔴 بۆتە ڕاگیراوەکان"),       KeyboardButton("📊 ئامارەکانی بۆتەکان")],[KeyboardButton("▶️ دەستپێکردنی هەموو"),       KeyboardButton("⏸ وەستاندنی هەموو")],[KeyboardButton("🗑 سڕینەوەی بۆت بە ID"),      KeyboardButton("🔍 گەڕان بۆ بۆت")],[KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

KB_MSG = ReplyKeyboardMarkup([[KeyboardButton("📨 بڵاوکردنەوە بۆ هەموو"),    KeyboardButton("📨 بڵاوکردنەوە بۆ VIP")],[KeyboardButton("📨 بڵاوکردنەوە بۆ نا-VIP"),   KeyboardButton("📬 پەیام بۆ بەکارهێنەرێک")],[KeyboardButton("📌 دانانی پەیامی سیستەم"),     KeyboardButton("🗑 سڕینەوەی پەیامی سیستەم")],[KeyboardButton("📋 پەیامی سیستەمی ئێستا"),     KeyboardButton("📜 مێژووی بڵاوکردنەوە")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

KB_VIP = ReplyKeyboardMarkup([[KeyboardButton("💎 لیستی VIPەکان"),            KeyboardButton("➕ زیادکردنی VIP")],[KeyboardButton("➖ لابردنی VIP"),               KeyboardButton("📊 ئامارەکانی VIP")],[KeyboardButton("💎 VIP بۆ کاتی دیاریکراو"),    KeyboardButton("💎 VIP بۆ هەمیشەیی")],[KeyboardButton("🔍 پشکنینی VIP بەکارهێنەر"),   KeyboardButton("🗑 سڕینەوەی هەموو VIP")],[KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

KB_SEC = ReplyKeyboardMarkup([[KeyboardButton("🚫 بلۆک کردنی بەکارهێنەر"),    KeyboardButton("✅ لابردنی بلۆک")],[KeyboardButton("📋 لیستی بلۆکەکان"),            KeyboardButton("🗑 سڕینەوەی هەموو بلۆک")],[KeyboardButton("⚠️ ئاگادارکردنەوەی بەکارهێنەر"),KeyboardButton("🔒 قەدەغەکردنی فیچەر")],[KeyboardButton("🛡 مۆدی ئاگادارکردنەوە"),       KeyboardButton("📋 لیستی ئاگادارکراوەکان")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

KB_CHAN = ReplyKeyboardMarkup([[KeyboardButton("📢 گۆڕینی کانالی سەرەکی"),     KeyboardButton("➕ زیادکردنی کانالی داواکراو")],[KeyboardButton("➖ لابردنی کانالی داواکراو"),   KeyboardButton("📋 لیستی کانالەکان")],[KeyboardButton("✅ چالاککردنی داواکردنی کانال"),KeyboardButton("❌ لەکارخستنی داواکردن")],[KeyboardButton("🔍 پشکنینی ئەندامی کانال"),    KeyboardButton("📊 ئامارەکانی کانال")],
    [KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

KB_SYS = ReplyKeyboardMarkup([[KeyboardButton("➕ زیادکردنی ئەدمین"),          KeyboardButton("➖ لابردنی ئەدمین")],[KeyboardButton("📋 لیستی ئەدمینەکان"),          KeyboardButton("⚙️ زانیاری سیستەم")],[KeyboardButton("🗑 پاككردنی داتابەیس"),          KeyboardButton("💾 پشتگیری داتابەیس")],[KeyboardButton("📝 گۆڕینی بۆتی سەرەکی"),        KeyboardButton("🌐 گۆڕینی PROJECT URL")],
    [KeyboardButton("📋 لۆگەکان"),                    KeyboardButton("🔃 ڕیستارتی سیستەم")],[KeyboardButton("🔄 نوێکردنەوەی هەموو وەبهووک"), KeyboardButton("🖼 گۆڕینی وێنەی بەخێرهاتن")],[KeyboardButton("🔙 گەڕانەوە بۆ پانێلی سەرەکی")],
], resize_keyboard=True)

# ══════════════════════════════════════════════════════════════════════════════
# ██  /start
# ══════════════════════════════════════════════════════════════════════════════
async def master_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = html.escape(update.effective_user.first_name or "بەکارهێنەر")
    is_adm = await is_admin(uid)

    if await is_blocked(uid):
        await update.message.reply_text("🚫 دەستت لە بۆتەکە گرتراوە.")
        return

    # پشکنینی جۆینی ناچاری
    joined, missing = await check_force_join(uid, ctx.bot)
    if not joined:
        btn = [[InlineKeyboardButton(f"📢 کەناڵی {ch}", url=f"https://t.me/{ch}")] for ch in missing]
        await update.message.reply_text("⚠️ <b>تکایە سەرەتا جۆینی ئەم کەناڵانە بکە پاشان /start بکە:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn))
        return

    await db_del(f"users/{uid}/state")
    await db_patch(f"users/{uid}", {
        "name":     update.effective_user.first_name or "",
        "username": update.effective_user.username   or "",
        "active":   True,
        "last_seen": now_str(),
    })

    user_data = await db_get(f"users/{uid}") or {}
    notif_on = user_data.get("notifications", True)
    vip_badge = " 💎" if await is_vip(uid) else ""

    if is_adm:
        txt = (
            f"👑 <b>بەخێربێیت بەڕێوەبەر، {name}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎛 پانێلی سەرەکی — کۆنترۆڵی تەواوی سیستەم\n"
            "👇 هەڵبژاردنێک بکە لە خوارەوە:"
        )
    else:
        txt = (
            f"👋 <b>بەخێربێیت، {name}{vip_badge}!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 دروستکردنی بۆتی تایبەتی خۆت\n"
            "⚙️ کۆنترۆڵی تەواوی بۆتەکەت\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 لە کیبۆردی خوارەوە هەڵبژێرە:"
        )

    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main(uid, is_adm, notif_on))

# ══════════════════════════════════════════════════════════════════════════════
# ██  هەندڵەری سەرەکی (پەیام و وێنە)
# ══════════════════════════════════════════════════════════════════════════════
async def handle_all_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    state = await db_get(f"users/{uid}/state") or ""
    is_adm = await is_admin(uid)

    if await is_blocked(uid):
        return

    # پشکنینی جۆین پێش وەڵامدانەوە
    joined, missing = await check_force_join(uid, ctx.bot)
    if not joined:
        btn = [[InlineKeyboardButton(f"📢 کەناڵی {ch}", url=f"https://t.me/{ch}")] for ch in missing]
        await update.message.reply_text("⚠️ <b>تکایە سەرەتا جۆینی ئەم کەناڵانە بکە:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn))
        return

    user_data = await db_get(f"users/{uid}") or {}
    notif_on = user_data.get("notifications", True)

    # ── وەرگرتنی وێنە بە ڕاستەوخۆیی (بۆ بەخێرهاتن) ──
    if update.message.photo:
        if state == "change_photo_url" and is_adm:
            photo_id = update.message.photo[-1].file_id
            await db_put("system/photo_id", photo_id) # خەزنکردنی IDی وێنەکە
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ <b>وێنەی بەخێرهاتن بە سەرکەوتوویی گۆڕدرا!</b>", parse_mode="HTML", reply_markup=KB_SYS)
        return

    txt = update.message.text
    if not txt: return
    txt = txt.strip()

    # ── ناڤیگەیشنی گشتی ───────────────────────────────────────────────────
    if txt == "❌ هەڵوەشاندنەوە" or txt == "🔙 گەڕانەوە بۆ سەرەتا":
        await db_del(f"users/{uid}/state")
        await master_start(update, ctx)
        return

    if txt == "🔙 گەڕانەوە بۆ لیست":
        await db_del(f"users/{uid}/state")
        await show_bot_list(update, uid, is_adm, notif_on)
        return

    if txt == "🔙 گەڕانەوە بۆ پانێلی سەرەکی" and is_adm:
        await db_del(f"users/{uid}/state")
        await show_owner_main(update)
        return

    # ── ئاگادارکردنەوەکان ─────────────────────────────────────────────────
    if "ئاگادارکردنەوە:" in txt:
        new_status = not notif_on
        await db_patch(f"users/{uid}", {"notifications": new_status})
        st_text = "چالاک کرا ✅" if new_status else "ناچالاک کرا 🔕"
        await update.message.reply_text(f"زەنگی ئاگادارکردنەوە {st_text}.", reply_markup=kb_main(uid, is_adm, new_status))
        return

    # ── دروستکردنی بۆتی نوێ ───────────────────────────────────────────────
    if txt == "➕ دروستکردنی بۆتی نوێ":
        kb = ReplyKeyboardMarkup([[KeyboardButton("🍓 بۆتی ڕیاکشن")], [KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text("🤖 <b>جۆری بۆت هەڵبژێرە:</b>\n\n🍓 <b>بۆتی ڕیاکشن</b> — بۆ هەموو نامەیەک ئیموجی دەنێرێت", parse_mode="HTML", reply_markup=kb)
        return

    if txt == "🍓 بۆتی ڕیاکشن":
        await db_put(f"users/{uid}/state", "await_token")
        kb = ReplyKeyboardMarkup([[KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")]], resize_keyboard=True)
        await update.message.reply_text("🍓 <b>دروستکردنی بۆتی ڕیاکشن</b>\n\nبچۆ بۆ @BotFather و تۆکێنەکەی کۆپی بکە و لێرە بینێرە:", parse_mode="HTML", reply_markup=kb)
        return

    # ── لیستی بۆتەکانم ────────────────────────────────────────────────────
    if txt == "📂 بۆتەکانم":
        await show_bot_list(update, uid, is_adm, notif_on)
        return

    # ── هەڵبژاردنی بۆت ───────────────────────────────────────────────────
    if re.match(r"^[🟢🔴] @\S+$", txt):
        uname = re.sub(r"^[🟢🔴] @", "", txt).strip()
        all_b = await db_get("managed_bots") or {}
        bid   = next((k for k, v in all_b.items() if v.get("owner") == uid and v.get("bot_username") == uname), None)
        if not bid:
            await update.message.reply_text("❌ بۆتەکە نەدۆزرایەوە!")
            return
        await db_put(f"users/{uid}/selected_bot", bid)
        await show_bot_control(update, uid, bid, all_b[bid], is_adm)
        return

    # ── دوگمەکانی کۆنترۆڵ ────────────────────────────────────────────────
    CTRL = {"▶️ دەستپێکردن","⏸ وەستاندن","🔄 نوێکردنەوە","📋 زانیاری بۆت", "✏️ گۆڕینی بەخێرهاتن","📨 پەیام بۆ بەکارهێنەران", "🗑 سڕینەوەی بۆت","🔑 گۆڕینی تۆکێن","🔗 نوێکردنەوەی وەبهووک"}
    if txt in CTRL:
        await handle_control(update, uid, txt, is_adm, notif_on)
        return

    if txt in ("📊 ئامارەکان", "📊 ئامارەکانم"):
        await show_stats(update, uid, is_adm, notif_on)
        return

    # ════════════════════════════════════════════════════════════════════════
    # پانێلی سەرەکی و بەشەکانی (تەنها ئەدمین و خاوەن)
    # ════════════════════════════════════════════════════════════════════════
    if is_adm:
        if txt == "👑 پانێلی سەرەکی": await show_owner_main(update); return

        if txt == "👥 بەشی بەکارهێنەران": await update.message.reply_text("👥 <b>بەشی بەکارهێنەران</b>", parse_mode="HTML", reply_markup=KB_USERS); return
        if txt == "🤖 بەشی بۆتەکان": await update.message.reply_text("🤖 <b>بەشی بۆتەکان</b>", parse_mode="HTML", reply_markup=KB_BOTS); return
        if txt == "📨 بەشی پەیام": await update.message.reply_text("📨 <b>بەشی پەیام</b>", parse_mode="HTML", reply_markup=KB_MSG); return
        if txt == "💎 بەشی VIP": await update.message.reply_text("💎 <b>بەشی VIP</b>", parse_mode="HTML", reply_markup=KB_VIP); return
        if txt == "🛡 بەشی ئەمنیەت": await update.message.reply_text("🛡 <b>بەشی ئەمنیەت</b>", parse_mode="HTML", reply_markup=KB_SEC); return
        if txt == "📢 بەشی کانال": await update.message.reply_text("📢 <b>بەشی کانال</b>", parse_mode="HTML", reply_markup=KB_CHAN); return
        if txt == "⚙️ بەشی سیستەم": await update.message.reply_text("⚙️ <b>بەشی سیستەم</b>", parse_mode="HTML", reply_markup=KB_SYS); return

        # بەکارهێنەران
        if txt == "👥 لیستی هەموو بەکارهێنەران": await owner_list_users(update); return
        if txt == "🔍 گەڕان بۆ بەکارهێنەر": await db_put(f"users/{uid}/state", "search_user"); await update.message.reply_text("🔍 ناو یان ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📋 زانیاری بەکارهێنەر بە ID": await db_put(f"users/{uid}/state", "user_info_id"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📊 ئامارەکانی بەکارهێنەران": await owner_user_stats(update); return
        if txt == "🗑 سڕینەوەی بەکارهێنەر": await db_put(f"users/{uid}/state", "del_user"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        
        # بۆتەکان
        if txt == "🤖 لیستی هەموو بۆتەکان": await owner_list_bots(update); return
        if txt == "🟢 بۆتە چالاکەکان": await owner_list_bots(update, "running"); return
        if txt == "🔴 بۆتە ڕاگیراوەکان": await owner_list_bots(update, "stopped"); return
        if txt == "📊 ئامارەکانی بۆتەکان": await owner_bot_stats(update); return
        if txt == "▶️ دەستپێکردنی هەموو": await owner_all_bots_action(update, "running"); return
        if txt == "⏸ وەستاندنی هەموو": await owner_all_bots_action(update, "stopped"); return
        if txt == "🗑 سڕینەوەی بۆت بە ID": await db_put(f"users/{uid}/state", "owner_del_bot"); await update.message.reply_text("🆔 ID ی بۆت بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "🔍 گەڕان بۆ بۆت": await db_put(f"users/{uid}/state", "search_bot"); await update.message.reply_text("🔍 یوزەرنەیم یان ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return

        # پەیام
        if txt == "📨 بڵاوکردنەوە بۆ هەموو": await db_put(f"users/{uid}/state", "bc_all"); await update.message.reply_text("📨 نامەکەت بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📨 بڵاوکردنەوە بۆ VIP": await db_put(f"users/{uid}/state", "bc_vip"); await update.message.reply_text("💎 نامەکەت بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📨 بڵاوکردنەوە بۆ نا-VIP": await db_put(f"users/{uid}/state", "bc_nonvip"); await update.message.reply_text("📨 نامەکەت بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📬 پەیام بۆ بەکارهێنەرێک": await db_put(f"users/{uid}/state", "msg_one_id"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📌 دانانی پەیامی سیستەم": await db_put(f"users/{uid}/state", "set_sys_msg"); await update.message.reply_text("📌 پەیامەکەت بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "🗑 سڕینەوەی پەیامی سیستەم": await db_del("system/notice"); await update.message.reply_text("✅ پەیامی سیستەم سڕایەوە."); return
        if txt == "📋 پەیامی سیستەمی ئێستا": msg_now = await db_get("system/notice"); await update.message.reply_text(f"📌 {msg_now}" if msg_now else "📭 نییە."); return

        # VIP
        if txt == "💎 لیستی VIPەکان": await owner_list_vips(update); return
        if txt == "➕ زیادکردنی VIP": await db_put(f"users/{uid}/state", "add_vip"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "➖ لابردنی VIP": await db_put(f"users/{uid}/state", "del_vip"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📊 ئامارەکانی VIP": await owner_vip_stats(update); return
        if txt == "💎 VIP بۆ کاتی دیاریکراو": await db_put(f"users/{uid}/state", "add_vip_date"); await update.message.reply_text("🆔 ID و بەروار (12345 2025-12-31):", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "💎 VIP بۆ هەمیشەیی": await db_put(f"users/{uid}/state", "add_vip_life"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "🔍 پشکنینی VIP بەکارهێنەر": await db_put(f"users/{uid}/state", "check_vip"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "🗑 سڕینەوەی هەموو VIP": await db_del("vip"); await update.message.reply_text("✅ هەموویان سڕانەوە."); return

        # ئەمنیەت
        if txt == "🚫 بلۆک کردنی بەکارهێنەر": await db_put(f"users/{uid}/state", "block_user"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "✅ لابردنی بلۆک": await db_put(f"users/{uid}/state", "unblock_user"); await update.message.reply_text("🆔 ID بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📋 لیستی بلۆکەکان": await owner_list_blocked(update); return
        if txt == "🗑 سڕینەوەی هەموو بلۆک": await db_del("blocked"); await update.message.reply_text("✅ هەموویان سڕانەوە."); return
        
        # کانال
        if txt == "📢 گۆڕینی کانالی سەرەکی": await db_put(f"users/{uid}/state", "change_main_channel"); await update.message.reply_text("📢 یوزەرنەیم بنووسە بێ @:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "➕ زیادکردنی کانالی داواکراو": await db_put(f"users/{uid}/state", "add_req_channel"); await update.message.reply_text("➕ یوزەرنەیم بنووسە بێ @:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "➖ لابردنی کانالی داواکراو": await db_put(f"users/{uid}/state", "del_req_channel"); await update.message.reply_text("➖ یوزەرنەیم بنووسە بێ @:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📋 لیستی کانالەکان": await owner_list_channels(update); return
        if txt == "✅ چالاککردنی داواکردنی کانال": await db_put("system/force_join", True); await update.message.reply_text("✅ چالاک کرا."); return
        if txt == "❌ لەکارخستنی داواکردن": await db_put("system/force_join", False); await update.message.reply_text("❌ لەکار خرا."); return
        if txt == "📊 ئامارەکانی کانال": await owner_channel_stats(update); return

        # سیستەم و ئەدمین
        if txt == "➕ زیادکردنی ئەدمین": await db_put(f"users/{uid}/state", "add_admin"); await update.message.reply_text("🆔 ID ی کەسەکە بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "➖ لابردنی ئەدمین": await db_put(f"users/{uid}/state", "del_admin"); await update.message.reply_text("🆔 ID ی کەسەکە بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "📋 لیستی ئەدمینەکان": 
            admins = await db_get("system/admins") or {}
            msg = "📋 <b>لیستی ئەدمینەکان:</b>\n" + "\n".join([f"• <code>{k}</code>" for k in admins.keys()]) if admins else "هیچ ئەدمینێک نییە."
            await update.message.reply_text(msg, parse_mode="HTML"); return
        if txt == "⚙️ زانیاری سیستەم": await owner_sys_info(update); return
        if txt == "🔄 نوێکردنەوەی هەموو وەبهووک": await owner_refresh_all_webhooks(update); return
        if txt == "🗑 پاككردنی داتابەیس": await db_del("users"); await db_del("managed_bots"); await update.message.reply_text("✅ پاککرایەوە."); return
        if txt == "📝 گۆڕینی بۆتی سەرەکی": await update.message.reply_text("لە Vercel بیگۆڕە."); return
        if txt == "🌐 گۆڕینی PROJECT URL": await db_put(f"users/{uid}/state", "change_project_url"); await update.message.reply_text("لینک بنووسە:", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)); return
        if txt == "🖼 گۆڕینی وێنەی بەخێرهاتن":
            await db_put(f"users/{uid}/state", "change_photo_url")
            kb = ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True)
            await update.message.reply_text("🖼 <b>تکایە وێنەکە ڕاستەوخۆ لێرە بنێرە:</b>", parse_mode="HTML", reply_markup=kb)
            return

    # دۆخەکانی چاوەڕوانی
    await handle_states(update, uid, txt, state, is_adm, notif_on)


# ══════════════════════════════════════════════════════════════════════════════
# ── فەنکشنەکانی خێرایی (asyncio.gather) و نیشاندان
# ══════════════════════════════════════════════════════════════════════════════
async def show_owner_main(update: Update):
    all_b, all_u, all_v, all_bl = await asyncio.gather(
        db_get("managed_bots"), db_get("users"), db_get("vip"), db_get("blocked")
    )
    all_b = all_b or {}; all_u = all_u or {}; all_v = all_v or {}; all_bl = all_bl or {}
    run = sum(1 for v in all_b.values() if v.get("status") == "running")
    
    msg = (
        "👑 <b>پانێلی سەرەکی</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{len(all_u)}</b> :بەکارهێنەران 👥\n"
        f"<b>{len(all_b)}</b> :بۆتەکان 🤖  (🟢{run}  🔴{len(all_b)-run})\n"
        f"<b>{len(all_v)}</b> :VIPەکان 💎\n"
        f"<b>{len(all_bl)}</b> :بلۆکەکان 🚫\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>بەشێک هەڵبژێرە:</b>"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_OWNER_MAIN)

async def show_stats(update: Update, uid: int, is_adm: bool, notif: bool):
    all_b, all_u = await asyncio.gather(db_get("managed_bots"), db_get("users"))
    all_b = all_b or {}; all_u = all_u or {}
    mine = {k: v for k, v in all_b.items() if v.get("owner") == uid}
    run_m = sum(1 for v in mine.values() if v.get("status") == "running")
    
    if is_adm:
        run_a = sum(1 for v in all_b.values() if v.get("status") == "running")
        txt = (
            "📊 <b>ئامارەکانی سیستەم</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"<b>{len(all_u)}</b> :هەموو بەکارهێنەران 👥\n"
            f"<b>{len(all_b)}</b> :هەموو بۆتەکان 🤖\n"
            f"🔴 ڕاگیراو: <b>{len(all_b)-run_a}</b>  |  🟢 چالاک: <b>{run_a}</b>\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
    else:
        txt = (
            "📊 <b>ئامارەکانت</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"<b>{len(mine)}</b> :بۆتی دروستکردوو 🤖\n"
            f"🔴 ڕاگیراو: <b>{len(mine)-run_m}</b>  |  🟢 چالاک: <b>{run_m}</b>\n"
        )
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main(uid, is_adm, notif))

async def show_bot_list(update: Update, uid: int, is_adm: bool, notif: bool):
    all_b = await db_get("managed_bots") or {}
    mine  = {k: v for k, v in all_b.items() if v.get("owner") == uid}
    if not mine:
        await update.message.reply_text("📭 <b>هیچ بۆتێکت نییە!</b>", parse_mode="HTML", reply_markup=kb_main(uid, is_adm, notif))
        return
    rows = [[KeyboardButton(f"{'🟢' if info.get('status') == 'running' else '🔴'} @{info.get('bot_username','Bot')}")] for _, info in mine.items()]
    rows.append([KeyboardButton("🔙 گەڕانەوە بۆ سەرەتا")])
    await update.message.reply_text(f"📂 <b>بۆتەکانت ({len(mine)}):</b>", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True))

async def show_bot_control(update: Update, uid: int, bid: str, info: dict, is_adm: bool):
    st = "🟢 کاردەکات" if info.get("status") == "running" else "🔴 ڕاگیراوە"
    msg = (
        "⚙️ <b>پانێلی کۆنترۆڵ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{html.escape(info.get('bot_name','ناسناو'))}</b> :ناو 🤖\n"
        f"<b>@{info.get('bot_username','ناسناو')}</b> :یوزەر 🔗\n"
        f"<b>{st}</b> :دۆخ 📊\n"
        "━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb_control(is_adm))

# ══════════════════════════════════════════════════════════════════════════════
# ── دۆخەکانی چاوەڕوانی (States)
# ══════════════════════════════════════════════════════════════════════════════
async def handle_states(update: Update, uid: int, txt: str, state: str, is_adm: bool, notif: bool):
    if not state: return

    if state == "await_token":
        if re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35}$", txt):
            sm = await update.message.reply_text("⏳ خەریکی پشکنین...")
            res = await send_tg(txt, "getMe", {})
            if not res.get("ok"):
                await sm.edit_text("❌ تۆکێن هەڵەیە.")
                return
            bi = res["result"]
            bid = str(bi["id"])
            safe = (PROJECT_URL or "").rstrip('/')
            wh = await send_tg(txt, "setWebhook", {"url": f"{safe}/api/bot/{txt}"})
            if wh.get("ok"):
                await db_put(f"managed_bots/{bid}", {
                    "token":txt, "owner":uid, "bot_username":bi["username"],
                    "bot_name":bi["first_name"], "status":"running"
                })
                await db_del(f"users/{uid}/state")
                await sm.edit_text(f"✅ <b>بۆتەکەت چالاک کرا!</b>\n🤖 @{bi['username']}", parse_mode="HTML")
                await show_bot_list(update, uid, is_adm, notif)
            else:
                await sm.edit_text("❌ هەڵە لە وەبهووک.")
        else:
            await update.message.reply_text("⚠️ تۆکێنی دروست بنێرە.")
        return

    if state.startswith("edit_welcome:"):
        bid = state.split(":")[1]
        await db_patch(f"managed_bots/{bid}", {"welcome_msg": txt})
        await db_del(f"users/{uid}/state")
        await update.message.reply_text("✅ گۆڕدرا.", reply_markup=kb_control(is_adm))
        return

    if is_adm:
        if state == "add_admin":
            await db_put(f"system/admins/{txt}", True)
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ کرا بە ئەدمین.", reply_markup=KB_SYS); return
        if state == "del_admin":
            await db_del(f"system/admins/{txt}")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ لە ئەدمین لابرا.", reply_markup=KB_SYS); return
        if state == "add_req_channel":
            await db_put(f"system/req_channels/{txt}", True)
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ کانال زیادکرا.", reply_markup=KB_CHAN); return
        if state == "del_req_channel":
            await db_del(f"system/req_channels/{txt}")
            await db_del(f"users/{uid}/state")
            await update.message.reply_text("✅ کانال لابرا.", reply_markup=KB_CHAN); return
        if state == "bc_all":
            all_u = await db_get("users") or {}
            await db_del(f"users/{uid}/state")
            sm = await update.message.reply_text(f"⏳ ناردن بۆ {len(all_u)} کەس...")
            sent = 0
            for u in all_u.keys():
                try:
                    await ctx.bot.copy_message(u, update.message.chat_id, update.message.message_id)
                    sent += 1
                except: pass
            await sm.edit_text(f"✅ نێردرا بۆ {sent} کەس.", reply_markup=KB_MSG); return

async def handle_control(update: Update, uid: int, txt: str, is_adm: bool, notif: bool = True):
    bid = await db_get(f"users/{uid}/selected_bot")
    if not bid: return await update.message.reply_text("⚠️ بۆتێک هەڵبژێرە.")
    info = await db_get(f"managed_bots/{bid}")
    if not info: return await update.message.reply_text("❌ نەدۆزرایەوە.")

    if txt == "▶️ دەستپێکردن":
        info["status"] = "running"
        await db_put(f"managed_bots/{bid}", info)
        await update.message.reply_text("✅ دەستی پێکرد.", reply_markup=kb_control(is_adm))
    elif txt == "⏸ وەستاندن":
        info["status"] = "stopped"
        await db_put(f"managed_bots/{bid}", info)
        await update.message.reply_text("🛑 وەستاندرا.", reply_markup=kb_control(is_adm))
    elif txt == "🔄 نوێکردنەوە":
        info["status"] = "running"
        await db_put(f"managed_bots/{bid}", info)
        await update.message.reply_text("🔄 نوێکرایەوە.", reply_markup=kb_control(is_adm))
    elif txt == "✏️ گۆڕینی بەخێرهاتن":
        await db_put(f"users/{uid}/state", f"edit_welcome:{bid}")
        await update.message.reply_text("✏️ نامەی نوێ بنووسە (دەتوانیت {name} بەکاربهێنیت):", reply_markup=ReplyKeyboardMarkup([["❌ هەڵوەشاندنەوە"]], resize_keyboard=True))
    elif txt == "🗑 سڕینەوەی بۆت":
        await db_del(f"managed_bots/{bid}")
        await db_del(f"users/{uid}/selected_bot")
        await update.message.reply_text("🗑 سڕایەوە.", reply_markup=kb_main(uid, is_adm, notif))

# ══════════════════════════════════════════════════════════════════════════════
# ── فەنکشنەکانی خاوەن بۆ ئامار و لیست
# ══════════════════════════════════════════════════════════════════════════════
async def owner_sys_info(update: Update):
    all_b, all_u, req_chs = await asyncio.gather(db_get("managed_bots"), db_get("users"), db_get("system/req_channels"))
    all_b = all_b or {}; all_u = all_u or {}; req_chs = req_chs or {}
    fj = await db_get("system/force_join")
    msg = (
        f"⚙️ <b>زانیاری سیستەم</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{PROJECT_URL}</code> :لینک 🌐\n"
        f"<b>{len(all_u)}</b> :بەکارهێنەران 👥\n"
        f"<b>{len(all_b)}</b> :بۆتەکان 🤖\n"
        f"({len(req_chs)} کەناڵ) <b>{'چالاک' if fj else 'لەکارخراو'}</b> :جۆینی ناچاری ✅"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_SYS)

async def owner_list_users(update: Update):
    all_u = await db_get("users") or {}
    msg = f"👥 <b>لیستی بەکارهێنەران ({len(all_u)}):</b>\n"
    for i, (k, v) in enumerate(list(all_u.items())[:40]):
        msg += f"• <code>{k}</code> - {html.escape(v.get('name',''))}\n"
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_USERS)

async def owner_list_bots(update: Update, status=None):
    all_b = await db_get("managed_bots") or {}
    if status: all_b = {k:v for k,v in all_b.items() if v.get("status") == status}
    msg = f"🤖 <b>بۆتەکان ({len(all_b)}):</b>\n"
    for i, (k, v) in enumerate(list(all_b.items())[:40]):
        st = "🟢" if v.get('status')=='running' else "🔴"
        msg += f"{st} @{v.get('bot_username','')} | Owner: <code>{v.get('owner')}</code>\n"
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_BOTS)

async def owner_all_bots_action(update: Update, status: str):
    all_b = await db_get("managed_bots") or {}
    for k, v in all_b.items():
        v["status"] = status
        await db_put(f"managed_bots/{k}", v)
    await update.message.reply_text(f"✅ هەموویان {'دەستیان پێکرد' if status=='running' else 'وەستاندران'}.", reply_markup=KB_BOTS)

async def owner_list_channels(update: Update):
    req_chs = await db_get("system/req_channels") or {}
    msg = "📢 <b>کەناڵە ناچارییەکان:</b>\n" + "\n".join([f"• @{ch}" for ch in req_chs.keys()])
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=KB_CHAN)

async def owner_user_stats(update: Update):
    all_u, all_bl = await asyncio.gather(db_get("users"), db_get("blocked"))
    all_u = all_u or {}; all_bl = all_bl or {}
    await update.message.reply_text(f"📊 بەکارهێنەران: {len(all_u)}\n🚫 بلۆک: {len(all_bl)}", reply_markup=KB_USERS)

async def owner_refresh_all_webhooks(update: Update):
    all_b = await db_get("managed_bots") or {}
    sm    = await update.message.reply_text(f"⏳ نوێکردنەوەی {len(all_b)} وەبهووک...")
    ok=fail=0
    safe  = (PROJECT_URL or "").rstrip('/')
    for bid, bd in all_b.items():
        if bd.get("status") != "running": continue
        token = bd.get("token","")
        if not token: continue
        r = await send_tg(token,"setWebhook",{"url":f"{safe}/api/bot/{token}"})
        if r.get("ok"): ok+=1
        else: fail+=1
    await sm.edit_text(f"✅ وەبهووک نوێکرایەوە!\n✅ سەرکەوتوو: {ok}  ❌ هەڵە: {fail}", reply_markup=KB_SYS)


# ══════════════════════════════════════════════════════════════════════════════
# ── بۆتی منداڵ (Child Bot)
# ══════════════════════════════════════════════════════════════════════════════
async def process_child_update(token: str, body: dict):
    try:
        bid = token.split(":")[0]
        info = await db_get(f"managed_bots/{bid}")
        if not info or info.get("status") != "running": return

        bun = info.get("bot_username","Bot")
        bnm = info.get("bot_name","Reaction Bot")
        wlcm = info.get("welcome_msg", "")
        # پشکنین بۆ وێنەی ناو داتابەیس یان لینکی دیفاڵت
        sys_photo = await db_get("system/photo_id") or PHOTO_URL

        msg = body.get("message") or body.get("channel_post")
        if not msg: return

        chat_id, message_id, txt = msg["chat"]["id"], msg["message_id"], msg.get("text","")
        u_name = html.escape(msg.get("from", {}).get("first_name", "بەکارهێنەر"))
        
        async with httpx.AsyncClient(timeout=10) as c:
            if txt.startswith("/start"):
                if wlcm:
                    caption = wlcm.replace("{name}", u_name)
                else:
                    caption = (
                        f"سڵاو، <b>{u_name}</b> 👋\n\n"
                        f"من بۆتی ڕیاکشنم 🍓 ناوم <b>{html.escape(bnm)}</b>ە\n\n"
                        f"دەتوانم بۆ هەموو نامەیەک ئەم ئیمۆجیانە دابنێم:\n{' '.join(EMOJIS)}\n\n"
                        "تەنها زیادم بکە بۆ گروپ یان کانالەکەت و بمکە بە ئەدمین ☘️"
                    )
                kb = {"inline_keyboard": [[{"text":"➕ زیادکردن بۆ گروپ", "url":f"https://t.me/{bun}?startgroup=new"},
                     {"text":"➕ زیادکردن بۆ کانال","url":f"https://t.me/{bun}?startchannel=new"}]
                ]}
                payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML", "reply_markup": kb, "reply_to_message_id": message_id}
                
                # ئەگەر photo_id بێت ڕاستەوخۆ دەینێرێت
                payload["photo"] = sys_photo
                await c.post(f"https://api.telegram.org/bot{token}/sendPhoto", json=payload)
            else:
                await c.post(f"https://api.telegram.org/bot{token}/setMessageReaction", json={
                    "chat_id": chat_id, "message_id": message_id,
                    "reaction":[{"type":"emoji", "emoji": random.choice(EMOJIS)}]
                })
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
master_app = ApplicationBuilder().token(MASTER_TOKEN).build()
master_app.add_handler(CommandHandler("start", master_start))
master_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))

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
