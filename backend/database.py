import aiosqlite
import sqlite3
import logging
import json
from datetime import datetime
import hashlib

log = logging.getLogger("ServerOS.DB")

class DatabaseManager:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection = None

    async def initialise(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self._conn.commit()
        log.info(f"Database ready at {self.path}")

    async def _create_tables(self):
        tables = [
            # Dashboard Users
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            # Guild registry
            """CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                member_count INTEGER DEFAULT 0,
                joined_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )""",
            # Cog States (Per Guild)
            """CREATE TABLE IF NOT EXISTS cog_states (
                guild_id INTEGER NOT NULL,
                cog_name TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, cog_name),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )""",
            # Guild settings
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                welcome_channel INTEGER,
                log_channel INTEGER,
                auto_role INTEGER,
                leave_channel INTEGER,
                settings_json TEXT DEFAULT '{}',
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )""",
            # Economy
            """CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                balance INTEGER DEFAULT 0,
                last_daily TEXT,
                last_weekly TEXT,
                total_earned INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )""",
            # Analytics
            """CREATE TABLE IF NOT EXISTS analytics (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                msg_count INTEGER DEFAULT 0,
                date TEXT NOT NULL,
                PRIMARY KEY (user_id, guild_id, channel_id, date),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )""",
            # Audit Logs
            """CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )""",
            # Reminders
            """CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                fire_at TEXT NOT NULL,
                done INTEGER DEFAULT 0
            )""",
            # Warnings
            """CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mod_id INTEGER NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )""",
            # Cases (Mod Actions)
            """CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mod_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL
            )""",
            # Shop
            """CREATE TABLE IF NOT EXISTS shop (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                role_id INTEGER,
                stock INTEGER DEFAULT -1
            )""",
            # Inventory
            """CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, guild_id, item_id),
                FOREIGN KEY (item_id) REFERENCES shop(id) ON DELETE CASCADE
            )""",
            # AI Context
            """CREATE TABLE IF NOT EXISTS ai_context (
                user_id INTEGER PRIMARY KEY,
                history_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        ]
        for ddl in tables:
            await self._conn.execute(ddl)
        
        # Create default admin user if not exists (admin/admin)
        admin_exists = await self.fetchone("SELECT id FROM users WHERE username = ?", ("admin",))
        if not admin_exists:
            hashed_pw = hashlib.sha256("admin".encode()).hexdigest()
            await self.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                ("admin", hashed_pw, datetime.utcnow().isoformat())
            )

    async def fetchone(self, sql: str, params: tuple = ()):
        async with self._conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()):
        async with self._conn.execute(sql, params) as cur:
            return await cur.fetchall()

    async def execute(self, sql: str, params: tuple = ()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    # --- Auth Methods ---
    async def authenticate_user(self, username, password):
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        user = await self.fetchone(
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, hashed_pw)
        )
        return dict(user) if user else None

    # --- Guild Methods ---
    async def add_guild(self, guild_id: int, name: str, owner_id: int, member_count: int):
        await self.execute(
            """INSERT INTO guilds (guild_id, name, owner_id, member_count, joined_at, is_active)
               VALUES (?, ?, ?, ?, ?, 1)
               ON CONFLICT(guild_id) DO UPDATE SET
                   name=excluded.name,
                   owner_id=excluded.owner_id,
                   member_count=excluded.member_count,
                   is_active=1""",
            (guild_id, name, owner_id, member_count, datetime.utcnow().isoformat()),
        )

    async def deactivate_guild(self, guild_id: int):
        await self.execute("UPDATE guilds SET is_active=0 WHERE guild_id=?", (guild_id,))

    async def get_all_guilds(self):
        rows = await self.fetchall("SELECT * FROM guilds WHERE is_active=1")
        return [dict(r) for r in rows]

    # --- Cog Control ---
    async def get_cog_states(self, guild_id: int):
        rows = await self.fetchall("SELECT cog_name, enabled FROM cog_states WHERE guild_id=?", (guild_id,))
        return {r['cog_name']: bool(r['enabled']) for r in rows}

    async def set_cog_state(self, guild_id: int, cog_name: str, enabled: bool):
        await self.execute(
            "INSERT INTO cog_states (guild_id, cog_name, enabled) VALUES (?, ?, ?) ON CONFLICT(guild_id, cog_name) DO UPDATE SET enabled=excluded.enabled",
            (guild_id, cog_name, int(enabled))
        )

    # --- Analytics ---
    async def get_global_stats(self):
        guild_count = await self.fetchone("SELECT COUNT(*) FROM guilds WHERE is_active=1")
        total_msgs = await self.fetchone("SELECT SUM(msg_count) FROM analytics")
        return {
            "total_guilds": guild_count[0] if guild_count else 0,
            "total_messages": total_msgs[0] if total_msgs and total_msgs[0] else 0
        }
    
    async def log_message(self, user_id, guild_id, channel_id):
        today = datetime.utcnow().date().isoformat()
        await self.execute(
            """INSERT INTO analytics (user_id, guild_id, channel_id, msg_count, date)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(user_id, guild_id, channel_id, date)
               DO UPDATE SET msg_count = msg_count + 1""",
            (user_id, guild_id, channel_id, today),
        )

    # --- Reminders ---
    async def add_reminder(self, user_id, channel_id, guild_id, message, fire_at):
        await self.execute(
            "INSERT INTO reminders (user_id, channel_id, guild_id, message, fire_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, channel_id, guild_id, message, fire_at)
        )

    async def get_pending_reminders(self):
        now = datetime.utcnow().isoformat()
        rows = await self.fetchall("SELECT * FROM reminders WHERE fire_at <= ? AND done = 0", (now,))
        return [dict(r) for r in rows]

    async def mark_reminder_done(self, reminder_id):
        await self.execute("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))

    # --- Moderation ---
    async def add_warning(self, guild_id, user_id, mod_id, reason):
        await self.execute(
            "INSERT INTO warnings (guild_id, user_id, mod_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, mod_id, reason, datetime.utcnow().isoformat())
        )

    async def get_warnings(self, guild_id, user_id):
        rows = await self.fetchall("SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? AND active = 1", (guild_id, user_id))
        return [dict(r) for r in rows]

    async def add_case(self, guild_id, user_id, mod_id, action, reason):
        await self.execute(
            "INSERT INTO cases (guild_id, user_id, mod_id, action, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, mod_id, action, reason, datetime.utcnow().isoformat())
        )

    # --- Economy Methods ---
    async def _ensure_economy_user(self, user_id, guild_id):
        exists = await self.fetchone("SELECT 1 FROM economy WHERE user_id=? AND guild_id=?", (user_id, guild_id))
        if not exists:
            await self.execute(
                "INSERT INTO economy (user_id, guild_id, balance, total_earned) VALUES (?, ?, ?, ?)",
                (user_id, guild_id, 50, 0) # Default starting balance
            )

    async def get_balance(self, user_id, guild_id):
        await self._ensure_economy_user(user_id, guild_id)
        row = await self.fetchone("SELECT * FROM economy WHERE user_id=? AND guild_id=?", (user_id, guild_id))
        return dict(row)

    async def update_balance(self, user_id, guild_id, amount):
        await self._ensure_economy_user(user_id, guild_id)
        if amount > 0:
            await self.execute(
                "UPDATE economy SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id=? AND guild_id=?",
                (amount, amount, user_id, guild_id)
            )
        else:
            await self.execute(
                "UPDATE economy SET balance = balance + ? WHERE user_id=? AND guild_id=?",
                (amount, user_id, guild_id)
            )

    async def get_leaderboard(self, guild_id, limit=10):
        rows = await self.fetchall(
            "SELECT user_id, balance FROM economy WHERE guild_id=? ORDER BY balance DESC LIMIT ?",
            (guild_id, limit)
        )
        return [dict(r) for r in rows]

    # --- Analytics Methods ---
    async def get_user_stats(self, user_id, guild_id):
        row = await self.fetchone(
            "SELECT SUM(msg_count) as total, COUNT(DISTINCT date) as days_active FROM analytics WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        return dict(row) if row else {"total": 0, "days_active": 0}

    async def get_top_users(self, guild_id, limit=10):
        rows = await self.fetchall(
            "SELECT user_id, SUM(msg_count) as total FROM analytics WHERE guild_id=? GROUP BY user_id ORDER BY total DESC LIMIT ?",
            (guild_id, limit)
        )
        return [dict(r) for r in rows]

    # --- Automation Methods ---
    async def get_guild_settings(self, guild_id):
        row = await self.fetchone("SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,))
        if not row:
            await self.execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
            row = await self.fetchone("SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,))
        return dict(row)

    async def set_guild_setting(self, guild_id, key, value):
        # Ensure row exists
        await self.get_guild_settings(guild_id)
        await self.execute(f"UPDATE guild_settings SET {key}=? WHERE guild_id=?", (value, guild_id))

    # --- Games Methods ---
    async def update_trivia(self, user_id, guild_id, won: bool):
        # Ensure table exists
        await self.execute("""CREATE TABLE IF NOT EXISTS trivia_stats (
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )""")
        if won:
            await self.execute(
                "INSERT INTO trivia_stats (user_id, guild_id, wins) VALUES (?, ?, 1) ON CONFLICT(user_id, guild_id) DO UPDATE SET wins = wins + 1",
                (user_id, guild_id)
            )
        else:
            await self.execute(
                "INSERT INTO trivia_stats (user_id, guild_id, losses) VALUES (?, ?, 1) ON CONFLICT(user_id, guild_id) DO UPDATE SET losses = losses + 1",
                (user_id, guild_id)
            )

    async def get_trivia_leaderboard(self, guild_id, limit=10):
        rows = await self.fetchall(
            "SELECT * FROM trivia_stats WHERE guild_id=? ORDER BY wins DESC LIMIT ?",
            (guild_id, limit)
        )
        return [dict(r) for r in rows]
