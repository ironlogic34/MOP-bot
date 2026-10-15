"""
cogs/msglogger.py — Full message logger.
- Saves every message (up to 5000 per server) to a separate .txt file per server
- Format: [DATE TIME] [#channel] [Username (ID)]: message content
- On bot join new server → new file created automatically
- Commands: fetchlogs, searchlog, clearlog, logstats, exportlog
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
from datetime import datetime
import os
import asyncio


LOGS_DIR = "server_logs"       # folder where all log files are stored
MAX_MESSAGES = 5000            # max lines kept per server file


def _log_path(guild_id: int) -> str:
    """Return the path to a server's log file."""
    return os.path.join(LOGS_DIR, f"server_{guild_id}.txt")


def _ensure_logs_dir():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)


def _format_line(message: discord.Message) -> str:
    """Format a single message into a log line."""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    channel = f"#{message.channel.name}" if hasattr(message.channel, "name") else "#unknown"
    user = f"{message.author.name}#{message.author.discriminator}"
    uid = message.author.id
    content = message.content or "[no text content]"

    # Handle attachments
    if message.attachments:
        attach_urls = " | ".join(a.url for a in message.attachments)
        content += f" [ATTACHMENT: {attach_urls}]"

    # Handle embeds
    if message.embeds:
        content += " [EMBED]"

    return f"[{ts} UTC] [{channel}] [{user} ({uid})]: {content}\n"


def _trim_file(path: str):
    """Keep only the last MAX_MESSAGES lines in the file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_MESSAGES:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_MESSAGES:])
    except Exception:
        pass


class MsgLogger(BaseCog):
    """📝 Message logger — records every message per server into .txt files."""

    def __init__(self, bot):
        super().__init__(bot)
        _ensure_logs_dir()

    # ── Internal write helper (runs in executor so it never blocks) ───────────
    async def _write_line(self, guild_id: int, line: str):
        path = _log_path(guild_id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_write, path, line)

    def _sync_write(self, path: str, line: str):
        _ensure_logs_dir()
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        _trim_file(path)

    def _sync_write_header(self, path: str, guild: discord.Guild):
        _ensure_logs_dir()
        if not os.path.exists(path):
            header = (
                f"{'='*70}\n"
                f"  SERVER LOG — {guild.name} (ID: {guild.id})\n"
                f"  Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"  Max stored messages: {MAX_MESSAGES}\n"
                f"{'='*70}\n\n"
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(header)

    # ═══════════════════════════════════════════════════════════════════════════
    # EVENTS
    # ═══════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """When bot joins a new server, create its log file."""
        path = _log_path(guild.id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_write_header, path, guild)
        self.log.info(f"Created log file for new server: {guild.name} ({guild.id})")

    @commands.Cog.listener()
    async def on_ready(self):
        """On startup, make sure every existing server has a log file."""
        loop = asyncio.get_event_loop()
        for guild in self.bot.guilds:
            path = _log_path(guild.id)
            await loop.run_in_executor(None, self._sync_write_header, path, guild)
        self.log.info(f"Message logger ready. Tracking {len(self.bot.guilds)} server(s).")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Log every non-bot message."""
        if message.author.bot:
            return
        if not message.guild:
            return   # ignore DMs
        line = _format_line(message)
        await self._write_line(message.guild.id, line)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log message edits."""
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return

        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        channel = f"#{before.channel.name}"
        user = f"{before.author.name}#{before.author.discriminator}"
        uid = before.author.id
        line = (
            f"[{ts} UTC] [{channel}] [{user} ({uid})] [EDITED]\n"
            f"    BEFORE: {before.content or '[empty]'}\n"
            f"    AFTER:  {after.content or '[empty]'}\n"
        )
        await self._write_line(before.guild.id, line)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log message deletions."""
        if message.author.bot or not message.guild:
            return

        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        channel = f"#{message.channel.name}"
        user = f"{message.author.name}#{message.author.discriminator}"
        uid = message.author.id
        line = (
            f"[{ts} UTC] [{channel}] [{user} ({uid})] [DELETED]: "
            f"{message.content or '[no text]'}\n"
        )
        await self._write_line(message.guild.id, line)

    # ═══════════════════════════════════════════════════════════════════════════
    # FETCHLOGS — show last N lines in Discord
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="fetchlogs", description="Show the last N logged messages. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(count="How many lines to show (max 30)")
    async def fetchlogs(self, ctx, count: int = 10):
        count = min(count, 30)
        path = _log_path(ctx.guild.id)

        if not os.path.exists(path):
            return await ctx.send(embed=self.error_embed("No log file found for this server yet."))

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter out header lines (start with = or spaces)
        data_lines = [l for l in lines if l.startswith("[")]
        last = data_lines[-count:] if len(data_lines) >= count else data_lines

        if not last:
            return await ctx.send(embed=self.info_embed("📝 Message Log", "No messages logged yet."))

        content = "".join(last)
        # Discord embed limit 4096
        if len(content) > 3900:
            content = "..." + content[-3900:]

        await ctx.send(embed=self.info_embed(
            f"📝 Last {len(last)} Logged Messages",
            f"```\n{content}\n```"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # SEARCHLOG — search for keyword in log
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="searchlog", description="Search the message log for a keyword. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(keyword="Word or phrase to search for")
    async def searchlog(self, ctx, *, keyword: str):
        path = _log_path(ctx.guild.id)

        if not os.path.exists(path):
            return await ctx.send(embed=self.error_embed("No log file for this server."))

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        matches = [l for l in lines if keyword.lower() in l.lower() and l.startswith("[")]

        if not matches:
            return await ctx.send(embed=self.info_embed("🔍 Search", f"No results for `{keyword}`."))

        # Show last 15 matches
        shown = matches[-15:]
        content = "".join(shown)
        if len(content) > 3900:
            content = "..." + content[-3900:]

        await ctx.send(embed=self.info_embed(
            f"🔍 '{keyword}' — {len(matches)} match(es)",
            f"```\n{content}\n```"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # USERLOG — show all logged messages by a specific user
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="userlog", description="Show logged messages from a specific user. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(member="Member to look up", count="How many to show (max 20)")
    async def userlog(self, ctx, member: discord.Member, count: int = 10):
        count = min(count, 20)
        path = _log_path(ctx.guild.id)

        if not os.path.exists(path):
            return await ctx.send(embed=self.error_embed("No log file for this server."))

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Match by user ID (most reliable)
        uid_str = str(member.id)
        matches = [l for l in lines if uid_str in l and l.startswith("[")]

        if not matches:
            return await ctx.send(embed=self.info_embed(
                f"📝 Logs for {member}", "No messages found for this user."
            ))

        shown = matches[-count:]
        content = "".join(shown)
        if len(content) > 3900:
            content = "..." + content[-3900:]

        await ctx.send(embed=self.info_embed(
            f"📝 Last {len(shown)} messages by {member.display_name} ({len(matches)} total)",
            f"```\n{content}\n```"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORTLOG — send the full .txt file as a Discord attachment
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="exportlog", description="Download the full server log as a .txt file. (Admin)")
    @commands.has_permissions(administrator=True)
    async def exportlog(self, ctx):
        path = _log_path(ctx.guild.id)

        if not os.path.exists(path):
            return await ctx.send(embed=self.error_embed("No log file for this server yet."))

        size = os.path.getsize(path)
        if size == 0:
            return await ctx.send(embed=self.error_embed("Log file is empty."))

        # Discord file upload limit 8MB for non-boosted
        if size > 8_000_000:
            return await ctx.send(embed=self.error_embed(
                "Log file exceeds 8MB. Use `!searchlog` or `!fetchlogs` instead."
            ))

        file = discord.File(path, filename=f"log_{ctx.guild.name}_{datetime.utcnow().strftime('%Y%m%d')}.txt")
        await ctx.send(
            embed=self.success_embed(f"Here is the full log for **{ctx.guild.name}**."),
            file=file
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # LOGSTATS — how many messages logged, file size, etc.
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="logstats", description="Show log file stats for this server. (Admin)")
    @commands.has_permissions(administrator=True)
    async def logstats(self, ctx):
        path = _log_path(ctx.guild.id)

        if not os.path.exists(path):
            return await ctx.send(embed=self.error_embed("No log file for this server yet."))

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        data_lines = [l for l in lines if l.startswith("[")]
        edits = sum(1 for l in data_lines if "[EDITED]" in l)
        deletes = sum(1 for l in data_lines if "[DELETED]" in l)
        normal = len(data_lines) - edits - deletes
        size_kb = round(os.path.getsize(path) / 1024, 2)

        e = self.info_embed(f"📊 Log Stats — {ctx.guild.name}", "")
        e.add_field(name="💬 Messages", value=f"{normal:,}", inline=True)
        e.add_field(name="✏️ Edits Logged", value=f"{edits:,}", inline=True)
        e.add_field(name="🗑️ Deletes Logged", value=f"{deletes:,}", inline=True)
        e.add_field(name="📁 File Size", value=f"{size_kb} KB", inline=True)
        e.add_field(name="📝 Total Lines", value=f"{len(data_lines):,} / {MAX_MESSAGES:,}", inline=True)
        e.add_field(name="📂 File", value=f"`{os.path.basename(path)}`", inline=True)
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # CLEARLOG — wipe the log file (with confirmation)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="clearlog", description="Wipe the message log for this server. (Admin)")
    @commands.has_permissions(administrator=True)
    async def clearlog(self, ctx):
        path = _log_path(ctx.guild.id)

        if not os.path.exists(path):
            return await ctx.send(embed=self.error_embed("No log file to clear."))

        await ctx.send(embed=self.info_embed(
            "⚠️ Confirm",
            "This will **permanently delete** all logged messages for this server.\n"
            "Type `CONFIRM` in the next 15 seconds to proceed."
        ))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "CONFIRM"

        try:
            await self.bot.wait_for("message", timeout=15.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=self.error_embed("Cancelled — no confirmation received."))

        # Recreate with fresh header
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_write_header_force, path, ctx.guild)
        await ctx.send(embed=self.success_embed("Log file has been cleared and reset."))

    def _sync_write_header_force(self, path: str, guild: discord.Guild):
        """Overwrite file with fresh header."""
        _ensure_logs_dir()
        header = (
            f"{'='*70}\n"
            f"  SERVER LOG — {guild.name} (ID: {guild.id})\n"
            f"  Cleared & reset: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"  Max stored messages: {MAX_MESSAGES}\n"
            f"{'='*70}\n\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(header)


async def setup(bot):
    await bot.add_cog(MsgLogger(bot))
