"""
cogs/moderation.py — Full moderation suite.
Commands: warn, warns, clearwarns, kick, ban, unban, mute, unmute,
          purge, slowmode, case, history, lock, unlock
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
from datetime import datetime, timedelta


class Moderation(BaseCog):
    """🛡️ Moderation tools — keep your server clean."""

    # ── Internal helpers ──────────────────────────────────────────────────────
    async def _log(self, guild: discord.Guild, embed: discord.Embed):
        """Send embed to the mod-log channel if it exists."""
        ch = discord.utils.get(guild.text_channels, name=self.config.MOD_LOG_CHANNEL)
        if ch:
            try:
                await ch.send(embed=embed)
            except discord.Forbidden:
                pass

    async def _mod_embed(self, action, user, mod, reason, color=0xED4245):
        e = discord.Embed(
            title=f"🔨 {action}",
            color=color,
            timestamp=datetime.utcnow()
        )
        e.add_field(name="User", value=f"{user} (`{user.id}`)", inline=True)
        e.add_field(name="Moderator", value=f"{mod}", inline=True)
        e.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        return e

    # ═══════════════════════════════════════════════════════════════════════════
    # WARN
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="warn", description="Warn a member.")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.bot:
            return await ctx.send(embed=self.error_embed("Can't warn bots."))
        if member == ctx.author:
            return await ctx.send(embed=self.error_embed("Can't warn yourself."))

        await self.db.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        await self.db.add_case(ctx.guild.id, member.id, ctx.author.id, "WARN", reason)

        warns = await self.db.get_warnings(ctx.guild.id, member.id)
        warn_count = len(warns)

        embed = self.info_embed(
            "⚠️ Warning Issued",
            f"{member.mention} has been warned.\n**Reason:** {reason}\n**Total warnings:** {warn_count}"
        )
        await ctx.send(embed=embed)

        # DM the user
        try:
            await member.send(embed=self.info_embed(
                f"⚠️ You were warned in {ctx.guild.name}",
                f"**Reason:** {reason}\n**Total warnings:** {warn_count}"
            ))
        except discord.Forbidden:
            pass

        await self._log(ctx.guild, await self._mod_embed("WARN", member, ctx.author, reason, 0xFEE75C))

        # Auto-escalate
        if warn_count >= self.config.MAX_WARNS_BEFORE_BAN:
            try:
                await member.ban(reason=f"Auto-ban: {warn_count} warnings")
                await ctx.send(embed=self.error_embed(
                    f"{member.mention} was **auto-banned** after {warn_count} warnings."
                ))
            except discord.Forbidden:
                pass
        elif warn_count >= self.config.MAX_WARNS_BEFORE_KICK:
            try:
                await member.kick(reason=f"Auto-kick: {warn_count} warnings")
                await ctx.send(embed=self.error_embed(
                    f"{member.mention} was **auto-kicked** after {warn_count} warnings."
                ))
            except discord.Forbidden:
                pass

    # ═══════════════════════════════════════════════════════════════════════════
    # WARNS
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="warns", description="View warnings for a member.")
    @commands.has_permissions(manage_messages=True)
    async def warns(self, ctx, member: discord.Member):
        rows = await self.db.get_warnings(ctx.guild.id, member.id)
        if not rows:
            return await ctx.send(embed=self.success_embed(f"{member.mention} has no active warnings."))

        e = self.info_embed(f"⚠️ Warnings — {member}", "")
        for i, w in enumerate(rows, 1):
            mod = ctx.guild.get_member(w["mod_id"])
            e.add_field(
                name=f"#{i} — {w['timestamp'][:10]}",
                value=f"**Reason:** {w['reason']}\n**By:** {mod or w['mod_id']}",
                inline=False
            )
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # CLEARWARNS
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="clearwarns", description="Clear all warnings for a member.")
    @commands.has_permissions(administrator=True)
    async def clearwarns(self, ctx, member: discord.Member):
        await self.db.execute(
            "UPDATE warnings SET active=0 WHERE guild_id=? AND user_id=?",
            (ctx.guild.id, member.id)
        )
        await ctx.send(embed=self.success_embed(f"All warnings cleared for {member.mention}."))

    # ═══════════════════════════════════════════════════════════════════════════
    # KICK
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=self.error_embed("You can't kick someone with a higher/equal role."))

        try:
            await member.send(embed=self.info_embed(
                f"👢 You were kicked from {ctx.guild.name}", f"**Reason:** {reason}"
            ))
        except discord.Forbidden:
            pass

        await member.kick(reason=reason)
        await self.db.add_case(ctx.guild.id, member.id, ctx.author.id, "KICK", reason)
        await ctx.send(embed=self.success_embed(f"Kicked **{member}** — {reason}"))
        await self._log(ctx.guild, await self._mod_embed("KICK", member, ctx.author, reason))

    # ═══════════════════════════════════════════════════════════════════════════
    # BAN
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="ban", description="Ban a member from the server.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member="Member to ban", delete_days="Days of messages to delete", reason="Reason")
    async def ban(self, ctx, member: discord.Member, delete_days: int = 1, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=self.error_embed("You can't ban someone with a higher/equal role."))

        try:
            await member.send(embed=self.info_embed(
                f"🔨 You were banned from {ctx.guild.name}", f"**Reason:** {reason}"
            ))
        except discord.Forbidden:
            pass

        await member.ban(reason=reason, delete_message_days=min(delete_days, 7))
        await self.db.add_case(ctx.guild.id, member.id, ctx.author.id, "BAN", reason)
        await ctx.send(embed=self.success_embed(f"Banned **{member}** — {reason}"))
        await self._log(ctx.guild, await self._mod_embed("BAN", member, ctx.author, reason))

    # ═══════════════════════════════════════════════════════════════════════════
    # UNBAN
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="unban", description="Unban a user by ID or user#tag.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int, *, reason: str = "No reason provided"):
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
            await self.db.add_case(ctx.guild.id, user.id, ctx.author.id, "UNBAN", reason)
            await ctx.send(embed=self.success_embed(f"Unbanned **{user}**."))
            await self._log(ctx.guild, await self._mod_embed("UNBAN", user, ctx.author, reason, 0x57F287))
        except discord.NotFound:
            await ctx.send(embed=self.error_embed("User not found or not banned."))

    # ═══════════════════════════════════════════════════════════════════════════
    # MUTE (uses Discord timeout / "communication disabled")
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="mute", description="Timeout a member for N minutes.")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to mute", minutes="Duration in minutes", reason="Reason")
    async def mute(self, ctx, member: discord.Member, minutes: int = 10, *, reason: str = "No reason provided"):
        if minutes < 1 or minutes > 40320:   # Discord limit: 28 days
            return await ctx.send(embed=self.error_embed("Duration must be 1–40320 minutes."))

        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await self.db.add_case(ctx.guild.id, member.id, ctx.author.id, f"MUTE({minutes}m)", reason)
        await ctx.send(embed=self.success_embed(f"Muted **{member}** for **{minutes}m** — {reason}"))
        await self._log(ctx.guild, await self._mod_embed(f"MUTE ({minutes}m)", member, ctx.author, reason, 0xFEE75C))

    # ═══════════════════════════════════════════════════════════════════════════
    # UNMUTE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="unmute", description="Remove timeout from a member.")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        await member.timeout(None, reason=reason)
        await ctx.send(embed=self.success_embed(f"Unmuted **{member}**."))

    # ═══════════════════════════════════════════════════════════════════════════
    # PURGE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="purge", description="Bulk-delete messages.")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.describe(amount="Number of messages (1–100)", member="Only delete this member's messages")
    async def purge(self, ctx, amount: int, member: discord.Member = None):
        if not 1 <= amount <= 100:
            return await ctx.send(embed=self.error_embed("Amount must be 1–100."))

        def check(m):
            return member is None or m.author == member

        # hybrid commands: delete the invocation message first
        try:
            await ctx.message.delete()
        except (discord.Forbidden, AttributeError):
            pass

        deleted = await ctx.channel.purge(limit=amount, check=check)
        msg = await ctx.send(embed=self.success_embed(f"Deleted **{len(deleted)}** messages."))
        await msg.delete(delay=4)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLOWMODE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="slowmode", description="Set slowmode on this channel.")
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    async def slowmode(self, ctx, seconds: int = 0):
        if not 0 <= seconds <= 21600:
            return await ctx.send(embed=self.error_embed("0–21600 seconds only."))
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(embed=self.success_embed("Slowmode disabled."))
        else:
            await ctx.send(embed=self.success_embed(f"Slowmode set to **{seconds}s**."))

    # ═══════════════════════════════════════════════════════════════════════════
    # LOCK / UNLOCK
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="lock", description="Lock a channel (prevent @everyone from sending).")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.success_embed(f"🔒 {channel.mention} is now **locked**."))

    @commands.hybrid_command(name="unlock", description="Unlock a channel.")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.success_embed(f"🔓 {channel.mention} is now **unlocked**."))

    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORY / CASE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="history", description="View moderation history for a member.")
    @commands.has_permissions(manage_messages=True)
    async def history(self, ctx, member: discord.Member):
        cases = await self.db.get_cases(ctx.guild.id, member.id)
        if not cases:
            return await ctx.send(embed=self.info_embed("No History", f"{member.mention} has a clean record."))

        e = self.info_embed(f"📋 Mod History — {member}", f"Total cases: {len(cases)}")
        for case in cases[:10]:   # show latest 10
            mod = ctx.guild.get_member(case["mod_id"])
            e.add_field(
                name=f"[{case['action']}] — {case['timestamp'][:10]}",
                value=f"**Reason:** {case['reason']}\n**By:** {mod or case['mod_id']}",
                inline=False
            )
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
