# config.py - FINAL PRODUCTION READY CONFIGURATION
# Owner: @Nullprotocol_X | ID: 8104850843
# No Errors, Fully Optimized for Render Free Plan

import os

# ============================================
# 1. TELEGRAM BOT CREDENTIALS
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN environment variable is missing!")

OWNER_ID = int(os.getenv("OWNER_ID", "8104850843"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "NullProtocol_SuperSecret_2024")
BOT_MODE = os.getenv("BOT_MODE", "webhook").lower()

# ============================================
# 2. SERVER & DEPLOYMENT (Render)
# ============================================
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip('/')
if not RENDER_EXTERNAL_URL and BOT_MODE == "webhook":
    raise ValueError("❌ RENDER_EXTERNAL_URL is required for webhook mode!")

PORT = int(os.getenv("PORT", "8080"))

# ============================================
# 3. DATABASE (FIXED FOR RENDER FREE PLAN)
# ============================================
# IMPORTANT: Free plan me /data folder nahi hota, isliye simple bot.db use karo.
DB_FILE = os.getenv("DB_FILE", "bot.db")

# ============================================
# 4. CACHE CONFIGURATION
# ============================================
REDIS_URL = os.getenv("REDIS_URL", None)
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))

# ============================================
# 5. AUTO-PING (Self Ping for Anti-Sleep)
# ============================================
SELF_PING_INTERVAL = int(os.getenv("SELF_PING_INTERVAL", "300"))  # 5 minutes default
ENABLE_SELF_PING = os.getenv("ENABLE_SELF_PING", "True").lower() == "true"

# ============================================
# 6. BRANDING
# ============================================
BRANDING = {
    "developer": os.getenv("BRANDING_DEVELOPER", "@Nullprotocol_X"),
    "powered_by": os.getenv("BRANDING_POWERED", "NULL PROTOCOL"),
    "support": os.getenv("BRANDING_SUPPORT", "@Nullprotocol_X"),
    "website": "https://t.me/Nullprotocol_X"
}

# ============================================
# 7. GLOBAL BLACKLIST (Branding Removal)
# ============================================
GLOBAL_BLACKLIST = [
    "copyright", "signature", "credit", "source",
    "developer", "powered_by", "brand", "owner"
]

# ============================================
# 8. FORCE JOIN CHANNELS
# ============================================
FORCE_JOIN_CHANNELS = [
    {"id": -1003090922367, "link": "https://t.me/all_data_here", "name": "All Data Here"},
    {"id": -1003698567122, "link": "https://t.me/osint_lookup", "name": "OSINT Lookup"},
    {"id": -1003672015073, "link": "https://t.me/legend_chats_osint", "name": "LEGEND CHATS"}
]

# ============================================
# 9. LOG CHANNEL
# ============================================
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1003740236326"))

# ============================================
# 10. API ENDPOINTS (20+ APIs)
# ============================================
API_ENDPOINTS = {
    "num": {
        "name": "📞 Phone Number Info",
        "description": "Get basic information about a phone number",
        "url_template": "https://store.abdulstoreapi.workers.dev/api/v1?key={api_key}&num={param}",
        "external_api_key": os.getenv("NUM_API_KEY", "ak_73be4bb78f617ab2ade18663c90b31b1"),
        "param_name": "number",
        "param_example": "9876543210",
        "param_validation": r"^\d{10}$",
        "extra_blacklist": ["credits"],
        "rate_limit_per_min": 80,
        "log_channel": LOG_CHANNEL_ID,
        "enabled": True
    },
    "tg": {
        "name": "🆔 Telegram Username to Number",
        "description": "Get phone number from Telegram username",
        "url_template": "https://sbsakib.eu.cc/apis/tg_username?key={api_key}&user={param}",
        "external_api_key": os.getenv("TG_API_KEY", "Demo"),
        "param_name": "username",
        "param_example": "@InvalidAnand",
        "param_validation": r"^@?[a-zA-Z][a-zA-Z0-9_]{4,31}$",
        "extra_blacklist": [
            "is_verified", "id", "has_profile_pic", "first_name",
            "is_scam", "credit", "common_chats", "bio", "username", "target",
            "is_fake", "type", "public_view", "is_bot"
        ],
        "rate_limit_per_min": 80,
        "log_channel": LOG_CHANNEL_ID,
        "enabled": True
    },
    "aadhaar": {
        "name": "🪪 Aadhaar Info",
        "url_template": "https://sbsakib.eu.cc/apis/aadhaar?key={api_key}&id={param}",
        "external_api_key": os.getenv("AADHAAR_API_KEY", "Demo"),
        "param_name": "id",
        "param_example": "123456789012",
        "param_validation": r"^\d{12}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "ration": {
        "name": "🍚 Ration Card (Family ID)",
        "url_template": "https://intelx-premium-apipanel.vercel.app/INTELXDEMO5?FADHAR={param}",
        "external_api_key": "",
        "param_name": "fadhar",
        "param_example": "FAMILY123",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "tgid": {
        "name": "🆔 Telegram User ID Info",
        "url_template": "https://intelx-premium-apipanel.vercel.app/INTELXDEMO?USERID={param}",
        "external_api_key": "",
        "param_name": "userid",
        "param_example": "123456789",
        "param_validation": r"^\d+$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "vehicle": {
        "name": "🚗 Vehicle RC Info",
        "url_template": "https://devil.elementfx.com/api.php?key={api_key}&type=vehicle&term={param}",
        "external_api_key": os.getenv("VEHICLE_API_KEY", "TRIAL"),
        "param_name": "term",
        "param_example": "MH12AB1234",
        "param_validation": r"^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "challan": {
        "name": "📜 Vehicle Challan",
        "url_template": "https://anon-vehicle-info.vercel.app/rc?key={api_key}&rc={param}",
        "external_api_key": os.getenv("CHALLAN_API_KEY", "temp114"),
        "param_name": "rc",
        "param_example": "MH12AB1234",
        "param_validation": r"^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "paknum": {
        "name": "🇵🇰 Pakistan Number Info",
        "url_template": "https://anon-pak-info.vercel.app/num?key={api_key}&q={param}",
        "external_api_key": os.getenv("PAK_API_KEY", "temp1004"),
        "param_name": "q",
        "param_example": "923001234567",
        "param_validation": r"^92\d{10}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "pakcnic": {
        "name": "🇵🇰 Pakistan CNIC Info",
        "url_template": "https://mafia-ayan-free-osint-api.vercel.app/info?type=sim&number={param}&key={api_key}",
        "external_api_key": os.getenv("PAK_CNIC_KEY", "AYAN-MAFIA-FREE-API"),
        "param_name": "cnic",
        "param_example": "1234567890123",
        "param_validation": r"^\d{13}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "email": {
        "name": "📧 Email Info",
        "url_template": "https://anon-email-info.vercel.app/email?key={api_key}&email={param}",
        "external_api_key": os.getenv("EMAIL_API_KEY", "tempe124"),
        "param_name": "email",
        "param_example": "test@example.com",
        "param_validation": r"^[\w\.-]+@[\w\.-]+\.\w+$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "ip": {
        "name": "🌐 IP Info",
        "url_template": "https://anon-multi-info.vercel.app/ipinfo?key={api_key}&ip={param}",
        "external_api_key": os.getenv("IP_API_KEY", "temp104"),
        "param_name": "ip",
        "param_example": "8.8.8.8",
        "param_validation": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
        "rate_limit_per_min": 50,
        "enabled": True
    },
    "gst": {
        "name": "💰 GST Info",
        "url_template": "https://gst-info-api-by-abhigyan-codes-1.onrender.com/gst?number={param}",
        "external_api_key": "",
        "param_name": "number",
        "param_example": "22AAAAA0000A1Z5",
        "param_validation": r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "pantogst": {
        "name": "🔖 PAN to GST",
        "url_template": "https://gst-info-api-by-abhigyan-codes-1.onrender.com/PANTOGST?number={param}",
        "external_api_key": "",
        "param_name": "number",
        "param_example": "AAAAA0000A",
        "param_validation": r"^[A-Z]{5}\d{4}[A-Z]{1}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "insta": {
        "name": "📸 Instagram Info",
        "url_template": "https://anon-insta-info.vercel.app/profile?key={api_key}&username={param}",
        "external_api_key": os.getenv("INSTA_API_KEY", "temp104"),
        "param_name": "username",
        "param_example": "instagram",
        "param_validation": r"^[a-zA-Z0-9_.]{1,30}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "github": {
        "name": "🐙 GitHub Info",
        "url_template": "https://info-github-api.vercel.app/api/github?username={param}",
        "external_api_key": "",
        "param_name": "username",
        "param_example": "torvalds",
        "param_validation": r"^[a-zA-Z0-9-]{1,39}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "pincode": {
        "name": "📍 Pincode Info",
        "url_template": "https://api.postalpincode.in/pincode/{param}",
        "external_api_key": "",
        "param_name": "pincode",
        "param_example": "110001",
        "param_validation": r"^\d{6}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "ifsc": {
        "name": "🏦 IFSC Info",
        "url_template": "https://ab-ifscinfoapi.vercel.app/info?ifsc={param}",
        "external_api_key": "",
        "param_name": "ifsc",
        "param_example": "SBIN0001234",
        "param_validation": r"^[A-Z]{4}0[A-Z0-9]{6}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "ffinfo": {
        "name": "🎮 Free Fire UID Info",
        "url_template": "https://abbas-apis.vercel.app/api/ff-info?uid={param}",
        "external_api_key": "",
        "param_name": "uid",
        "param_example": "123456789",
        "param_validation": r"^\d{9,12}$",
        "rate_limit_per_min": 30,
        "enabled": True
    },
    "ffban": {
        "name": "⛔ Free Fire Ban Info",
        "url_template": "https://abbas-apis.vercel.app/api/ff-ban?uid={param}",
        "external_api_key": "",
        "param_name": "uid",
        "param_example": "123456789",
        "param_validation": r"^\d{9,12}$",
        "rate_limit_per_min": 30,
        "enabled": True
    }
}

# ============================================
# 11. API PLANS & PRICING (Default)
# ============================================
DEFAULT_PLANS = {}
for api_type in API_ENDPOINTS.keys():
    DEFAULT_PLANS[api_type] = {
        "weekly": {"credits": 15, "days": 7},
        "monthly": {"credits": 30, "days": 30}
    }

# ============================================
# 12. REFERRAL SYSTEM
# ============================================
REFERRAL_REWARD_CREDITS = int(os.getenv("REFERRAL_REWARD_CREDITS", "3"))

# ============================================
# 13. PREMIUM USER SETTINGS
# ============================================
PREMIUM_EXEMPT_FORCE_JOIN = os.getenv("PREMIUM_EXEMPT_FORCE_JOIN", "False").lower() == "true"

# ============================================
# 14. ADMIN / OWNER CONTACT
# ============================================
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "@Nullprotocol_X")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@Nullprotocol_X")

# ============================================
# 15. RATE LIMITING
# ============================================
DEFAULT_RATE_LIMIT_PER_MIN = int(os.getenv("DEFAULT_RATE_LIMIT", "80"))

# ============================================
# 16. DEBUG & LOGGING
# ============================================
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================================
# 17. PRINT CONFIRMATION (Startup Log)
# ============================================
print("✅ CONFIG LOADED - NULL PROTOCOL MULTI-API BOT")
print(f"🚀 Bot Mode: {BOT_MODE.upper()}")
print(f"👑 Owner ID: {OWNER_ID} | @{OWNER_USERNAME}")
print(f"📢 Log Channel: {LOG_CHANNEL_ID}")
print(f"🔗 Force Join Channels: {len(FORCE_JOIN_CHANNELS)}")
print(f"💎 Branding: {BRANDING['developer']}")
print(f"📡 Total APIs Loaded: {len(API_ENDPOINTS)}")
print(f"⏱️ Self-Ping Interval: {SELF_PING_INTERVAL}s")
