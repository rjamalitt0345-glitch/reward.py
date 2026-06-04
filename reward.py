import asyncio
import requests
import io
import random
import json
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ╔══════════════════════════════╗
# ║        CONFIGURATION         ║
# ╚══════════════════════════════╝
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID         = 5319770650
USERS_FILE       = "bot_users.json"

# ── Conversation States ──
CHOOSING, PHONE, REFER_CODE, OTP, DASHBOARD, PHOTO, BROADCAST = range(7)

# ── Button Labels ──
BTN_SIGNUP       = "🆕 Naya Account"
BTN_LOGIN        = "🔑 Login Karo"
BTN_BALANCE      = "💰 Balance & Profile"
BTN_UPLOAD       = "📸 Upload Receipt"
BTN_REFERRAL     = "🔗 My Referral Code"
BTN_LOGOUT       = "🚪 Logout"
BTN_BROADCAST    = "📢 Broadcast"
BTN_DEFAULT_REF  = f"✅ Default Code Use Karo ({DEFAULT_REF_CODE})"
BTN_CUSTOM_REF   = "✏️ Apna Referral Code Daalo"

# ── Keyboards ──
def is_admin(user_id):
    return user_id == ADMIN_ID

def pre_login_kb(user_id):
    rows = [[BTN_SIGNUP, BTN_LOGIN]]
    if is_admin(user_id):
        rows.append([BTN_BROADCAST])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

def refer_code_kb(user_id):
    rows = [[BTN_DEFAULT_REF], [BTN_CUSTOM_REF]]
    if is_admin(user_id):
        rows.append([BTN_BROADCAST])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

def dashboard_kb(user_id):
    rows = [[BTN_BALANCE, BTN_UPLOAD], [BTN_REFERRAL], [BTN_LOGOUT]]
    if is_admin(user_id):
        rows.insert(1, [BTN_BROADCAST])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

# ╔══════════════════════════════╗
# ║         API LOGIC            ║
# ╚══════════════════════════════╝
class RewardsBot:
    def __init__(self):
        self.base_url  = "https://rewardssphere.com/api/v1"
        self.session   = requests.Session()
        self.locations = ["Sonipat", "Rohtak", "Sampla", "Bahadurgarh", "Delhi"]
        self.headers   = {
            "User-Agent":       "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "Content-Type":     "application/json",
            "Accept":           "application/json, text/plain, */*",
            "X-Requested-With": "mark.via.gp",
            "Origin":           "https://www.rewardssphere.com",
            "Referer":          "https://www.rewardssphere.com/"
        }

    def check_exists(self, phone):
        try:
            r = self.session.get(f"{self.base_url}/auth/user/exists?phone={phone}", headers=self.headers, timeout=10)
            return r.json()
        except:
            return {"exists": False}

    def request_otp(self, phone, is_login=False):
        path = "/auth/otp/request" if is_login else "/auth/signup/otp/request"
        try:
            r = self.session.post(f"{self.base_url}{path}", json={"phone": str(phone)}, headers=self.headers, timeout=15)
            return r.json()
        except:
            return {"success": False}

    def verify_otp(self, phone, otp, ref_code, is_login=False):
        if is_login:
            url     = f"{self.base_url}/auth/otp/verify"
            payload = {"phone": str(phone), "otp": str(otp)}
        else:
            url     = f"{self.base_url}/auth/signup/otp/verify"
            payload = {"phone": str(phone), "otp": str(otp),
                       "referral_code": str(ref_code),
                       "accepted_terms": True, "accepted_privacy": True}
        try:
            r = self.session.post(url, json=payload, headers=self.headers, timeout=15)
            return r.json()
        except:
            return {"success": False}

    def get_profile(self, token):
        try:
            r = self.session.get(f"{self.base_url}/user/me",
                                 headers={**self.headers, "Authorization": f"Bearer {token}"}, timeout=10)
            return r.json()
        except:
            return None

api = RewardsBot()

# ╔══════════════════════════════╗
# ║          HELPERS             ║
# ╚══════════════════════════════╝
def remember_user(context, user_id):
    users = context.application.bot_data.setdefault("known_users", set())
    if user_id not in users:
        users.add(user_id)
        save_known_users(users)

def load_known_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return {int(uid) for uid in json.load(f)}
    except Exception:
        return set()

def save_known_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(users)), f)
    except Exception:
        pass

def find_points_value(data):
    if isinstance(data, list):
        for item in data:
            found = find_points_value(item)
            if found is not None:
                return found
        return None
    if not isinstance(data, dict):
        return None
    keys = [
        "pointsEarned", "earnedPoints", "points_awarded", "pointsAwarded",
        "rewardPoints", "points", "creditedPoints", "amount"
    ]
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str) and value.replace(".", "", 1).isdigit():
            return value
    for value in data.values():
        if isinstance(value, dict):
            found = find_points_value(value)
            if found is not None:
                return found
    return None

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, next_state):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await context.bot.send_message(chat_id, "🚫 Yeh feature sirf admin ke liye hai.")
        return next_state

    context.user_data["broadcast_return_state"] = next_state
    await context.bot.send_message(
        chat_id,
        "📢 *Broadcast Message*\n━━━━━━━━━━━━━━━━━━━━━\nJo message sab users ko bhejna hai, ab type karo:",
        parse_mode="Markdown"
    )
    return BROADCAST

async def on_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("🚫 Yeh feature sirf admin ke liye hai.")
        return context.user_data.get("broadcast_return_state", CHOOSING)

    users = load_known_users()
    context.application.bot_data["known_users"] = users
    sent = 0
    failed = 0

    for uid in list(users):
        if uid == ADMIN_ID:
            continue
        try:
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=chat_id,
                message_id=update.message.message_id
            )
            sent += 1
        except Exception:
            failed += 1

    await context.bot.send_message(
        chat_id,
        f"✅ *Broadcast Done!*\n━━━━━━━━━━━━━━━━━━━━━\n📨 Sent: *{sent}*\n⚠️ Failed: *{failed}*",
        parse_mode="Markdown"
    )
    return context.user_data.get("broadcast_return_state", CHOOSING)

async def send_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE, message):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("🚫 Yeh command sirf admin ke liye hai.")
        return

    users = load_known_users()
    context.application.bot_data["known_users"] = users
    sent = 0
    failed = 0

    for uid in list(users):
        if uid == ADMIN_ID:
            continue
        try:
            await context.bot.send_message(uid, message)
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ *Broadcast Done!*\n━━━━━━━━━━━━━━━━━━━━━\n📨 Sent: *{sent}*\n⚠️ Failed: *{failed}*",
        parse_mode="Markdown"
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Yeh command sirf admin ke liye hai.")
        return

    message = " ".join(context.args).strip()
    if message:
        await send_broadcast_text(update, context, message)
        return

    context.user_data["broadcast_return_state"] = DASHBOARD if "token" in context.user_data else CHOOSING
    await update.message.reply_text(
        "📢 *Broadcast Message*\n━━━━━━━━━━━━━━━━━━━━━\nJo message/photo sab users ko bhejna hai, ab bhejo:",
        parse_mode="Markdown"
    )
    return BROADCAST

# ╔══════════════════════════════╗
# ║         HANDLERS             ║
# ╚══════════════════════════════╝

# ── /start ──
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)

    if "token" in context.user_data:
        return await send_dashboard(update, context)

    text = (
        "🌟 *RewardsSphere Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Receipts upload karo 📸\n"
        "aur gift cards jeeto! 🎁\n\n"
        "👇 Neeche se choose karo:"
    )
    msg = update.message if update.message else update.callback_query.message
    await msg.reply_text(text, reply_markup=pre_login_kb(update.effective_user.id), parse_mode="Markdown")
    return CHOOSING

# ── CHOOSING state handler ──
async def on_choosing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    text = update.message.text

    if text == BTN_BROADCAST:
        return await start_broadcast(update, context, CHOOSING)

    elif text == BTN_SIGNUP:
        context.user_data["mode"] = "signup"
        await update.message.reply_text(
            "📱 *Naya Registration*\n━━━━━━━━━━━━\nApna 10-digit mobile number bhejo:",
            parse_mode="Markdown"
        )
        return PHONE

    elif text == BTN_LOGIN:
        context.user_data["mode"] = "login"
        await update.message.reply_text(
            "📱 *Login*\n━━━━━━━━━━━━\nApna 10-digit mobile number bhejo:",
            parse_mode="Markdown"
        )
        return PHONE

    else:
        await update.message.reply_text("👆 Neeche diye buttons use karo.")
        return CHOOSING

# ── Dashboard ──
async def send_dashboard(update, context):
    profile = api.get_profile(context.user_data.get("token", ""))
    if not isinstance(profile, dict) or profile.get("detail"):
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id,
            "❌ Session khatam ho gayi! /start karein.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

    bal  = profile.get("balance", 0)
    ref  = profile.get("referralCode", "N/A")
    name = profile.get("name") or profile.get("fullName") or profile.get("phone") or "Bhai"
    text = (
        f"🏠 *Welcome, {name}!*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance   :  ₹*{bal}*\n"
        f"🔗 Ref Code :  `{ref}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 Menu se option choose karo:"
    )
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, text, reply_markup=dashboard_kb(update.effective_user.id), parse_mode="Markdown")
    return DASHBOARD

# ── Phone number ──
async def on_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    text = update.message.text.strip()

    if text == BTN_BROADCAST:
        return await start_broadcast(update, context, PHONE)

    phone = text
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("⚠️ Sahi 10-digit number bhejo (sirf numbers):")
        return PHONE

    context.user_data["phone"] = phone
    check = api.check_exists(phone)

    if context.user_data["mode"] == "signup":
        if check.get("exists"):
            await update.message.reply_text("⚠️ Ye number already registered hai!\n👇 Login karo:", reply_markup=pre_login_kb(update.effective_user.id))
            context.user_data["mode"] = "login"
            return CHOOSING
        await update.message.reply_text(
            "🔗 *Referral Code*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Kisi ne tumhe refer kiya hai?\n"
            "👇 Unka code daalo — ya default use karo:",
            reply_markup=refer_code_kb(update.effective_user.id),
            parse_mode="Markdown"
        )
        return REFER_CODE
    else:
        if not check.get("exists"):
            await update.message.reply_text("❌ Ye number registered nahi hai!\n👇 Pehle signup karo:", reply_markup=pre_login_kb(update.effective_user.id))
            return CHOOSING
        api.request_otp(phone, is_login=True)
        await update.message.reply_text(
            "📩 *OTP Bheja Gaya!*\n━━━━━━━━━━━━\nApna OTP type karo 👇",
            parse_mode="Markdown"
        )
        return OTP

# ── Refer code ──
async def on_refer_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    text = update.message.text.strip()

    if text == BTN_BROADCAST:
        return await start_broadcast(update, context, REFER_CODE)

    elif text == BTN_DEFAULT_REF:
        # Use the default referral code
        context.user_data["ref_code"] = DEFAULT_REF_CODE
        api.request_otp(context.user_data["phone"], is_login=False)
        await update.message.reply_text(
            f"✅ *Default Code Set!* `{DEFAULT_REF_CODE}`\n\n"
            "📩 *OTP Bheja Gaya!*\n━━━━━━━━━━━━\nApna OTP type karo 👇",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        return OTP

    elif text == BTN_CUSTOM_REF:
        # Ask them to type their custom code
        await update.message.reply_text(
            "✏️ *Apna Referral Code Type Karo:*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Jis dost ne refer kiya unka code daalo 👇\n"
            "_(sirf code — koi aur text nahi)_",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        context.user_data["waiting_custom_ref"] = True
        return REFER_CODE

    elif context.user_data.get("waiting_custom_ref"):
        # They typed a custom code
        code = text.upper().strip()
        context.user_data["ref_code"] = code
        context.user_data.pop("waiting_custom_ref", None)
        api.request_otp(context.user_data["phone"], is_login=False)
        await update.message.reply_text(
            f"✅ *Referral Code Set!* `{code}`\n\n"
            "📩 *OTP Bheja Gaya!*\n━━━━━━━━━━━━\nApna OTP type karo 👇",
            parse_mode="Markdown"
        )
        return OTP

    else:
        # They directly typed a code (without pressing custom button)
        code = text.upper().strip()
        context.user_data["ref_code"] = code
        api.request_otp(context.user_data["phone"], is_login=False)
        await update.message.reply_text(
            f"✅ *Referral Code Set!* `{code}`\n\n"
            "📩 *OTP Bheja Gaya!*\n━━━━━━━━━━━━\nApna OTP type karo 👇",
            parse_mode="Markdown"
        )
        return OTP

# ── OTP verify ──
async def on_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    text = update.message.text.strip()
    if text == BTN_BROADCAST:
        return await start_broadcast(update, context, OTP)

    phone = context.user_data["phone"]
    mode  = context.user_data["mode"]
    ref   = context.user_data.get("ref_code", DEFAULT_REF_CODE)

    res       = api.verify_otp(phone, text, ref, is_login=(mode == "login"))
    token     = res.get("token") or res.get("data", {}).get("token")
    msg_lower = str(res.get("message", "")).lower()

    if token:
        context.user_data["token"] = token
        await update.message.reply_text("✅ *Login Successful!* Dashboard load ho raha hai...", parse_mode="Markdown")
        return await send_dashboard(update, context)
    elif "waiting" in msg_lower or "waitlist" in msg_lower:
        await update.message.reply_text(
            "⏳ *OTP sahi tha!*\n\nPar bhai, tumhe *Waiting List* mein dala gaya hai.\nThodi der baad try karna! 🙏",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        err = res.get("message", "Wrong OTP ya session expire ho gaya.")
        await update.message.reply_text(f"❌ *Error:* {err}\n\n/start se dobara try karo.", parse_mode="Markdown")
        return ConversationHandler.END

# ── Dashboard menu ──
async def on_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    text    = update.message.text
    chat_id = update.effective_chat.id

    # Delete user's button-press message
    try:
        await update.message.delete()
    except Exception:
        pass

    if text == BTN_BROADCAST:
        return await start_broadcast(update, context, DASHBOARD)

    elif text == BTN_BALANCE:
        profile = api.get_profile(context.user_data["token"])
        if not isinstance(profile, dict) or profile.get("detail"):
            await context.bot.send_message(chat_id, "❌ Session expire ho gayi. /start karo.")
            return ConversationHandler.END
        bal   = profile.get("balance", 0)
        ref   = profile.get("referralCode", "N/A")
        phone = profile.get("phone", "N/A")
        name  = profile.get("name") or profile.get("fullName") or "—"
        prev_id = context.user_data.get("balance_msg_id")
        if prev_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=prev_id)
            except Exception:
                pass
        msg = (
            "👤 *My Profile*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧑 Name     :  {name}\n"
            f"📱 Phone    :  {phone}\n"
            f"💰 Balance  :  ₹*{bal}*\n"
            f"🔗 Ref Code :  `{ref}`\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        m = await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
        context.user_data["balance_msg_id"] = m.message_id
        return DASHBOARD

    elif text == BTN_UPLOAD:
        await context.bot.send_message(
            chat_id,
            "📸 *Receipt Upload*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Apni receipt ki photo bhejo\n"
            "aur points earn karo! 🎯",
            parse_mode="Markdown"
        )
        return PHOTO

    elif text == BTN_REFERRAL:
        profile = api.get_profile(context.user_data["token"])
        ref     = profile.get("referralCode", "N/A") if isinstance(profile, dict) else "N/A"
        prev_id = context.user_data.get("ref_msg_id")
        if prev_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=prev_id)
            except Exception:
                pass
        msg = (
            "🔗 *Tera Referral Code*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉  `{ref}`\n\n"
            "Dosto ko share karo aur dono\n"
            "ko bonus milega! 🎉"
        )
        m = await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
        context.user_data["ref_msg_id"] = m.message_id
        return DASHBOARD

    elif text == BTN_LOGOUT:
        context.user_data.clear()
        await context.bot.send_message(
            chat_id,
            "🚪 *Logout ho gaye!*\n\nPhir milenge bhai 👋\n/start se wapas aao.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    else:
        await context.bot.send_message(chat_id, "👆 Neeche diye buttons use karo.")
        return DASHBOARD

# ── Wrong input in PHOTO state ──
async def on_photo_wrong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    if update.message.text == BTN_BROADCAST:
        return await start_broadcast(update, context, PHOTO)
    await update.message.reply_text(
        "📸 Bhai, *photo bhejo* — text nahi!\nReceipt ki photo click karke bhejo 👇",
        parse_mode="Markdown"
    )
    return PHOTO

# ── Photo upload ──
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(context, update.effective_user.id)
    try:
        photo_file = await update.message.photo[-1].get_file()
        img        = await photo_file.download_as_bytearray()
        token      = context.user_data["token"]
        loc        = random.choice(api.locations)
        before_profile = api.get_profile(token)
        before_balance = before_profile.get("balance") if isinstance(before_profile, dict) else None
        h = {k: v for k, v in api.headers.items() if k != "Content-Type"}
        h["Authorization"] = f"Bearer {token}"
        m = await update.message.reply_text("⏳ *Uploading your receipt...* 🔄", parse_mode="Markdown")
        up = requests.post(
            f"{api.base_url}/receipts/upload",
            headers=h,
            data={"payment_method": "Cash", "store_location": loc},
            files={"receipt": ("receipt.jpg", io.BytesIO(img), "image/jpeg")},
            timeout=30
        )
        if up.status_code in [200, 201]:
            try:
                upload_data = up.json()
            except Exception:
                upload_data = {}
            points = find_points_value(upload_data)
            after_profile = api.get_profile(token)
            after_balance = after_profile.get("balance") if isinstance(after_profile, dict) else None
            if points is None and isinstance(before_balance, (int, float)) and isinstance(after_balance, (int, float)):
                diff = after_balance - before_balance
                if diff >= 0:
                    points = diff
            points_line = f"🪙 Points mile: *{points}*\n" if points is not None else "🪙 Points: Processing mein hai, approve hote hi add honge.\n"
            await m.edit_text(
                f"🎉 *Upload Successful!*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📍 Location: {loc}\n"
                f"{points_line}"
                f"✅ Receipt accepted!",
                parse_mode="Markdown"
            )
        else:
            await m.edit_text(f"❌ *Upload Failed!*\n`{up.text[:80]}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ *Error:* `{e}`", parse_mode="Markdown")

    return await send_dashboard(update, context)

# ╔══════════════════════════════╗
# ║            MAIN              ║
# ╚══════════════════════════════╝
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.bot_data["known_users"] = load_known_users()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("broadcast", broadcast_command)],
        states={
            CHOOSING:   [MessageHandler(filters.TEXT & ~filters.COMMAND, on_choosing)],
            PHONE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, on_phone)],
            REFER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_refer_code)],
            OTP:        [MessageHandler(filters.TEXT & ~filters.COMMAND, on_otp)],
            DASHBOARD:  [MessageHandler(filters.TEXT & ~filters.COMMAND, on_dashboard_menu)],
            PHOTO:      [
                MessageHandler(filters.PHOTO, on_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_photo_wrong),
            ],
            BROADCAST:  [MessageHandler(filters.ALL & ~filters.COMMAND, on_broadcast)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("broadcast", broadcast_command)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    print("🤖 RewardsSphere Bot chal raha hai...")
    app.run_polling()

if __name__ == "__main__":
    main()
