# keyboards.py - PROFESSIONAL INLINE KEYBOARDS (NULL PROTOCOL MULTI-API BOT)
# Owner: @Nullprotocol_X | ID: 8104850843

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import API_ENDPOINTS, BRANDING, OWNER_USERNAME

# ============================================
# HELPER FUNCTIONS
# ============================================
def back_button(callback_data: str = "menu_start", text: str = "🔙 Back") -> InlineKeyboardButton:
    """Standard back button for navigation."""
    return InlineKeyboardButton(text, callback_data=callback_data)

def close_button(callback_data: str = "close_panel", text: str = "❌ Close") -> InlineKeyboardButton:
    """Standard close button."""
    return InlineKeyboardButton(text, callback_data=callback_data)

# ============================================
# MAIN MENU (User & Admin)
# ============================================
def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main menu shown on /start. Different for admin/owner."""
    buttons = [
        [InlineKeyboardButton("🔑 Generate API Key", callback_data="menu_genkey"),
         InlineKeyboardButton("📘 API Docs", callback_data="menu_apihelp")],
        [InlineKeyboardButton("👤 My Keys", callback_data="menu_mykeys"),
         InlineKeyboardButton("💰 Balance & Plans", callback_data="menu_balance")],
        [InlineKeyboardButton("🔗 Referral", callback_data="menu_referral"),
         InlineKeyboardButton("🎟️ Redeem Code", callback_data="menu_redeem")],
        [InlineKeyboardButton("💳 Buy Credits", callback_data="menu_buycredits")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("🛡️ Admin Panel", callback_data="menu_admin")])
    return InlineKeyboardMarkup(buttons)

# ============================================
# ADMIN PANEL
# ============================================
def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Full admin control panel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
        [InlineKeyboardButton("🔑 All API Keys", callback_data="admin_keys"),
         InlineKeyboardButton("⭐ Premium Users", callback_data="admin_premium")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton("📨 Bulk DM", callback_data="admin_bulkdm")],
        [InlineKeyboardButton("💳 Add Credits", callback_data="admin_addcredits"),
         InlineKeyboardButton("🎟️ Gen Redeem Code", callback_data="admin_genredeem")],
        [InlineKeyboardButton("💰 Set API Prices", callback_data="admin_pricing"),
         InlineKeyboardButton("🛒 Pending Purchases", callback_data="admin_purchases")],
        [InlineKeyboardButton("👑 Manage Admins", callback_data="admin_admins"),
         InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ API Status", callback_data="admin_apistatus"),
         InlineKeyboardButton("💾 Backup DB", callback_data="admin_backup")],
        [close_button("close_panel", "❌ Close Admin Panel")]
    ])

# ============================================
# API SELECTION (Paginated - 20+ APIs)
# ============================================
def api_selection_keyboard(page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """
    Paginated keyboard showing all enabled APIs for key generation.
    Returns list of API types with their display names.
    """
    # Filter only enabled APIs from config
    enabled_apis = [(key, cfg['name']) for key, cfg in API_ENDPOINTS.items() if cfg.get('enabled', True)]
    total = len(enabled_apis)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    start = page * per_page
    end = start + per_page
    current_apis = enabled_apis[start:end]

    keyboard = []
    for api_type, display_name in current_apis:
        keyboard.append([InlineKeyboardButton(display_name, callback_data=f"gen_{api_type}")])

    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"apipage_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"apipage_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([back_button("menu_genkey")])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# PLANS & PURCHASE
# ============================================
def api_plans_keyboard(api_type: str) -> InlineKeyboardMarkup:
    """Show weekly/monthly plans for a specific API."""
    api_name = API_ENDPOINTS.get(api_type, {}).get('name', api_type.upper())
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 Weekly - {api_name}", callback_data=f"plan_{api_type}_weekly")],
        [InlineKeyboardButton(f"📆 Monthly - {api_name}", callback_data=f"plan_{api_type}_monthly")],
        [back_button("menu_balance")]
    ])

def buy_credits_menu_keyboard() -> InlineKeyboardMarkup:
    """Menu for purchasing credits manually."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Generate Transaction ID", callback_data="gen_purchase_req")],
        [InlineKeyboardButton("ℹ️ Payment Instructions", callback_data="payment_help")],
        [back_button("menu_start")]
    ])

def payment_help_keyboard() -> InlineKeyboardMarkup:
    """Instructions for manual credit purchase."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📲 Contact {OWNER_USERNAME}", url=f"https://t.me/{OWNER_USERNAME.replace('@', '')}")],
        [back_button("menu_buycredits")]
    ])

# ============================================
# USER MANAGEMENT (Paginated)
# ============================================
def user_management_keyboard(users: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """
    Display list of users with action buttons.
    users: list of tuples (user_id, username, first_name, is_banned, is_premium, credits)
    """
    keyboard = []
    for user in users:
        uid, username, first_name, banned, premium, credits = user
        name = first_name or str(uid)
        status = "🚫" if banned else ("⭐" if premium else "✅")
        # Row 1: User info button (for detail view)
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {name} | 💰{credits}",
                callback_data=f"userdetail_{uid}"
            )
        ])
        # Row 2: Action buttons
        action_row = []
        if banned:
            action_row.append(InlineKeyboardButton("✅ Unban", callback_data=f"toggle_ban_{uid}"))
        else:
            action_row.append(InlineKeyboardButton("🚫 Ban", callback_data=f"toggle_ban_{uid}"))
        action_row.append(InlineKeyboardButton("💳 Add Credits", callback_data=f"add_credits_{uid}"))
        if premium:
            action_row.append(InlineKeyboardButton("❌ Remove Premium", callback_data=f"remove_premium_{uid}"))
        else:
            action_row.append(InlineKeyboardButton("⭐ Make Premium", callback_data=f"make_premium_{uid}"))
        keyboard.append(action_row)
        # Row 3: Delete user
        keyboard.append([
            InlineKeyboardButton("🗑️ Permanent Delete", callback_data=f"permdelete_{uid}")
        ])

    # Navigation
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"userlist_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"userlist_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([back_button("menu_admin")])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# PREMIUM USERS LIST (Paginated)
# ============================================
def premium_users_keyboard(users: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Display premium users with remove option."""
    keyboard = []
    for user in users:
        uid, username, first_name, expiry = user
        name = first_name or str(uid)
        exp_str = expiry[:10] if expiry else "Permanent"
        keyboard.append([
            InlineKeyboardButton(f"⭐ {name} | Exp: {exp_str}", callback_data=f"premdetail_{uid}")
        ])
        keyboard.append([
            InlineKeyboardButton("❌ Remove Premium", callback_data=f"remove_premium_{uid}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"premiumlist_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"premiumlist_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("➕ Add Premium User", callback_data="admin_addpremium"),
        back_button("menu_admin")
    ])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# API KEYS LIST (Paginated)
# ============================================
def api_keys_list_keyboard(keys: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """
    keys: list of tuples (key, expires_at, rate_limit, custom_name, is_active, created_by?)
    """
    keyboard = []
    for key_data in keys:
        key = key_data[0]
        expires = key_data[1][:10] if key_data[1] else "Unknown"
        active = key_data[4] if len(key_data) > 4 else 1
        status = "✅" if active else "❌"
        short_key = key[:12] + "..." + key[-4:] if len(key) > 20 else key
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {short_key} | Exp: {expires}",
                callback_data=f"keydetail_{key[:20]}"
            )
        ])
        # Admin actions: Edit Expiry, Deactivate
        keyboard.append([
            InlineKeyboardButton("📅 Edit Expiry", callback_data=f"editkeyexp_{key[:20]}"),
            InlineKeyboardButton("🚫 Deactivate", callback_data=f"deactkey_{key[:20]}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"keys_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"keys_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([back_button("menu_admin")])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# API STATUS MANAGEMENT
# ============================================
def api_status_keyboard(page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """List all APIs with enable/disable toggle."""
    apis = list(API_ENDPOINTS.keys())
    total = len(apis)
    total_pages = (total + per_page - 1) // per_page

    start = page * per_page
    end = start + per_page
    current_apis = apis[start:end]

    keyboard = []
    for api_type in current_apis:
        cfg = API_ENDPOINTS[api_type]
        name = cfg.get('name', api_type)
        status = "🟢" if cfg.get('enabled', True) else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {name}",
                callback_data=f"togglestatus_{api_type}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"apistatus_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"apistatus_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([back_button("menu_admin")])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# SET PRICING KEYBOARD
# ============================================
def pricing_api_selection_keyboard() -> InlineKeyboardMarkup:
    """Select API to set pricing."""
    apis = list(API_ENDPOINTS.keys())
    keyboard = []
    for api_type in apis[:12]:  # Limit to 12 for UI
        name = API_ENDPOINTS[api_type].get('name', api_type)
        keyboard.append([InlineKeyboardButton(name, callback_data=f"setprice_{api_type}")])
    keyboard.append([back_button("menu_admin")])
    return InlineKeyboardMarkup(keyboard)

def pricing_plan_selection_keyboard(api_type: str) -> InlineKeyboardMarkup:
    """Select plan (weekly/monthly) for price update."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Weekly", callback_data=f"price_{api_type}_weekly")],
        [InlineKeyboardButton("📆 Monthly", callback_data=f"price_{api_type}_monthly")],
        [back_button("admin_pricing")]
    ])

# ============================================
# PENDING PURCHASES
# ============================================
def pending_purchases_keyboard(requests: list) -> InlineKeyboardMarkup:
    """
    requests: list of (request_id, user_id, credits_amount, transaction_id, created_at)
    """
    keyboard = []
    for req in requests[:8]:  # Max 8 to avoid overflow
        req_id, uid, credits, txn_id, created = req
        short_txn = txn_id[:10] + "..."
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {uid} | 💰 {credits} | {short_txn}",
                callback_data=f"viewpurchase_{txn_id}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_purchase_{txn_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_purchase_{txn_id}")
        ])

    keyboard.append([back_button("menu_admin")])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# BROADCAST TYPE SELECTION
# ============================================
def broadcast_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Text", callback_data="bcast_text")],
        [InlineKeyboardButton("🖼️ Photo", callback_data="bcast_photo")],
        [InlineKeyboardButton("🎥 Video", callback_data="bcast_video")],
        [InlineKeyboardButton("📁 Document", callback_data="bcast_doc")],
        [back_button("menu_admin")]
    ])

# ============================================
# ADMIN LIST (Paginated)
# ============================================
def admin_list_keyboard(admins: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    keyboard = []
    for admin in admins:
        uid, username, first_name = admin
        name = first_name or str(uid)
        keyboard.append([
            InlineKeyboardButton(f"👑 {name}", callback_data=f"admindetail_{uid}")
        ])
        keyboard.append([
            InlineKeyboardButton("❌ Remove Admin", callback_data=f"remove_admin_{uid}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"adminlist_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"adminlist_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("➕ Add Admin", callback_data="admin_add_admin"),
        back_button("menu_admin")
    ])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# STATS KEYBOARD
# ============================================
def stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_stats")],
        [back_button("menu_admin")]
    ])

# ============================================
# SIMPLE CONFIRMATION KEYBOARDS
# ============================================
def confirm_delete_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirmdelete_{user_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin_users")
        ]
    ])

def back_to_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[back_button("menu_admin")]])

# ============================================
# GENERIC PAGINATION HELPER (Optional)
# ============================================
def pagination_row(prefix: str, page: int, total_pages: int) -> list:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️", callback_data=f"{prefix}_{page-1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("▶️", callback_data=f"{prefix}_{page+1}"))
    return row
