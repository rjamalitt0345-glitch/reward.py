import os
import re
import uuid
import time
import json
import asyncio
import logging
import random
from typing import Optional
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ====== CREDENTIALS ======
BOT_TOKEN = "8903708107:AAEK50TICrw9OOO0vrjGWbcO6WQ7reVUQGI"  # Bot Token
DEFAULT_REF = "aftabd7c7ff3d"  # Default referral code
# =========================

# ====== 100+ RANDOM NAMES ======
RANDOM_NAMES = [
    "Aarav Sharma", "Vivaan Singh", "Aditya Patel", "Vihaan Kumar", "Arjun Reddy",
    "Sai Krishna", "Rahul Verma", "Aryan Gupta", "Ayaan Joshi", "Dhruv Nair",
    "Krishna Iyer", "Pranav Menon", "Ananya Rao", "Diya Shah", "Ishita Mehta",
    "Kavya Nair", "Navya Reddy", "Sara Khan", "Zara Sheikh", "Aisha Singh",
    "Riya Patel", "Priya Sharma", "Sneha Gupta", "Anjali Verma", "Meera Joshi",
    "Rohan Das", "Soham Bhatt", "Amit Kumar", "Vikram Singh", "Suresh Reddy",
    "Mahesh Babu", "Nagesh Rao", "Ramesh Iyer", "Suresh Menon", "Kiran Shetty",
    "Deepak Sharma", "Sanjay Gupta", "Rajesh Kumar", "Anil Singh", "Sunil Patel",
    "Pankaj Verma", "Manoj Joshi", "Vijay Nair", "Ajay Reddy", "Sachin Tendulkar",
    "Rahul Dravid", "Virat Kohli", "Rohit Sharma", "MS Dhoni", "Jasprit Bumrah",
    "Ravindra Jadeja", "Hardik Pandya", "KL Rahul", "Shubman Gill", "Ishan Kishan",
    "Sanju Samson", "Rishabh Pant", "Shreyas Iyer", "Suryakumar Yadav", "Cheteshwar Pujara",
    "Ajinkya Rahane", "Ravichandran Ashwin", "Axar Patel", "Yuzvendra Chahal", "Bhuvneshwar Kumar",
    "Mohammed Shami", "Umesh Yadav", "Ishant Sharma", "Shardul Thakur", "Deepak Chahar",
    "Kuldeep Yadav", "Varun Chakravarthy", "Washington Sundar", "Navdeep Saini", "T Natarajan",
    "Prasidh Krishna", "Mohammed Siraj", "Avesh Khan", "Umran Malik", "Arshdeep Singh",
    "Nikhil Patel", "Ravi Shankar", "Prakash Raj", "Ganesh Kumar", "Surya Prakash",
    "Chandrasekhar Rao", "Venkatesh Prasad", "Ramanujan Iyengar", "Subramaniam Swami", "Lakshmi Narayan",
    "Gautam Adani", "Mukesh Ambani", "Ratan Tata", "Azim Premji", "Shiv Nadar",
    "Kumar Mangalam", "Sunil Bharti", "Anil Agarwal", "Lakshmi Mittal", "Mallika Sharma",
    "Rekha Singh", "Kajal Reddy", "Tamil Selvi", "Kannaki Devi", "Radhika Krishnan",
    "Sita Ram", "Hanuman Rao", "Balaji R", "Venkatesh S", "Murali Krishna",
    "Srinivasan R", "Narasimhan K", "Raghavan P", "Viswanathan A", "Subramanian B",
    "Krishnamurthy V", "Ramachandran S", "Annadurai N", "Muthusamy K", "Perumal R",
    "Pandian V", "Sundararajan R", "Gopalakrishnan M", "Ramanathan S", "Balasubramanian P",
    "Sivakumar K", "Thirumalai R", "Natarajan V", "Chidambaram S", "Rangarajan M",
    "Vijayalakshmi S", "Karpagam R", "Selvi A", "Mangalam K", "Kalyani P",
    "Thilagavathi R", "Rukmini S", "Gayathri V", "Sarala M", "Kamala K"
]

# User states
WAITING_FOR_NUMBER = 1
WAITING_FOR_OTP = 2
WAITING_FOR_OTP_NUMBER = 3
WAITING_FOR_NEW_REF = 4

# Files
REGISTERED_NUMBERS_FILE = "registered_numbers.txt"
PENDING_OTP_FILE = "pending_otp.json"
USED_NAMES_FILE = "used_names.json"
USER_REFS_FILE = "user_refs.json"  # Store user-specific referral codes

# Global storage
user_data = {}
pending_otp = {}  # {phone_number: {"reference_code": "", "device_id": "", "phone": ""}}
registered_numbers = set()
used_names = set()
user_refs = {}  # {user_id: referral_code}

# Public access - allow multiple users
ALLOWED_USERS = set()  # Will be populated dynamically

class HabuildBot:
    def __init__(self):
        self.session = None
        
    async def get_session(self):
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit=10)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session
    
    def get_random_name(self):
        """Get a random name that hasn't been used yet"""
        global used_names
        
        # Filter available names
        available_names = [name for name in RANDOM_NAMES if name not in used_names]
        
        # If all names are used, reset the used_names set
        if not available_names:
            print("⚠️ All names used! Resetting name pool...")
            used_names.clear()
            save_used_names()
            available_names = RANDOM_NAMES.copy()
        
        # Pick random name
        chosen_name = random.choice(available_names)
        used_names.add(chosen_name)
        save_used_names()
        return chosen_name
    
    def get_user_ref(self, user_id):
        """Get referral code for a user"""
        return user_refs.get(str(user_id), DEFAULT_REF)
    
    async def check_if_registered(self, phone_number):
        """Check if number is already registered with ANY referral code"""
        phone_full = f"+91{phone_number}"
        
        url = "https://auth-service.habuild.in/public/auth/v1/login"
        payload = {
            "method": "phone_otp",
            "otpChannel": "sms",
            "phoneNumber": phone_full,
            "sourceData": {"type": "portal", "utm_source": "whatsapp"},
            "experimentMetaInfo": {"deviceId": str(uuid.uuid4()), "sessionId": str(uuid.uuid4())},
            "registerUser": False
        }
        
        try:
            session = await self.get_session()
            async with session.post(url, json=payload, timeout=10) as r:
                result = await r.json()
                if r.status == 404 or result.get('message') == 'User not found':
                    return False, None
                elif r.status == 200 and result.get('message') == 'OTP sent to your phone':
                    return True, "already_registered"
                else:
                    return False, None
        except Exception as e:
            return False, str(e)
    
    async def register_user(self, phone_number, user_id):
        """Register user with user's referral code and random name"""
        phone_full = f"+91{phone_number}"
        device_id = str(uuid.uuid4())
        random_name = self.get_random_name()
        ref_code = self.get_user_ref(user_id)
        
        url = "https://auth-service.habuild.in/public/user/v1/register-user"
        payload = {
            "name": random_name,
            "phoneNumber": phone_full,
            "referredBy": ref_code,
            "sourceData": {"type": "Referral", "refererurl": "", "timezone": "Asia/Kolkata"},
            "experimentMetaInfo": {"deviceId": device_id, "sessionId": str(uuid.uuid4())}
        }
        
        try:
            session = await self.get_session()
            async with session.post(url, json=payload, timeout=10) as r:
                result = await r.json()
                if r.status == 200 and result.get('message') == 'success':
                    return True, None, random_name, ref_code
                elif r.status == 409:
                    return False, "already_registered", None, None
                else:
                    return False, result.get('message', 'Unknown error'), None, None
        except Exception as e:
            return False, str(e), None, None
    
    async def send_otp(self, phone_number):
        """Send OTP to phone number"""
        phone_full = f"+91{phone_number}"
        device_id = str(uuid.uuid4())
        
        url = "https://auth-service.habuild.in/public/auth/v1/login"
        payload = {
            "method": "phone_otp",
            "otpChannel": "sms",
            "phoneNumber": phone_full,
            "sourceData": {"type": "portal", "utm_source": "whatsapp"},
            "experimentMetaInfo": {"deviceId": device_id, "sessionId": str(uuid.uuid4())},
            "registerUser": False
        }
        
        try:
            session = await self.get_session()
            async with session.post(url, json=payload, timeout=10) as r:
                result = await r.json()
                if r.status == 200 and result.get('message') == 'OTP sent to your phone':
                    ref_code = result.get('data', {}).get('refrence_code')
                    if ref_code:
                        pending_otp[phone_number] = {
                            "reference_code": ref_code,
                            "device_id": device_id,
                            "phone": phone_full
                        }
                        save_pending_otp()
                        return True, ref_code
                elif r.status == 429:
                    return False, "rate_limit"
                else:
                    return False, result.get('message', 'Unknown error')
        except Exception as e:
            return False, str(e)
    
    async def verify_otp(self, phone_number, otp_code):
        """Verify OTP"""
        if phone_number not in pending_otp:
            return False, "no_pending_otp"
        
        data = pending_otp[phone_number]
        url = "https://auth-service.habuild.in/public/auth/v1/verify-otp"
        payload = {
            "phone": data['phone'],
            "reference_code": data['reference_code'],
            "otp": otp_code,
            "experimentMetaInfo": {"deviceId": data['device_id'], "sessionId": str(uuid.uuid4())},
            "registerUser": False
        }
        
        try:
            session = await self.get_session()
            async with session.post(url, json=payload, timeout=10) as r:
                result = await r.json()
                if r.status == 200 and result.get('message') == 'OTP verified successfully':
                    member = result.get('data', {}).get('member', {})
                    registered_numbers.add(phone_number)
                    save_registered_numbers()
                    del pending_otp[phone_number]
                    save_pending_otp()
                    return True, member
                else:
                    return False, result.get('message', 'Invalid OTP')
        except Exception as e:
            return False, str(e)
    
    async def clear_pending_otp(self):
        """Clear all pending OTPs"""
        global pending_otp
        pending_otp.clear()
        save_pending_otp()
        return True

bot = HabuildBot()

# ========== FILE FUNCTIONS ==========

def load_registered_numbers():
    """Load registered numbers from file"""
    global registered_numbers
    if os.path.exists(REGISTERED_NUMBERS_FILE):
        try:
            with open(REGISTERED_NUMBERS_FILE, "r") as f:
                for line in f:
                    num = line.strip()
                    if num:
                        registered_numbers.add(num)
            print(f"✅ Loaded {len(registered_numbers)} registered numbers")
        except Exception as e:
            print(f"⚠️ Error loading registered numbers: {e}")

def save_registered_numbers():
    """Save registered numbers to file"""
    try:
        with open(REGISTERED_NUMBERS_FILE, "w") as f:
            for num in registered_numbers:
                f.write(f"{num}\n")
    except Exception as e:
        print(f"⚠️ Error saving registered numbers: {e}")

def load_pending_otp():
    """Load pending OTPs from file"""
    global pending_otp
    if os.path.exists(PENDING_OTP_FILE):
        try:
            with open(PENDING_OTP_FILE, "r") as f:
                pending_otp = json.load(f)
            print(f"✅ Loaded {len(pending_otp)} pending OTPs")
        except Exception as e:
            print(f"⚠️ Error loading pending OTPs: {e}")

def save_pending_otp():
    """Save pending OTPs to file"""
    try:
        with open(PENDING_OTP_FILE, "w") as f:
            json.dump(pending_otp, f)
    except Exception as e:
        print(f"⚠️ Error saving pending OTPs: {e}")

def load_used_names():
    """Load used names from file"""
    global used_names
    if os.path.exists(USED_NAMES_FILE):
        try:
            with open(USED_NAMES_FILE, "r") as f:
                used_names = set(json.load(f))
            print(f"✅ Loaded {len(used_names)} used names")
        except Exception as e:
            print(f"⚠️ Error loading used names: {e}")

def save_used_names():
    """Save used names to file"""
    try:
        with open(USED_NAMES_FILE, "w") as f:
            json.dump(list(used_names), f)
    except Exception as e:
        print(f"⚠️ Error saving used names: {e}")

def load_user_refs():
    """Load user referral codes from file"""
    global user_refs
    if os.path.exists(USER_REFS_FILE):
        try:
            with open(USER_REFS_FILE, "r") as f:
                user_refs = json.load(f)
            print(f"✅ Loaded {len(user_refs)} user referral codes")
        except Exception as e:
            print(f"⚠️ Error loading user refs: {e}")

def save_user_refs():
    """Save user referral codes to file"""
    try:
        with open(USER_REFS_FILE, "w") as f:
            json.dump(user_refs, f)
    except Exception as e:
        print(f"⚠️ Error saving user refs: {e}")

# ========== TELEGRAM HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - show menu"""
    user_id = str(update.effective_chat.id)
    
    # Add user to allowed list
    ALLOWED_USERS.add(user_id)
    
    # Get user's referral code
    user_ref = bot.get_user_ref(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📱 New Number", callback_data="new_number")],
        [InlineKeyboardButton("✅ Verify OTP", callback_data="verify_otp")],
        [InlineKeyboardButton("🔑 Change Referral", callback_data="change_ref")],
        [InlineKeyboardButton("🗑️ Clear Pending OTPs", callback_data="clear_pending")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    available_names = len([n for n in RANDOM_NAMES if n not in used_names])
    
    await update.message.reply_text(
        f"🤖 *Habuild Looter Bot*\n\n"
        f"👤 Your Referral Code: `{user_ref}`\n"
        f"📊 Registered: {len(registered_numbers)}\n"
        f"⏳ Pending OTP: {len(pending_otp)}\n"
        f"👤 Names Used: {len(used_names)}/{len(RANDOM_NAMES)}\n\n"
        f"Select an option:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_chat.id)
    
    if query.data == "new_number":
        context.user_data['state'] = WAITING_FOR_NUMBER
        await query.edit_message_text(
            f"📱 *Enter 10-digit phone number:*\n\n"
            f"Example: `9876543210`\n\n"
            f"Type /cancel to go back",
            parse_mode='Markdown'
        )
    
    elif query.data == "verify_otp":
        if not pending_otp:
            await query.edit_message_text(
                "❌ No pending OTP requests.\n"
                "First send OTP to a number using 'New Number' option."
            )
            await asyncio.sleep(3)
            await start(update, context)
            return
        
        context.user_data['state'] = WAITING_FOR_OTP
        
        numbers = list(pending_otp.keys())
        msg = "📱 *Enter OTP for verification:*\n\n"
        msg += f"🔢 *Pending Numbers:*\n"
        for i, num in enumerate(numbers, 1):
            msg += f"{i}. `{num}`\n"
        msg += f"\n📝 *Send OTP like:* `123456`\n"
        msg += f"⚠️ Make sure OTP matches the number\n"
        msg += f"Type /cancel to go back"
        
        await query.edit_message_text(msg, parse_mode='Markdown')
    
    elif query.data == "change_ref":
        context.user_data['state'] = WAITING_FOR_NEW_REF
        current_ref = bot.get_user_ref(user_id)
        await query.edit_message_text(
            f"🔑 *Change Referral Code*\n\n"
            f"Current Code: `{current_ref}`\n\n"
            f"📝 Send new referral code:\n"
            f"Example: `abc123xyz`\n\n"
            f"Type /cancel to go back",
            parse_mode='Markdown'
        )
    
    elif query.data == "clear_pending":
        if not pending_otp:
            await query.edit_message_text("✅ No pending OTPs to clear!")
            await asyncio.sleep(2)
            await start(update, context)
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Clear All", callback_data="confirm_clear")],
            [InlineKeyboardButton("❌ No, Go Back", callback_data="cancel_clear")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚠️ *Clear Pending OTPs*\n\n"
            f"Pending Numbers: {len(pending_otp)}\n"
            f"📱 Numbers: {', '.join(list(pending_otp.keys())[:5])}\n\n"
            f"Are you sure you want to clear all pending OTPs?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif query.data == "confirm_clear":
        await bot.clear_pending_otp()
        await query.edit_message_text(
            f"✅ *All pending OTPs cleared!*\n\n"
            f"🗑️ All pending requests removed."
        )
        await asyncio.sleep(2)
        await start(update, context)
    
    elif query.data == "cancel_clear":
        await query.edit_message_text("✅ Operation cancelled!")
        await asyncio.sleep(1)
        await start(update, context)
    
    elif query.data == "stats":
        available_names = len([n for n in RANDOM_NAMES if n not in used_names])
        user_ref = bot.get_user_ref(user_id)
        msg = f"📊 *Stats*\n\n"
        msg += f"👤 Your Ref Code: `{user_ref}`\n"
        msg += f"✅ Registered Numbers: {len(registered_numbers)}\n"
        msg += f"⏳ Pending OTP: {len(pending_otp)}\n"
        msg += f"👤 Names Used: {len(used_names)}/{len(RANDOM_NAMES)}\n"
        msg += f"📝 Names Available: {available_names}\n"
        if registered_numbers:
            msg += f"\n📱 *Recently Registered:*\n"
            recent = list(registered_numbers)[-10:]  # Last 10
            for num in recent:
                msg += f"• `{num}`\n"
        
        await query.edit_message_text(msg, parse_mode='Markdown')
        await asyncio.sleep(5)
        await start(update, context)
    
    elif query.data == "about":
        available_names = len([n for n in RANDOM_NAMES if n not in used_names])
        user_ref = bot.get_user_ref(user_id)
        msg = f"ℹ️ *About*\n\n"
        msg += f"🤖 Habuild Referral Bot (Public)\n"
        msg += f"👤 Your Code: `{user_ref}`\n"
        msg += f"📊 Total Registered: {len(registered_numbers)}\n"
        msg += f"👤 Names Used: {len(used_names)}/{len(RANDOM_NAMES)}\n\n"
        msg += f"💡 *Features:*\n"
        msg += f"• Each user has their own referral code\n"
        msg += f"• Check if number is already registered\n"
        msg += f"• Register with random names (100+ available)\n"
        msg += f"• Auto-detect existing users\n"
        msg += f"• One-click clear pending OTPs\n"
        msg += f"• Save data permanently\n\n"
        msg += f"Made with ❤️"
        
        await query.edit_message_text(msg, parse_mode='Markdown')
        await asyncio.sleep(5)
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input (number or OTP)"""
    user_id = str(update.effective_chat.id)
    text = update.message.text.strip()
    state = context.user_data.get('state')
    
    if state == WAITING_FOR_NUMBER:
        # Validate number
        if not text.isdigit() or len(text) != 10:
            await update.message.reply_text(
                "❌ Invalid number! Enter exactly 10 digits.\n"
                "Example: `9876543210`",
                parse_mode='Markdown'
            )
            return
        
        # Check local cache first
        if text in registered_numbers:
            await update.message.reply_text(
                f"⚠️ *Number Already Registered!*\n\n"
                f"📱 `{text}` is already registered with a referral code.\n\n"
                f"💡 Each number can only be registered once.",
                parse_mode='Markdown'
            )
            context.user_data['state'] = None
            await start(update, context)
            return
        
        # Check on server if already registered
        await update.message.reply_text(f"🔄 Checking if `{text}` is already registered...", parse_mode='Markdown')
        is_registered, msg = await bot.check_if_registered(text)
        
        if is_registered:
            registered_numbers.add(text)
            save_registered_numbers()
            await update.message.reply_text(
                f"⚠️ *Number Already Registered!*\n\n"
                f"📱 `{text}` is already registered on Habuild.\n\n"
                f"💡 Try another number.",
                parse_mode='Markdown'
            )
            context.user_data['state'] = None
            await start(update, context)
            return
        
        # Register user
        user_ref = bot.get_user_ref(user_id)
        await update.message.reply_text(f"🔄 Registering `{text}` with your referral code...", parse_mode='Markdown')
        success, msg, random_name, used_ref = await bot.register_user(text, user_id)
        
        if success:
            await update.message.reply_text(
                f"✅ *Registration Successful!*\n\n"
                f"📱 Number: `{text}`\n"
                f"👤 Name: `{random_name}`\n"
                f"🔗 Referral Code: `{used_ref}`\n"
                f"🎉 You earned +1 referral!\n"
                f"📝 Names Remaining: {len([n for n in RANDOM_NAMES if n not in used_names])}",
                parse_mode='Markdown'
            )
            
            # Send OTP
            await update.message.reply_text(f"📨 Sending OTP to `{text}`...", parse_mode='Markdown')
            otp_sent, ref_code = await bot.send_otp(text)
            
            if otp_sent:
                await update.message.reply_text(
                    f"✅ *OTP Sent!*\n\n"
                    f"📱 Number: `{text}`\n"
                    f"📌 Reference: `{ref_code}`\n\n"
                    f"🔐 Check SMS for OTP\n"
                    f"Click 'Verify OTP' to verify",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ *Failed to send OTP:* {ref_code}\n\n"
                    f"💡 Try again later.",
                    parse_mode='Markdown'
                )
        else:
            if msg == "already_registered":
                registered_numbers.add(text)
                save_registered_numbers()
                await update.message.reply_text(
                    f"⚠️ *Number Already Registered!*\n\n"
                    f"📱 `{text}` is already registered with a referral code.\n"
                    f"💡 Each number can only be registered once.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ *Registration failed:* {msg}\n\n"
                    f"💡 Try again later.",
                    parse_mode='Markdown'
                )
        
        context.user_data['state'] = None
        await start(update, context)
    
    elif state == WAITING_FOR_OTP:
        # Validate OTP
        if not text.isdigit() or len(text) != 6:
            await update.message.reply_text(
                "❌ Invalid OTP! Enter exactly 6 digits.\n"
                "Example: `123456`",
                parse_mode='Markdown'
            )
            return
        
        if not pending_otp:
            await update.message.reply_text("❌ No pending OTP requests!")
            context.user_data['state'] = None
            await start(update, context)
            return
        
        numbers = list(pending_otp.keys())
        
        if len(numbers) == 1:
            phone = numbers[0]
        else:
            await update.message.reply_text(
                f"❓ *Multiple pending OTPs!*\n\n"
                f"Which number is this OTP for?\n"
                f"Send number like: `{numbers[0]}`\n\n"
                f"🔢 Pending numbers:\n" + "\n".join([f"• `{num}`" for num in numbers]),
                parse_mode='Markdown'
            )
            context.user_data['temp_otp'] = text
            context.user_data['state'] = WAITING_FOR_OTP_NUMBER
            return
        
        await update.message.reply_text(f"🔄 Verifying OTP for `{phone}`...", parse_mode='Markdown')
        
        success, result = await bot.verify_otp(phone, text)
        
        if success:
            msg = f"✅ *OTP Verified Successfully!*\n\n"
            msg += f"📱 Number: `{phone}`\n"
            msg += f"👤 Name: {result.get('name', 'N/A')}\n"
            msg += f"🆔 Member ID: {result.get('legacy_free_id', 'N/A')}\n"
            msg += f"🔗 Referral Code Used: {bot.get_user_ref(user_id)}\n"
            msg += f"🎉 Referral Count Increased!"
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"❌ *Verification failed:* {result}\n\n"
                f"💡 Make sure:\n"
                f"• OTP is correct (6 digits)\n"
                f"• Number is correct\n"
                f"• OTP hasn't expired (2 min)\n"
                f"• Try resending OTP",
                parse_mode='Markdown'
            )
        
        context.user_data['state'] = None
        await start(update, context)
    
    elif state == WAITING_FOR_OTP_NUMBER:
        phone = text.strip()
        temp_otp = context.user_data.get('temp_otp', '')
        
        if phone not in pending_otp:
            await update.message.reply_text(
                f"❌ Number `{phone}` not found in pending OTPs!\n"
                f"🔢 Pending numbers: {', '.join(pending_otp.keys())}",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text(f"🔄 Verifying OTP for `{phone}`...", parse_mode='Markdown')
        
        success, result = await bot.verify_otp(phone, temp_otp)
        
        if success:
            msg = f"✅ *OTP Verified Successfully!*\n\n"
            msg += f"📱 Number: `{phone}`\n"
            msg += f"👤 Name: {result.get('name', 'N/A')}\n"
            msg += f"🆔 Member ID: {result.get('legacy_free_id', 'N/A')}\n"
            msg += f"🔗 Referral Code Used: {bot.get_user_ref(user_id)}\n"
            msg += f"🎉 Referral Count Increased!"
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"❌ *Verification failed:* {result}\n\n"
                f"💡 Make sure:\n"
                f"• OTP is correct (6 digits)\n"
                f"• Number is correct\n"
                f"• OTP hasn't expired",
                parse_mode='Markdown'
            )
        
        context.user_data['state'] = None
        context.user_data['temp_otp'] = None
        await start(update, context)
    
    elif state == WAITING_FOR_NEW_REF:
        # Validate referral code
        if len(text) < 5:
            await update.message.reply_text(
                "❌ Invalid referral code! Must be at least 5 characters.\n"
                "Example: `abc123xyz`",
                parse_mode='Markdown'
            )
            return
        
        # Save new referral code
        user_refs[user_id] = text
        save_user_refs()
        
        await update.message.reply_text(
            f"✅ *Referral Code Updated!*\n\n"
            f"🔑 New Code: `{text}`\n\n"
            f"All future registrations will use this code.",
            parse_mode='Markdown'
        )
        
        context.user_data['state'] = None
        await start(update, context)
    
    elif text.lower() == '/cancel':
        context.user_data['state'] = None
        context.user_data['temp_otp'] = None
        await update.message.reply_text("✅ Cancelled!")
        await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    context.user_data['state'] = None
    context.user_data['temp_otp'] = None
    await update.message.reply_text("✅ Cancelled!")
    await start(update, context)

def main():
    # Load saved data
    load_registered_numbers()
    load_pending_otp()
    load_used_names()
    load_user_refs()
    
    print("="*60)
    print("  HABUILD BOT - PUBLIC VERSION")
    print("="*60)
    print(f"\n🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"📌 Default Refer Code: {DEFAULT_REF}")
    print(f"📊 Registered Numbers: {len(registered_numbers)}")
    print(f"⏳ Pending OTPs: {len(pending_otp)}")
    print(f"👤 Names Used: {len(used_names)}/{len(RANDOM_NAMES)}")
    print(f"👥 Users Registered: {len(user_refs)}")
    print("\n⚠️  This is a PUBLIC bot - anyone can use it!")
    print("⚠️  Each user can set their own referral code!")
    print("="*60)
    print("\n🚀 Bot starting...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("\n✅ Bot is running! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()