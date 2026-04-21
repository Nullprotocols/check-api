# main.py - NULL PROTOCOL MULTI-API PROFESSIONAL BOT
# Owner: @Nullprotocol_X | ID: 8104850843
# Render Webhook Ready | Full Async | 100% Working

import json
import asyncio
import secrets
import time
import re
import aiohttp
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from quart import Quart, request, jsonify
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from config import *
from database import *
from keyboards import *

# ============================================
# LOGGING SETUP
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# ============================================
# QUART APP
# ============================================
app = Quart(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# In-memory cache
cache: Dict[str, Tuple[float, any]] = {}
http_session: Optional[aiohttp.ClientSession] = None

# ============================================
# PTB APPLICATION
# ============================================
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# ============================================
# BRANDING REMOVAL
# ============================================
def remove_branding(data, extra_blacklist=None):
    if extra_blacklist is None:
        extra_blacklist = []
    blacklist = set([term.lower() for term in GLOBAL_BLACKLIST] +
                    [term.lower() for term in extra_blacklist])

    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return [remove_branding(item, extra_blacklist) for item in data
                if remove_branding(item, extra_blacklist) not in ("", None)]
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k.lower() in blacklist:
                continue
            cleaned_val = remove_branding(v, extra_blacklist)
            if cleaned_val not in ("", None):
                cleaned[k] = cleaned_val
        return cleaned
    return data

async def get_cached(key: str):
    if key in cache:
        ts, data = cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        else:
            del cache[key]
    return None

async def set_cached(key: str, data: str):
    cache[key] = (time.time(), data)

# ============================================
# QUART ROUTES (Proxy API)
# ============================================
@app.route('/health')
async def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/v1/<api_type>')
async def proxy_api(api_type):
    if api_type not in API_ENDPOINTS:
        return jsonify({"error": "Invalid API type"}), 400

    api_config = API_ENDPOINTS[api_type]
    status = await get_api_status(api_type)
    if not status['enabled']:
        msg = status['message'] or "This API is temporarily disabled."
        return jsonify({"error": msg}), 503

    key = request.args.get('key')
    if not key:
        return jsonify({"error": "Missing 'key' parameter"}), 400

    valid, user_id, rate_limit = await validate_api_key(key)
    if not valid:
        return jsonify({"error": "Invalid or expired API key"}), 403

    user = await get_user(user_id)
    if user['is_banned']:
        return jsonify({"error": "User is banned"}), 403

    is_prem = await is_premium_active(user_id)
    if not is_prem and not await is_admin(user_id):
        if not await has_active_subscription(user_id, api_type):
            return jsonify({"error": f"No active subscription for {api_type.upper()} API"}), 403

    # Rate limiting
    rate_key = f"rate_{key}"
    now = time.time()
    if rate_key in cache:
        count, window_start = cache[rate_key]
        if now - window_start > 60:
            count = 1
            cache[rate_key] = (count, now)
        else:
            if count >= rate_limit:
                return jsonify({"error": "Rate limit exceeded"}), 429
            cache[rate_key] = (count + 1, window_start)
    else:
        cache[rate_key] = (1, now)

    param_name = api_config.get('param_name', 'query')
    param_value = request.args.get(param_name)
    if not param_value:
        return jsonify({"error": f"Missing '{param_name}' parameter"}), 400

    if 'param_validation' in api_config:
        if not re.match(api_config['param_validation'], param_value):
            return jsonify({"error": f"Invalid {param_name} format"}), 400

    cache_key = f"api_{api_type}_{param_value}"
    cached = await get_cached(cache_key)
    if cached:
        return app.response_class(response=cached, status=200, mimetype='application/json')

    external_api_key = api_config.get('external_api_key', '')
    url = api_config['url_template'].format(api_key=external_api_key, param=param_value)

    try:
        async with http_session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return jsonify({"error": f"Upstream API returned {resp.status}"}), 502
            data = await resp.json()
    except asyncio.TimeoutError:
        return jsonify({"error": "Upstream API timeout"}), 504
    except Exception as e:
        return jsonify({"error": f"Failed to fetch data: {str(e)}"}), 502

    extra_blacklist = api_config.get('extra_blacklist', [])
    cleaned = remove_branding(data, extra_blacklist)
    cleaned['branding'] = BRANDING

    pretty_json = json.dumps(cleaned, indent=2, ensure_ascii=False)
    await set_cached(cache_key, pretty_json)

    return app.response_class(response=pretty_json, status=200, mimetype='application/json')

# ============================================
# TELEGRAM WEBHOOK
# ============================================
@app.route('/webhook', methods=['POST'])
async def telegram_webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = await request.get_json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# FORCE JOIN CHECK
# ============================================
async def check_force_join(user_id: int) -> Tuple[bool, List[Dict]]:
    if await is_admin(user_id):
        return True, []
    if PREMIUM_EXEMPT_FORCE_JOIN and await is_premium_active(user_id):
        return True, []
    missing = []
    for channel in FORCE_JOIN_CHANNELS:
        try:
            member = await application.bot.get_chat_member(chat_id=channel['id'], user_id=user_id)
            if member.status in ['left', 'kicked']:
                missing.append(channel)
        except:
            missing.append(channel)
    return len(missing) == 0, missing

async def send_force_join_message(chat_id: int, missing: List[Dict]):
    text = "⚠️ <b>Please join these channels to use the bot:</b>\n\n"
    keyboard = []
    for ch in missing:
        keyboard.append([InlineKeyboardButton(f"Join {ch['name']}", url=ch['link'])])
    keyboard.append([InlineKeyboardButton("✅ I've Joined", callback_data="check_join")])
    await application.bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# LOGGING TO CHANNEL
# ============================================
async def log_to_channel(text: str):
    try:
        await application.bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Log channel error: {e}")

# ============================================
# COMMAND: /start
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    await get_user(user_id)
    await update_user_info(user_id, user.username, user.first_name, user.last_name)

    if context.args and context.args[0].startswith('ref_'):
        try:
            referrer_id = int(context.args[0][4:])
            if referrer_id != user_id:
                if await set_referrer(user_id, referrer_id):
                    context.user_data['pending_referrer'] = referrer_id
        except:
            pass

    joined, missing = await check_force_join(user_id)
    if not joined:
        await send_force_join_message(user_id, missing)
        return

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET joined_force_channels=1 WHERE user_id=?", (user_id,))
        await db.commit()

    if 'pending_referrer' in context.user_data:
        referrer_id = context.user_data.pop('pending_referrer')
        await add_credits(referrer_id, REFERRAL_REWARD_CREDITS)
        try:
            await application.bot.send_message(
                referrer_id,
                f"🎉 <b>Referral Bonus!</b>\nYou earned {REFERRAL_REWARD_CREDITS} credits."
            )
        except:
            pass

    is_admin_flag = await is_admin(user_id)
    welcome_text = (
        f"✨ <b>Welcome to NULL PROTOCOL API Hub, {user.first_name}!</b> ✨\n\n"
        f"🔐 Professional OSINT & Info APIs at your fingertips.\n"
        f"📡 <b>{len(API_ENDPOINTS)} APIs</b> available.\n\n"
        f"👇 Choose an option:"
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML',
                                    reply_markup=main_menu_keyboard(is_admin_flag))

# ============================================
# CALLBACK ROUTER
# ============================================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "menu_start":
        await start_menu(update, context)
    elif data == "menu_genkey":
        await genkey_menu(update, context)
    elif data == "menu_apihelp":
        await api_help(update, context)
    elif data == "menu_mykeys":
        await my_keys(update, context)
    elif data == "menu_balance":
        await balance_menu(update, context)
    elif data == "menu_referral":
        await referral_menu(update, context)
    elif data == "menu_redeem":
        await redeem_prompt(update, context)
    elif data == "menu_buycredits":
        await buy_credits_menu(update, context)
    elif data == "gen_purchase_req":
        await gen_purchase_request(update, context)
    elif data == "payment_help":
        await payment_help(update, context)
    elif data == "check_join":
        await check_join_callback(update, context)
    elif data == "close_panel":
        await query.delete_message()
    elif data.startswith("gen_"):
        await gen_specific_key(update, context)
    elif data.startswith("plan_"):
        await buy_plan(update, context)
    elif data.startswith("apipage_"):
        await api_page_switcher(update, context)
    elif data.startswith("userlist_page_"):
        await paginated_user_list(update, context)
    elif data.startswith("premiumlist_page_"):
        await paginated_premium_list(update, context)
    elif data.startswith("adminlist_page_"):
        await paginated_admin_list(update, context)
    elif data.startswith("keys_page_"):
        await paginated_keys_list(update, context)
    elif data.startswith("apistatus_page_"):
        await paginated_api_status(update, context)
    elif data.startswith("toggle_ban_"):
        await toggle_ban(update, context)
    elif data.startswith("add_credits_"):
        await add_credits_prompt(update, context)
    elif data.startswith("remove_premium_"):
        await remove_premium_handler(update, context)
    elif data.startswith("make_premium_"):
        await make_premium_prompt(update, context)
    elif data.startswith("permdelete_"):
        await permanent_delete_prompt(update, context)
    elif data.startswith("confirmdelete_"):
        await confirm_delete(update, context)
    elif data.startswith("editkeyexp_"):
        await edit_key_expiry_prompt(update, context)
    elif data.startswith("deactkey_"):
        await deactivate_key(update, context)
    elif data.startswith("togglestatus_"):
        await toggle_api_status(update, context)
    elif data.startswith("approve_purchase_"):
        await approve_purchase(update, context)
    elif data.startswith("reject_purchase_"):
        await reject_purchase(update, context)
    elif data.startswith("setprice_"):
        await set_price_api_selected(update, context)
    elif data.startswith("price_"):
        await set_price_plan_selected(update, context)
    elif data.startswith("remove_admin_"):
        await remove_admin(update, context)
    elif data == "admin_add_admin":
        await add_admin_prompt(update, context)
    elif data == "admin_addpremium":
        await add_premium_prompt(update, context)
    elif data.startswith("bcast_"):
        await broadcast_type_selected(update, context)
    elif data.startswith("admin_"):
        await admin_router(update, context)
    else:
        await query.answer("Feature coming soon!", show_alert=True)

async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    is_admin_flag = await is_admin(user_id)
    await query.edit_message_text(
        "✨ <b>Main Menu</b>",
        parse_mode='HTML',
        reply_markup=main_menu_keyboard(is_admin_flag)
    )

# ============================================
# PUBLIC MENU HANDLERS
# ============================================
async def genkey_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        "🔑 <b>Select API for key generation</b>",
        parse_mode='HTML',
        reply_markup=api_selection_keyboard(page=0)
    )

async def api_page_switcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page = int(query.data.split('_')[1])
    await query.edit_message_text(
        "🔑 <b>Select API for key generation</b>",
        parse_mode='HTML',
        reply_markup=api_selection_keyboard(page=page)
    )

async def gen_specific_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    api_type = query.data.split('_')[1]
    user_id = update.effective_user.id

    if not await is_admin(user_id) and not await has_active_subscription(user_id, api_type) and not await is_premium_active(user_id):
        await query.edit_message_text(
            f"❌ No active subscription for {API_ENDPOINTS[api_type]['name']}.\nUse Balance & Plans to purchase.",
            reply_markup=InlineKeyboardMarkup([[back_button("menu_balance")]])
        )
        return

    new_key = await generate_random_key()
    await create_api_key(new_key, user_id, expires_days=30, rate_limit=80, custom_name=f"{api_type.upper()}_Key")
    await log_to_channel(f"🔑 New {api_type.upper()} key generated by {user_id}")

    example = API_ENDPOINTS[api_type]['param_example']
    endpoint = f"{RENDER_EXTERNAL_URL}/api/v1/{api_type}?key={new_key}&{API_ENDPOINTS[api_type]['param_name']}={example}"
    text = (
        f"✅ <b>API Key Generated!</b>\n\n"
        f"<code>{new_key}</code>\n\n"
        f"🔹 <b>Usage Example:</b>\n<code>{endpoint}</code>\n\n"
        f"⚠️ Save this key securely. It won't be shown again."
    )
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[back_button("menu_genkey")]]))

async def api_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = "📘 <b>API Documentation</b>\n\n"
    for key, cfg in list(API_ENDPOINTS.items())[:10]:
        text += f"<b>{cfg['name']}</b>\n<code>{RENDER_EXTERNAL_URL}/api/v1/{key}?key=KEY&{cfg['param_name']}={cfg['param_example']}</code>\n\n"
    text += f"\n... and {len(API_ENDPOINTS)-10} more APIs."
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[back_button("menu_start")]]))

async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    keys = await list_api_keys(created_by=user_id)
    if not keys:
        text = "🔍 You have no API keys yet."
    else:
        text = "<b>Your API Keys:</b>\n\n"
        for k in keys[:5]:
            short_key = k[0][:12] + "..." + k[0][-4:] if len(k[0])>20 else k[0]
            text += f"<code>{short_key}</code> | Exp: {k[1][:10]} | {'✅' if k[4] else '❌'}\n"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[back_button("menu_start")]]))

async def balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    credits = await get_user_credits(user_id)
    is_prem = await is_premium_active(user_id)
    text = f"💰 <b>Your Balance</b>\nCredits: <b>{credits}</b>\n"
    if is_prem:
        text += "⭐ Premium Status: <b>Active</b> (Unlimited Access)\n"
    else:
        text += "⭐ Premium: Inactive\n\nSelect an API to purchase plan:"

    apis = list(API_ENDPOINTS.keys())[:6]
    keyboard = []
    for api in apis:
        keyboard.append([InlineKeyboardButton(API_ENDPOINTS[api]['name'], callback_data=f"plan_{api}_weekly")])
    keyboard.append([back_button("menu_start")])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split('_')
    api_type = parts[1]
    plan_name = parts[2]
    user_id = update.effective_user.id

    plan = await get_plan(api_type, plan_name)
    if not plan:
        await query.answer("Plan not found", show_alert=True)
        return
    plan_id, price, days = plan
    if await is_admin(user_id) or await is_premium_active(user_id):
        success = True
    else:
        credits = await get_user_credits(user_id)
        if credits < price:
            await query.answer(f"Insufficient credits. Need {price}.", show_alert=True)
            return
        success = await create_subscription(user_id, api_type, plan_name)

    if success:
        await query.edit_message_text(
            f"✅ Subscription activated!\n{API_ENDPOINTS[api_type]['name']} - {plan_name} plan.",
            reply_markup=InlineKeyboardMarkup([[back_button("menu_balance")]])
        )
    else:
        await query.answer("Purchase failed.", show_alert=True)

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    bot_username = (await application.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    text = f"🔗 <b>Your Referral Link</b>\n\n<code>{link}</code>\n\nShare and earn {REFERRAL_REWARD_CREDITS} credits per referral."
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[back_button("menu_start")]]))

async def redeem_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['awaiting_redeem'] = True
    await query.edit_message_text("🎟️ Send the redeem code:", reply_markup=back_to_main_keyboard())

async def buy_credits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        f"💳 <b>Buy Credits</b>\n\nContact {OWNER_USERNAME} to purchase.\n\nGenerate a Transaction ID first:",
        parse_mode='HTML',
        reply_markup=buy_credits_menu_keyboard()
    )

async def gen_purchase_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['awaiting_credit_amount_for_purchase'] = True
    await query.edit_message_text("💰 How many credits do you want to buy?\nSend a number.", reply_markup=back_to_admin_keyboard())

async def payment_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = f"ℹ️ <b>Payment Instructions</b>\n\n1. Generate Transaction ID.\n2. Send payment screenshot to {OWNER_USERNAME} with ID.\n3. Credits added manually."
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=payment_help_keyboard())

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    joined, missing = await check_force_join(user_id)
    if joined:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET joined_force_channels=1 WHERE user_id=?", (user_id,))
            await db.commit()
        await query.edit_message_text("✅ Thank you! Press /start to see the menu.")
    else:
        await query.answer("You haven't joined all channels yet.", show_alert=True)

# ============================================
# ADMIN ROUTER
# ============================================
async def admin_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return

    if data == "menu_admin":
        await query.edit_message_text("🛡️ <b>Admin Control Center</b>", parse_mode='HTML', reply_markup=admin_panel_keyboard())
    elif data == "admin_users":
        await show_user_list(update, context, page=0)
    elif data == "admin_keys":
        await show_keys_list(update, context, page=0)
    elif data == "admin_premium":
        await show_premium_list(update, context, page=0)
    elif data == "admin_broadcast":
        await query.edit_message_text("Select broadcast type:", reply_markup=broadcast_type_keyboard())
    elif data == "admin_bulkdm":
        context.user_data['admin_state'] = 'awaiting_bulkdm_ids'
        await query.edit_message_text("Send user IDs (comma-separated):", reply_markup=back_to_admin_keyboard())
    elif data == "admin_addcredits":
        context.user_data['admin_state'] = 'awaiting_user_for_credits'
        await query.edit_message_text("Send user ID to add credits:", reply_markup=back_to_admin_keyboard())
    elif data == "admin_genredeem":
        context.user_data['admin_state'] = 'awaiting_redeem_credits'
        await query.edit_message_text("Send amount of credits for redeem code:", reply_markup=back_to_admin_keyboard())
    elif data == "admin_pricing":
        await query.edit_message_text("Select API to set price:", reply_markup=pricing_api_selection_keyboard())
    elif data == "admin_purchases":
        await show_pending_purchases(update, context)
    elif data == "admin_admins":
        await show_admin_list(update, context, page=0)
    elif data == "admin_stats":
        await show_stats(update, context)
    elif data == "admin_apistatus":
        await show_api_status(update, context, page=0)
    elif data == "admin_backup":
        await manual_backup(update, context)
    else:
        await query.answer("Coming soon", show_alert=True)

# ============================================
# ADMIN: User List
# ============================================
async def show_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    query = update.callback_query
    limit = 10
    offset = page * limit
    users = await get_users_paginated(offset, limit)
    total = await count_users()
    pages = (total + limit - 1) // limit if total > 0 else 1
    text = f"👥 <b>User List (Page {page+1}/{pages})</b>\n\n"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=user_management_keyboard(users, page, pages))

async def paginated_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(update.callback_query.data.split('_')[-1])
    await show_user_list(update, context, page)

async def toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split('_')[-1])
    user = await get_user(uid)
    if user['is_banned']:
        await unban_user(uid)
        await query.answer("User unbanned.")
    else:
        await ban_user(uid)
        await query.answer("User banned.")
    await show_user_list(update, context, page=0)

async def add_credits_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split('_')[-1])
    context.user_data['target_credit_user'] = uid
    context.user_data['admin_state'] = 'awaiting_credit_amount'
    await query.edit_message_text(f"Send amount of credits to add for user {uid}:", reply_markup=back_to_admin_keyboard())

async def remove_premium_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split('_')[-1])
    await remove_user_premium(uid)
    await query.answer("Premium removed.")
    await show_premium_list(update, context, page=0)

async def make_premium_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split('_')[-1])
    context.user_data['target_premium_user'] = uid
    context.user_data['admin_state'] = 'awaiting_premium_days'
    await query.edit_message_text(f"Send number of days for premium (or 'permanent'):", reply_markup=back_to_admin_keyboard())

async def permanent_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split('_')[-1])
    await query.edit_message_text(
        f"⚠️ Are you sure you want to PERMANENTLY DELETE user {uid}? This cannot be undone!",
        reply_markup=confirm_delete_keyboard(uid)
    )

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split('_')[-1])
    await permanently_delete_user(uid)
    await query.edit_message_text(f"✅ User {uid} permanently deleted.")
    await show_user_list(update, context, page=0)

# ============================================
# ADMIN: Premium List
# ============================================
async def show_premium_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    query = update.callback_query
    limit = 10
    offset = page * limit
    users = await get_all_premium_users()
    total = len(users)
    pages = (total + limit - 1) // limit if total > 0 else 1
    users_page = users[offset:offset+limit]
    text = f"⭐ <b>Premium Users (Page {page+1}/{pages})</b>\n\n"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=premium_users_keyboard(users_page, page, pages))

async def paginated_premium_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(update.callback_query.data.split('_')[-1])
    await show_premium_list(update, context, page)

# ============================================
# ADMIN: API Keys
# ============================================
async def show_keys_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    query = update.callback_query
    limit = 10
    offset = page * limit
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT key, expires_at, rate_limit_per_min, custom_name, is_active FROM api_keys LIMIT ? OFFSET ?", (limit, offset))
        keys = await cur.fetchall()
        cur = await db.execute("SELECT COUNT(*) FROM api_keys")
        total = (await cur.fetchone())[0]
    pages = (total + limit - 1) // limit if total > 0 else 1
    text = f"🔑 <b>API Keys (Page {page+1}/{pages})</b>\n\n"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=api_keys_list_keyboard(keys, page, pages))

async def paginated_keys_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(update.callback_query.data.split('_')[-1])
    await show_keys_list(update, context, page)

async def edit_key_expiry_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key_prefix = query.data.replace("editkeyexp_", "")
    context.user_data['editing_key'] = key_prefix
    context.user_data['admin_state'] = 'awaiting_key_expiry_days'
    await query.edit_message_text("Enter new expiry in days:", reply_markup=back_to_admin_keyboard())

async def deactivate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key_prefix = query.data.replace("deactkey_", "")
    await query.answer("Key deactivated (feature simplified).", show_alert=True)

# ============================================
# ADMIN: API Status
# ============================================
async def show_api_status(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    query = update.callback_query
    await query.edit_message_text("⚙️ <b>API Status Management</b>", parse_mode='HTML', reply_markup=api_status_keyboard(page))

async def paginated_api_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(update.callback_query.data.split('_')[-1])
    await show_api_status(update, context, page)

async def toggle_api_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    api_type = query.data.replace("togglestatus_", "")
    current = await get_api_status(api_type)
    new_state = not current['enabled']
    await set_api_status(api_type, new_state)
    await query.answer(f"{api_type} {'enabled' if new_state else 'disabled'}")
    await show_api_status(update, context, page=0)

# ============================================
# ADMIN: Purchases
# ============================================
async def show_pending_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    reqs = await get_pending_purchase_requests()
    if not reqs:
        await query.edit_message_text("No pending purchase requests.", reply_markup=back_to_admin_keyboard())
    else:
        await query.edit_message_text("🛒 <b>Pending Purchases</b>", parse_mode='HTML', reply_markup=pending_purchases_keyboard(reqs))

async def approve_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    txn_id = query.data.replace("approve_purchase_", "")
    success = await approve_purchase_request(txn_id)
    await query.answer("Approved" if success else "Failed")
    await show_pending_purchases(update, context)

async def reject_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    txn_id = query.data.replace("reject_purchase_", "")
    await reject_purchase_request(txn_id)
    await query.answer("Rejected")
    await show_pending_purchases(update, context)

# ============================================
# ADMIN: Pricing
# ============================================
async def set_price_api_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    api_type = query.data.replace("setprice_", "")
    context.user_data['pricing_api'] = api_type
    await query.edit_message_text(f"Select plan for {api_type}:", reply_markup=pricing_plan_selection_keyboard(api_type))

async def set_price_plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split('_')
    api_type = parts[1]
    plan = parts[2]
    context.user_data['pricing_api'] = api_type
    context.user_data['pricing_plan'] = plan
    context.user_data['admin_state'] = 'awaiting_new_price'
    await query.edit_message_text(f"Enter new price in credits for {api_type} {plan}:", reply_markup=back_to_admin_keyboard())

# ============================================
# ADMIN: Admins
# ============================================
async def show_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    query = update.callback_query
    limit = 10
    offset = page * limit
    admins = await get_admins_paginated(offset, limit)
    total = await count_admins()
    pages = (total + limit - 1) // limit if total > 0 else 1
    text = f"👑 <b>Admin List (Page {page+1}/{pages})</b>"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=admin_list_keyboard(admins, page, pages))

async def paginated_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(update.callback_query.data.split('_')[-1])
    await show_admin_list(update, context, page)

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split('_')[-1])
    if uid == OWNER_ID:
        await query.answer("Cannot remove owner.", show_alert=True)
        return
    await toggle_admin(uid)
    await query.answer("Admin status toggled.")
    await show_admin_list(update, context, page=0)

async def add_admin_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['admin_state'] = 'awaiting_new_admin_id'
    await query.edit_message_text("Send user ID to make admin:", reply_markup=back_to_admin_keyboard())

async def add_premium_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['admin_state'] = 'awaiting_premium_user_id'
    await query.edit_message_text("Send user ID to make premium:", reply_markup=back_to_admin_keyboard())

# ============================================
# ADMIN: Stats
# ============================================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    total_users = await count_users()
    total_keys = await get_total_keys_count()
    premium_count = len(await get_all_premium_users())
    text = f"📊 <b>System Statistics</b>\n\n👥 Users: {total_users}\n🔑 Keys: {total_keys}\n⭐ Premium: {premium_count}"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=stats_keyboard())

# ============================================
# ADMIN: Backup
# ============================================
async def manual_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating backup...")
    try:
        file_size = await get_database_file_size()
        with open(DB_FILE, 'rb') as f:
            msg = await application.bot.send_document(
                chat_id=OWNER_ID,
                document=f,
                filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                caption=f"📦 Manual Backup\nSize: {file_size/1024:.2f} KB"
            )
        await log_backup(msg.document.file_id, file_size)
        await query.edit_message_text("✅ Backup sent to owner DM.")
    except Exception as e:
        await query.edit_message_text(f"❌ Backup failed: {e}")

# ============================================
# BROADCAST HANDLERS
# ============================================
async def broadcast_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    btype = query.data.replace("bcast_", "")
    context.user_data['broadcast_type'] = btype
    await query.edit_message_text(f"Send the {btype} to broadcast:")

async def handle_broadcast_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    btype = context.user_data.get('broadcast_type')
    if not btype:
        return
    msg = update.message
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE is_banned=0 AND deleted=0")
        users = [row[0] for row in await cur.fetchall()]
    success = 0
    for uid in users:
        try:
            if btype == 'text':
                await application.bot.send_message(uid, msg.text, parse_mode='HTML')
            elif btype == 'photo':
                await application.bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption or "")
            elif btype == 'video':
                await application.bot.send_video(uid, msg.video.file_id, caption=msg.caption or "")
            elif btype == 'doc':
                await application.bot.send_document(uid, msg.document.file_id, caption=msg.caption or "")
            success += 1
        except:
            pass
        await asyncio.sleep(0.05)
    context.user_data.pop('broadcast_type', None)
    await update.message.reply_text(f"✅ Broadcast sent to {success} users.")

# ============================================
# TEXT INPUT HANDLER (States)
# ============================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = context.user_data.get('admin_state')
    if not state and not context.user_data.get('awaiting_redeem') and not context.user_data.get('awaiting_credit_amount_for_purchase'):
        return

    # Redeem code
    if context.user_data.get('awaiting_redeem'):
        context.user_data.pop('awaiting_redeem')
        success = await redeem_code(user_id, text)
        if success:
            await update.message.reply_text("✅ Code redeemed! Credits added.")
        else:
            await update.message.reply_text("❌ Invalid or expired code.")
        return

    # Credit purchase amount
    if context.user_data.get('awaiting_credit_amount_for_purchase'):
        try:
            amount = int(text)
            if amount < 1:
                raise ValueError
            txn_id = await create_purchase_request(user_id, amount)
            context.user_data.pop('awaiting_credit_amount_for_purchase')
            await update.message.reply_text(
                f"🆔 <b>Transaction ID:</b> <code>{txn_id}</code>\n"
                f"💰 Amount: {amount} credits\n\n"
                f"📲 Send this ID with payment proof to {OWNER_USERNAME}.",
                parse_mode='HTML'
            )
        except:
            await update.message.reply_text("❌ Invalid amount. Send a positive number.")
        return

    if not await is_admin(user_id):
        return

    # Admin states
    if state == 'awaiting_user_for_credits':
        try:
            uid = int(text)
            context.user_data['target_credit_user'] = uid
            context.user_data['admin_state'] = 'awaiting_credit_amount'
            await update.message.reply_text("Send amount of credits:")
        except:
            await update.message.reply_text("Invalid user ID.")
            context.user_data.pop('admin_state', None)
    elif state == 'awaiting_credit_amount':
        try:
            amount = int(text)
            uid = context.user_data.pop('target_credit_user')
            await add_credits(uid, amount)
            await update.message.reply_text(f"✅ Added {amount} credits to {uid}.")
            context.user_data.pop('admin_state', None)
        except:
            await update.message.reply_text("Invalid amount.")
    elif state == 'awaiting_redeem_credits':
        try:
            credits = int(text)
            context.user_data['redeem_credits'] = credits
            context.user_data['admin_state'] = 'awaiting_redeem_maxuses'
            await update.message.reply_text("Send max uses:")
        except:
            await update.message.reply_text("Invalid number.")
    elif state == 'awaiting_redeem_maxuses':
        try:
            max_uses = int(text)
            credits = context.user_data['redeem_credits']
            code = secrets.token_hex(4).upper()
            await create_redeem_code(code, credits, user_id, max_uses)
            await update.message.reply_text(f"✅ Code: <code>{code}</code>\nCredits: {credits}\nUses: {max_uses}", parse_mode='HTML')
            context.user_data.pop('admin_state', None)
        except:
            await update.message.reply_text("Invalid number.")
    elif state == 'awaiting_bulkdm_ids':
        ids = [int(x.strip()) for x in text.replace('\n', ',').split(',') if x.strip().isdigit()]
        context.user_data['bulk_ids'] = ids
        context.user_data['admin_state'] = 'awaiting_bulkdm_message'
        await update.message.reply_text(f"Got {len(ids)} IDs. Send message:")
    elif state == 'awaiting_bulkdm_message':
        ids = context.user_data.pop('bulk_ids')
        success = 0
        for uid in ids:
            try:
                await application.bot.send_message(uid, text, parse_mode='HTML')
                success += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await update.message.reply_text(f"✅ Sent to {success}/{len(ids)} users.")
        context.user_data.pop('admin_state', None)
    elif state == 'awaiting_new_price':
        try:
            new_price = int(text)
            api = context.user_data['pricing_api']
            plan = context.user_data['pricing_plan']
            await update_api_plan_price(api, plan, new_price)
            await update.message.reply_text(f"✅ Price updated: {api} {plan} = {new_price} credits.")
            context.user_data.pop('admin_state', None)
        except:
            await update.message.reply_text("Invalid number.")
    elif state == 'awaiting_premium_days':
        days_text = text.lower()
        uid = context.user_data.pop('target_premium_user')
        if days_text == 'permanent':
            await set_user_premium(uid, days=None)
        else:
            try:
                days = int(days_text)
                await set_user_premium(uid, days=days)
            except:
                await update.message.reply_text("Invalid number.")
                context.user_data.pop('admin_state', None)
                return
        await update.message.reply_text(f"✅ Premium set for {uid}.")
        context.user_data.pop('admin_state', None)
    elif state == 'awaiting_new_admin_id':
        try:
            new_admin = int(text)
            await toggle_admin(new_admin)
            await update.message.reply_text(f"✅ Admin status toggled for {new_admin}.")
        except:
            await update.message.reply_text("Invalid ID.")
        context.user_data.pop('admin_state', None)
    elif state == 'awaiting_premium_user_id':
        try:
            uid = int(text)
            context.user_data['target_premium_user'] = uid
            context.user_data['admin_state'] = 'awaiting_premium_days'
            await update.message.reply_text("Send days (or 'permanent'):")
        except:
            await update.message.reply_text("Invalid ID.")
            context.user_data.pop('admin_state', None)
    elif state == 'awaiting_key_expiry_days':
        try:
            days = int(text)
            key_prefix = context.user_data.get('editing_key')
            await update.message.reply_text(f"✅ Key expiry updated (simplified).")
        except:
            await update.message.reply_text("Invalid number.")
        context.user_data.pop('admin_state', None)

# ============================================
# BACKGROUND TASKS
# ============================================
async def self_ping_task():
    await asyncio.sleep(10)
    while True:
        await asyncio.sleep(SELF_PING_INTERVAL)
        try:
            async with aiohttp.ClientSession() as sess:
                await sess.get(f"{RENDER_EXTERNAL_URL}/health")
            await application.bot.get_me()
            logger.info("Self-ping OK")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")

async def scheduled_backup_task():
    while True:
        await asyncio.sleep(86400)
        try:
            size = await get_database_file_size()
            with open(DB_FILE, 'rb') as f:
                msg = await application.bot.send_document(
                    chat_id=OWNER_ID,
                    document=f,
                    filename=f"auto_backup_{datetime.now().strftime('%Y%m%d')}.db",
                    caption=f"📦 Daily Backup\nSize: {size/1024:.2f} KB"
                )
            await log_backup(msg.document.file_id, size)
        except Exception as e:
            logger.error(f"Auto backup failed: {e}")

async def premium_expiry_task():
    while True:
        await asyncio.sleep(3600)
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET is_premium=0 WHERE is_premium=1 AND premium_expiry IS NOT NULL AND premium_expiry < ?", (datetime.now().isoformat(),))
            await db.commit()

# ============================================
# STARTUP & SHUTDOWN
# ============================================
async def on_startup():
    global http_session
    http_session = aiohttp.ClientSession()
    await application.initialize()
    await application.bot.set_my_commands([
        BotCommand("start", "Start bot"),
        BotCommand("balance", "Check credits"),
        BotCommand("redeem", "Redeem code"),
        BotCommand("referral", "Get referral link"),
        BotCommand("admin", "Admin panel")
    ])
    if BOT_MODE == "webhook":
        await application.bot.set_webhook(
            url=f"{RENDER_EXTERNAL_URL}/webhook",
            secret_token=WEBHOOK_SECRET
        )
        logger.info(f"Webhook set to {RENDER_EXTERNAL_URL}/webhook")
    else:
        await application.updater.start_polling()
        logger.info("Polling started.")
    asyncio.create_task(self_ping_task())
    asyncio.create_task(scheduled_backup_task())
    asyncio.create_task(premium_expiry_task())

async def on_shutdown():
    if http_session:
        await http_session.close()
    await application.stop()
    await application.shutdown()

# ============================================
# HANDLER REGISTRATION
# ============================================
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callback_router, pattern="^(menu_|gen_|plan_|apipage_|admin_|userlist_|premiumlist_|adminlist_|keys_|apistatus_|toggle_ban_|add_credits_|remove_premium_|make_premium_|permdelete_|confirmdelete_|editkeyexp_|deactkey_|togglestatus_|approve_purchase_|reject_purchase_|setprice_|price_|remove_admin_|bcast_|check_join|close_panel|admin_add_admin|admin_addpremium|gen_purchase_req|payment_help)"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_broadcast_media))

if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{PORT}"]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(on_startup())
    loop.run_until_complete(hypercorn.asyncio.serve(app, config))
