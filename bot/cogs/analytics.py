"""
cogs/analytics.py — Server analytics.
Events: on_message (passive tracking)
Commands: stats, topusers, activity
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
from datetime import datetime, timedelta


class Analytics(BaseCog):
    """📊 Server analytics — track activity and stats."""

    # ── Passive listener ──────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if not self.config.ANALYTICS_ENABLED:
            return
        try:
            await self.db.log_message(
                message.author.id,
                message.guild.id,
                message.channel.id
            )
        except Exception as e:
            self.log.error(f"Analytics log error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # STATS (personal)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="stats", description="View your or someone's message stats.")
    @app_commands.describe(member="Member to check (leave blank for yourself)")
    async def stats(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        row = await self.db.get_user_stats(member.id, ctx.guild.id)

        total = row["total"] or 0
        days = row["days_active"] or 0
        avg = round(total / days, 1) if days > 0 else 0

        # Get their most active channel
        channel_row = await self.db.fetchone(
            """SELECT channel_id, SUM(msg_count) as cnt FROM analytics
               WHERE user_id=? AND guild_id=?
               GROUP BY channel_id ORDER BY cnt DESC LIMIT 1""",
            (member.id, ctx.guild.id)
        )

        e = self.info_embed(f"📊 Stats — {member.display_name}", "")
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="💬 Total Messages", value=f"{total:,}", inline=True)
        e.add_field(name="📅 Days Active", value=str(days), inline=True)
        e.add_field(name="📈 Daily Average", value=str(avg), inline=True)

        if channel_row and channel_row["channel_id"]:
            ch = ctx.guild.get_channel(channel_row["channel_id"])
            ch_name = ch.mention if ch else f"<#{channel_row['channel_id']}>"
            e.add_field(name="🏆 Most Active In", value=ch_name, inline=True)

        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # TOPUSERS (leaderboard)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="topusers", aliases=["topchatters", "mostactive"], description="Most active members.")
    async def topusers(self, ctx):
        rows = await self.db.get_top_users(ctx.guild.id, self.config.LEADERBOARD_SIZE)
        if not rows:
            return await ctx.send(embed=self.info_embed("📊 Top Users", "No data yet! Start chatting."))

        medals = ["🥇", "🥈", "🥉"]
        desc = ""
        for i, row in enumerate(rows):
            member = ctx.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            desc += f"{medal} **{name}** — {row['total']:,} messages\n"

        await ctx.send(embed=self.info_embed(f"📊 Most Active in {ctx.guild.name}", desc))

    # ═══════════════════════════════════════════════════════════════════════════
    # ACTIVITY (last 7 days per channel)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="activity", description="Server message activity for the last 7 days.")
    async def activity(self, ctx):
        rows = await self.db.fetchall(
            """SELECT date, SUM(msg_count) as total
               FROM analytics WHERE guild_id=?
               AND date >= date('now', '-7 days')
               GROUP BY date ORDER BY date ASC""",
            (ctx.guild.id,)
        )

        if not rows:
            return await ctx.send(embed=self.info_embed("📊 Activity", "No data for the last 7 days."))

        lines = ""
        max_count = max(r["total"] for r in rows) or 1
        bar_max = 20

        for row in rows:
            date_str = row["date"][5:]   # MM-DD
            bar_len = int((row["total"] / max_count) * bar_max)
            bar = "█" * bar_len + "░" * (bar_max - bar_len)
            lines += f"`{date_str}` {bar} **{row['total']:,}**\n"

        await ctx.send(embed=self.info_embed("📊 Last 7 Days — Server Activity", lines))

    # ═══════════════════════════════════════════════════════════════════════════
    # CHANNELSTATS
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="channelstats", description="Top channels by message count.")
    async def channelstats(self, ctx):
        rows = await self.db.fetchall(
            """SELECT channel_id, SUM(msg_count) as total FROM analytics
               WHERE guild_id=? GROUP BY channel_id ORDER BY total DESC LIMIT 10""",
            (ctx.guild.id,)
        )
        if not rows:
            return await ctx.send(embed=self.info_embed("Channel Stats", "No data yet."))

        desc = ""
        for i, row in enumerate(rows, 1):
            ch = ctx.guild.get_channel(row["channel_id"])
            name = ch.mention if ch else f"<#{row['channel_id']}>"
            desc += f"`{i}.` {name} — **{row['total']:,}** messages\n"

        await ctx.send(embed=self.info_embed("📊 Top Channels", desc))


async def setup(bot):
    await bot.add_cog(Analytics(bot))
