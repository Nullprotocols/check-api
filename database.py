# database.py - COMPLETE ADVANCED ASYNC DATABASE LAYER
# Render Ready | All Tables + Functions | Owner: @Nullprotocol_X

import sqlite3
import secrets
import asyncio
import aiosqlite
import os
from datetime import datetime, timedelta
from config import DB_FILE, DEFAULT_PLANS, OWNER_ID, REFERRAL_REWARD_CREDITS

# ============================================
# SYNC CONNECTION (For initialization only)
# ============================================
sync_conn = sqlite3.connect(DB_FILE, check_same_thread=False)
sync_c = sync_conn.cursor()

# ============================================
# INIT DATABASE (Call once at startup)
# ============================================
def init_db_sync():
    # Users table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_banned INTEGER DEFAULT 0,
            is_owner INTEGER DEFAULT 0,
            joined_at TEXT,
            referrer_id INTEGER,
            credits INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            premium_expiry TEXT,
            joined_force_channels INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0
        )
    ''')

    # Add columns if missing (migration safe)
    for col, col_type in [
        ('referrer_id', 'INTEGER'),
        ('credits', 'INTEGER DEFAULT 0'),
        ('is_premium', 'INTEGER DEFAULT 0'),
        ('premium_expiry', 'TEXT'),
        ('joined_force_channels', 'INTEGER DEFAULT 0'),
        ('deleted', 'INTEGER DEFAULT 0')
    ]:
        try:
            sync_c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
        except:
            pass

    # API Keys table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            created_by INTEGER,
            created_at TEXT,
            expires_at TEXT,
            rate_limit_per_min INTEGER DEFAULT 80,
            is_active INTEGER DEFAULT 1,
            custom_name TEXT
        )
    ''')

    # API Plans table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS api_plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_type TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            price_credits INTEGER NOT NULL,
            duration_days INTEGER NOT NULL,
            UNIQUE(api_type, plan_name)
        )
    ''')

    # User Subscriptions table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            api_type TEXT NOT NULL,
            plan_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(plan_id) REFERENCES api_plans(plan_id)
        )
    ''')

    # Redeem Codes table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS redeem_codes (
            code TEXT PRIMARY KEY,
            credits_value INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Code Redemptions table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS code_redemptions (
            redemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            redeemed_at TEXT NOT NULL,
            UNIQUE(user_id, code)
        )
    ''')

    # Credit Purchase Requests table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS credit_purchase_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            credits_amount INTEGER NOT NULL,
            transaction_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            approved_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    # System Backups log table
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS system_backups (
            backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            backup_date TEXT NOT NULL,
            file_id TEXT,
            size_bytes INTEGER
        )
    ''')

    # API Status table (enable/disable APIs with custom message)
    sync_c.execute('''
        CREATE TABLE IF NOT EXISTS api_status (
            api_type TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            custom_message TEXT
        )
    ''')

    # Insert default plans from config
    for api_type, plans in DEFAULT_PLANS.items():
        for plan_name, details in plans.items():
            sync_c.execute('''
                INSERT OR IGNORE INTO api_plans (api_type, plan_name, price_credits, duration_days)
                VALUES (?, ?, ?, ?)
            ''', (api_type, plan_name, details['credits'], details['days']))

    # Ensure owner is marked as owner
    sync_c.execute("UPDATE users SET is_owner = 1 WHERE user_id = ?", (OWNER_ID,))
    sync_conn.commit()

    print("✅ Database tables initialized and owner set.")

# Call init
init_db_sync()

# ============================================
# ASYNC HELPER: Get DB Connection
# ============================================
async def get_db():
    db = await aiosqlite.connect(DB_FILE)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA cache_size=-20000")
    return db

# ============================================
# USER MANAGEMENT
# ============================================
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """SELECT user_id, username, first_name, last_name, is_banned, is_owner,
               joined_at, referrer_id, credits, is_premium, premium_expiry, deleted
               FROM users WHERE user_id=?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            now = datetime.now().isoformat()
            await db.execute(
                "INSERT INTO users (user_id, joined_at, credits, is_owner) VALUES (?, ?, ?, ?)",
                (user_id, now, 0, 1 if user_id == OWNER_ID else 0)
            )
            await db.commit()
            return {
                "user_id": user_id, "username": None, "first_name": None, "last_name": None,
                "is_banned": 0, "is_owner": 1 if user_id == OWNER_ID else 0, "joined_at": now,
                "referrer_id": None, "credits": 0, "is_premium": 0, "premium_expiry": None,
                "deleted": 0
            }
        return {
            "user_id": row[0], "username": row[1], "first_name": row[2], "last_name": row[3],
            "is_banned": row[4], "is_owner": row[5], "joined_at": row[6], "referrer_id": row[7],
            "credits": row[8] if row[8] is not None else 0,
            "is_premium": row[9] if len(row) > 9 else 0,
            "premium_expiry": row[10] if len(row) > 10 else None,
            "deleted": row[11] if len(row) > 11 else 0
        }

async def update_user_info(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE users SET username=?, first_name=?, last_name=? WHERE user_id=?",
            (username, first_name, last_name, user_id)
        )
        await db.commit()

async def set_referrer(user_id: int, referrer_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        if row and row[0] is None and user_id != referrer_id:
            await db.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (referrer_id, user_id))
            await db.commit()
            return True
        return False

async def add_credits(user_id: int, amount: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
        await db.commit()

async def deduct_credits(user_id: int, amount: int) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT credits FROM users WHERE user_id=? AND deleted=0", (user_id,))
        row = await cursor.fetchone()
        if row and row[0] >= amount:
            await db.execute("UPDATE users SET credits = credits - ? WHERE user_id=?", (amount, user_id))
            await db.commit()
            return True
        return False

async def get_user_credits(user_id: int) -> int:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT credits FROM users WHERE user_id=? AND deleted=0", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT is_owner FROM users WHERE user_id=? AND deleted=0", (user_id,))
        row = await cursor.fetchone()
        return row is not None and row[0] == 1

async def is_premium_active(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT is_premium, premium_expiry FROM users WHERE user_id=? AND deleted=0",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row or not row[0]:
            return False
        if row[1]:
            expiry = datetime.fromisoformat(row[1])
            if expiry < datetime.now():
                await db.execute("UPDATE users SET is_premium=0 WHERE user_id=?", (user_id,))
                await db.commit()
                return False
        return True

async def set_user_premium(user_id: int, days: int = None):
    expiry = None if days is None else (datetime.now() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE users SET is_premium=1, premium_expiry=? WHERE user_id=?",
            (expiry, user_id)
        )
        await db.commit()

async def remove_user_premium(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_premium=0, premium_expiry=NULL WHERE user_id=?", (user_id,))
        await db.commit()

async def get_all_premium_users():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT user_id, username, first_name, premium_expiry FROM users WHERE is_premium=1 AND deleted=0"
        )
        return await cursor.fetchall()

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        await db.commit()

async def permanently_delete_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM api_keys WHERE created_by=?", (user_id,))
        await db.execute("DELETE FROM user_subscriptions WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM code_redemptions WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM credit_purchase_requests WHERE user_id=?", (user_id,))
        await db.execute("UPDATE users SET deleted=1 WHERE user_id=?", (user_id,))
        await db.commit()

async def toggle_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT is_owner FROM users WHERE user_id=? AND deleted=0", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return False
        new_status = 0 if row[0] == 1 else 1
        await db.execute("UPDATE users SET is_owner=? WHERE user_id=?", (new_status, user_id))
        await db.commit()
        return True

# ============================================
# API KEY MANAGEMENT
# ============================================
async def generate_random_key():
    return f"ak_{secrets.token_hex(16)}"

async def create_api_key(key: str, created_by: int, expires_days: int = 30, rate_limit: int = 80, custom_name: str = ""):
    expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """INSERT OR REPLACE INTO api_keys
               (key, created_by, created_at, expires_at, rate_limit_per_min, is_active, custom_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (key, created_by, datetime.now().isoformat(), expires_at, rate_limit, 1, custom_name)
        )
        await db.commit()

async def validate_api_key(key: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT created_by, expires_at, rate_limit_per_min, is_active FROM api_keys WHERE key=?",
            (key,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, None, None
        created_by, expires_at, rate_limit, is_active = row
        if not is_active or datetime.now() > datetime.fromisoformat(expires_at):
            return False, None, None
        return True, created_by, rate_limit

async def list_api_keys(created_by: int = None):
    async with aiosqlite.connect(DB_FILE) as db:
        if created_by:
            cursor = await db.execute(
                "SELECT key, expires_at, rate_limit_per_min, custom_name, is_active FROM api_keys WHERE created_by=?",
                (created_by,)
            )
        else:
            cursor = await db.execute(
                "SELECT key, expires_at, rate_limit_per_min, custom_name, is_active, created_by FROM api_keys"
            )
        return await cursor.fetchall()

async def update_key_expiry(key: str, new_expiry_days: int):
    expires_at = (datetime.now() + timedelta(days=new_expiry_days)).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE api_keys SET expires_at=? WHERE key=?", (expires_at, key))
        await db.commit()

async def update_key_rate_limit(key: str, new_limit: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE api_keys SET rate_limit_per_min=? WHERE key=?", (new_limit, key))
        await db.commit()

async def deactivate_api_key(key: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE api_keys SET is_active=0 WHERE key=?", (key,))
        await db.commit()

# ============================================
# SUBSCRIPTIONS & PLANS
# ============================================
async def get_plan(api_type: str, plan_name: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT plan_id, price_credits, duration_days FROM api_plans WHERE api_type=? AND plan_name=?",
            (api_type, plan_name)
        )
        return await cursor.fetchone()

async def create_subscription(user_id: int, api_type: str, plan_name: str):
    plan = await get_plan(api_type, plan_name)
    if not plan:
        return False
    plan_id, price, days = plan
    if not await deduct_credits(user_id, price):
        return False
    start = datetime.now().isoformat()
    end = (datetime.now() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """INSERT INTO user_subscriptions
               (user_id, api_type, plan_id, start_date, end_date, is_active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, api_type, plan_id, start, end, 1)
        )
        await db.commit()
    return True

async def has_active_subscription(user_id: int, api_type: str) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT end_date FROM user_subscriptions WHERE user_id=? AND api_type=? AND is_active=1",
            (user_id, api_type)
        )
        row = await cursor.fetchone()
        if row:
            end = datetime.fromisoformat(row[0])
            if end > datetime.now():
                return True
            else:
                await db.execute(
                    "UPDATE user_subscriptions SET is_active=0 WHERE user_id=? AND api_type=?",
                    (user_id, api_type)
                )
                await db.commit()
        return False

async def update_api_plan_price(api_type: str, plan_name: str, new_price: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE api_plans SET price_credits=? WHERE api_type=? AND plan_name=?",
            (new_price, api_type, plan_name)
        )
        await db.commit()

# ============================================
# REDEEM CODES
# ============================================
async def create_redeem_code(code: str, credits: int, created_by: int, max_uses: int = 1, expires_days: int = None):
    expires = None if expires_days is None else (datetime.now() + timedelta(days=expires_days)).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """INSERT INTO redeem_codes
               (code, credits_value, created_by, created_at, expires_at, max_uses)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code, credits, created_by, datetime.now().isoformat(), expires, max_uses)
        )
        await db.commit()

async def redeem_code(user_id: int, code: str) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT credits_value, max_uses, used_count, expires_at, is_active FROM redeem_codes WHERE code=?",
            (code,)
        )
        row = await cursor.fetchone()
        if not row:
            return False
        value, max_uses, used, expires, active = row
        if not active or used >= max_uses or (expires and datetime.now() > datetime.fromisoformat(expires)):
            return False
        cursor = await db.execute(
            "SELECT redemption_id FROM code_redemptions WHERE user_id=? AND code=?",
            (user_id, code)
        )
        if await cursor.fetchone():
            return False
        await db.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (value, user_id))
        await db.execute("UPDATE redeem_codes SET used_count = used_count + 1 WHERE code=?", (code,))
        await db.execute(
            "INSERT INTO code_redemptions (user_id, code, redeemed_at) VALUES (?, ?, ?)",
            (user_id, code, datetime.now().isoformat())
        )
        await db.commit()
        return True

# ============================================
# CREDIT PURCHASE REQUESTS
# ============================================
async def create_purchase_request(user_id: int, credits: int) -> str:
    txn_id = f"TXN{secrets.token_hex(6).upper()}"
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """INSERT INTO credit_purchase_requests
               (user_id, credits_amount, transaction_id, created_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, credits, txn_id, datetime.now().isoformat())
        )
        await db.commit()
    return txn_id

async def get_pending_purchase_requests():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """SELECT request_id, user_id, credits_amount, transaction_id, created_at
               FROM credit_purchase_requests WHERE status='pending' ORDER BY created_at"""
        )
        return await cursor.fetchall()

async def approve_purchase_request(txn_id: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT user_id, credits_amount FROM credit_purchase_requests WHERE transaction_id=? AND status='pending'",
            (txn_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False
        user_id, credits = row
        await db.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (credits, user_id))
        await db.execute(
            "UPDATE credit_purchase_requests SET status='approved', approved_at=? WHERE transaction_id=?",
            (datetime.now().isoformat(), txn_id)
        )
        await db.commit()
        return True

async def reject_purchase_request(txn_id: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE credit_purchase_requests SET status='rejected' WHERE transaction_id=?",
            (txn_id,)
        )
        await db.commit()

# ============================================
# API STATUS MANAGEMENT
# ============================================
async def get_api_status(api_type: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT enabled, custom_message FROM api_status WHERE api_type=?", (api_type,))
        row = await cursor.fetchone()
        if row:
            return {"enabled": bool(row[0]), "message": row[1]}
        return {"enabled": True, "message": None}

async def set_api_status(api_type: str, enabled: bool, message: str = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT OR REPLACE INTO api_status (api_type, enabled, custom_message) VALUES (?, ?, ?)",
            (api_type, int(enabled), message)
        )
        await db.commit()

# ============================================
# BACKUP & STATS
# ============================================
async def get_database_file_size():
    try:
        return os.path.getsize(DB_FILE)
    except:
        return 0

async def log_backup(file_id: str, size: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO system_backups (backup_date, file_id, size_bytes) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), file_id, size)
        )
        await db.commit()

async def count_users():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_users_paginated(offset: int, limit: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """SELECT user_id, username, first_name, is_banned, is_premium, credits
               FROM users WHERE deleted=0 ORDER BY user_id LIMIT ? OFFSET ?""",
            (limit, offset)
        )
        return await cursor.fetchall()

async def count_admins():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_owner=1 AND deleted=0")
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_admins_paginated(offset: int, limit: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT user_id, username, first_name FROM users WHERE is_owner=1 AND deleted=0 ORDER BY user_id LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return await cursor.fetchall()

async def get_all_users_count():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        return (await cursor.fetchone())[0]

async def get_active_subscriptions_count():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM user_subscriptions WHERE is_active=1")
        return (await cursor.fetchone())[0]

async def get_total_keys_count():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM api_keys")
        return (await cursor.fetchone())[0]

# ============================================
# CLEANUP
# ============================================
async def close_db():
    sync_conn.close()
    print("✅ Database connections closed.")
