"""
cogs/utilities.py — General utility commands.
Commands: ping, uptime, avatar, serverinfo, userinfo, remind, reminders, weather, help
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
from datetime import datetime, timedelta
import asyncio


class Utilities(BaseCog):
    """🔧 Utility commands — info, reminders, and more."""

    def __init__(self, bot):
        super().__init__(bot)
        self._start_time = datetime.utcnow()
        self.bot.loop.create_task(self._reminder_loop())

    # ── Reminder background loop ──────────────────────────────────────────────
    async def _reminder_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                rows = await self.db.get_pending_reminders()
                for row in rows:
                    ch = self.bot.get_channel(row["channel_id"])
                    if ch:
                        user = self.bot.get_user(row["user_id"])
                        mention = user.mention if user else f"<@{row['user_id']}>"
                        await ch.send(
                            embed=self.info_embed(
                                "⏰ Reminder",
                                f"{mention}: {row['message']}"
                            )
                        )
                    await self.db.mark_reminder_done(row["id"])
            except Exception as e:
                self.log.error(f"Reminder loop error: {e}")
            await asyncio.sleep(30)

    # ═══════════════════════════════════════════════════════════════════════════
    # PING
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="ping", description="Check the bot's latency.")
    async def ping(self, ctx):
        ws = round(self.bot.latency * 1000)
        start = datetime.utcnow()
        msg = await ctx.send(embed=self.info_embed("🏓 Pong!", f"WebSocket: **{ws}ms**"))
        rtt = round((datetime.utcnow() - start).total_seconds() * 1000)
        await msg.edit(embed=self.info_embed("🏓 Pong!", f"WebSocket: **{ws}ms**\nRoundtrip: **{rtt}ms**"))

    # ═══════════════════════════════════════════════════════════════════════════
    # UPTIME
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="uptime", description="How long has the bot been running?")
    async def uptime(self, ctx):
        delta = datetime.utcnow() - self._start_time
        d = delta.days
        h, rem = divmod(delta.seconds, 3600)
        m, s = divmod(rem, 60)
        await ctx.send(embed=self.info_embed(
            "⏱️ Uptime",
            f"**{d}d {h}h {m}m {s}s**"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # AVATAR
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="avatar", aliases=["av", "pfp"], description="Get a user's avatar.")
    @app_commands.describe(member="Member to get avatar of")
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        e = discord.Embed(title=f"{member.display_name}'s Avatar", color=0x5865F2)
        e.set_image(url=member.display_avatar.url)
        e.add_field(name="Links",
                    value=f"[PNG]({member.display_avatar.with_format('png').url}) | "
                          f"[WEBP]({member.display_avatar.with_format('webp').url})")
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # SERVERINFO
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="serverinfo", aliases=["si", "guildinfo"], description="Information about this server.")
    async def serverinfo(self, ctx):
        g = ctx.guild
        e = self.info_embed(g.name, g.description or "")
        if g.icon:
            e.set_thumbnail(url=g.icon.url)

        bots = sum(1 for m in g.members if m.bot)
        humans = g.member_count - bots
        text_ch = len(g.text_channels)
        voice_ch = len(g.voice_channels)

        e.add_field(name="👑 Owner", value=g.owner.mention, inline=True)
        e.add_field(name="📅 Created", value=g.created_at.strftime("%b %d, %Y"), inline=True)
        e.add_field(name="🌍 Region", value=str(g.preferred_locale), inline=True)
        e.add_field(name="👥 Members", value=f"{humans} humans, {bots} bots", inline=True)
        e.add_field(name="💬 Channels", value=f"{text_ch} text, {voice_ch} voice", inline=True)
        e.add_field(name="🎭 Roles", value=len(g.roles), inline=True)
        e.add_field(name="😀 Emojis", value=f"{len(g.emojis)}/{g.emoji_limit}", inline=True)
        e.add_field(name="🔒 Verification", value=str(g.verification_level).title(), inline=True)
        e.add_field(name="🚀 Boosts", value=f"{g.premium_subscription_count} (Tier {g.premium_tier})", inline=True)
        e.set_footer(text=f"ID: {g.id}")
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # USERINFO
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="userinfo", aliases=["ui", "whois"], description="Info about a member.")
    @app_commands.describe(member="Member to inspect")
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        e = self.info_embed(str(member), "")
        e.set_thumbnail(url=member.display_avatar.url)

        roles = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        roles_str = " ".join(roles[:10]) + ("..." if len(roles) > 10 else "") if roles else "None"

        badges = []
        if member.bot:
            badges.append("🤖 Bot")
        if member.guild_permissions.administrator:
            badges.append("🛡️ Admin")
        if member.premium_since:
            badges.append("🚀 Booster")

        e.add_field(name="🪪 ID", value=member.id, inline=True)
        e.add_field(name="📛 Nickname", value=member.nick or "None", inline=True)
        e.add_field(name="🏷️ Badges", value=" | ".join(badges) or "None", inline=True)
        e.add_field(name="📅 Account Created", value=member.created_at.strftime("%b %d, %Y"), inline=True)
        e.add_field(name="📥 Joined Server", value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "?", inline=True)
        e.add_field(name="🎭 Top Role", value=member.top_role.mention, inline=True)
        e.add_field(name=f"🎭 Roles ({len(roles)})", value=roles_str, inline=False)
        e.set_footer(text=f"Status: {member.status}")
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # REMIND
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="remind", aliases=["remindme", "reminder"], description="Set a reminder.")
    @app_commands.describe(time="Time e.g. 10m, 2h, 1d", message="What to remind you about")
    async def remind(self, ctx, time: str, *, message: str):
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        unit = time[-1].lower()
        if unit not in units or not time[:-1].isdigit():
            return await ctx.send(embed=self.error_embed("Format: `!remind 10m Feed the cat`\nUnits: s, m, h, d"))

        seconds = int(time[:-1]) * units[unit]
        if seconds > 86400 * 30:
            return await ctx.send(embed=self.error_embed("Max reminder time is 30 days."))

        fire_at = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
        await self.db.add_reminder(ctx.author.id, ctx.channel.id, ctx.guild.id, message, fire_at)
        await ctx.send(embed=self.success_embed(f"⏰ I'll remind you in **{time}**: {message}"))

    # ═══════════════════════════════════════════════════════════════════════════
    # HELP
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="help", description="Show all commands.")
    @app_commands.describe(cog="Specific module to show help for")
    async def help(self, ctx, cog: str = None):
        prefix = self.config.PREFIX

        if cog:
            cog_obj = self.bot.cogs.get(cog.title())
            if not cog_obj:
                return await ctx.send(embed=self.error_embed(f"Module `{cog}` not found."))
            cmds = [c for c in cog_obj.get_commands() if not c.hidden]
            desc = "\n".join(
                f"`{prefix}{c.name}` — {c.description or c.brief or 'No description'}"
                for c in cmds
            )
            await ctx.send(embed=self.info_embed(f"📖 {cog.title()} Commands", desc or "No commands."))
            return

        e = self.info_embed(
            "📖 Server OS — Help",
            f"Prefix: `{prefix}` | Slash commands also available\n"
            f"Use `{prefix}help <module>` for detailed info.\n\n"
        )
        module_map = {
            "🛡️ Moderation": "warn, kick, ban, unban, mute, unmute, purge, lock, unlock, slowmode, history",
            "💰 Economy":     "balance, daily, weekly, give, leaderboard, shop, buy, inventory, additem",
            "🎮 Games":       "trivia, coinflip, roll, rps, guess, triviastats",
            "🔧 Utilities":   "ping, uptime, avatar, serverinfo, userinfo, remind, help",
            "🤖 AI":          "ask, clearchat",
            "📺 Media":       "youtube, color, define, weather",
            "📊 Analytics":   "stats, topusers, activity",
            "⚙️ Automation":  "setwelcome, setlogs, setautorole, announce",
        }
        for name, cmds in module_map.items():
            e.add_field(name=name, value=cmds, inline=False)
        e.set_footer(text="ServerOS Bot | All systems operational")
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # COLOR
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="color", description="Show a color from a hex code.")
    @app_commands.describe(hex_code="Hex color code e.g. FF5733")
    async def color(self, ctx, hex_code: str):
        hex_code = hex_code.strip("#")
        try:
            int(hex_code, 16)
            assert len(hex_code) == 6
        except Exception:
            return await ctx.send(embed=self.error_embed("Invalid hex code. Example: `FF5733`"))

        color_int = int(hex_code, 16)
        r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
        e = discord.Embed(color=color_int, title=f"🎨 #{hex_code.upper()}")
        e.add_field(name="RGB", value=f"({r}, {g}, {b})", inline=True)
        e.add_field(name="Decimal", value=str(color_int), inline=True)
        e.set_image(url=f"https://singlecolorimage.com/get/{hex_code}/200x100")
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Utilities(bot))
