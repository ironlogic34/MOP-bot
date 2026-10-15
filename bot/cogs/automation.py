"""
cogs/automation.py — Server automation.
Events: on_member_join, on_member_remove, on_guild_channel_create
Commands: setwelcome, setlogs, setautorole, announce, setleave
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
from datetime import datetime


class Automation(BaseCog):
    """⚙️ Automated server management — welcome, roles, announcements."""

    # ═══════════════════════════════════════════════════════════════════════════
    # MEMBER JOIN
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await self.db.get_guild_settings(guild.id)

        # Welcome message
        ch_id = settings.get("welcome_channel")
        if ch_id:
            ch = guild.get_channel(int(ch_id))
            if ch:
                e = discord.Embed(
                    title=f"👋 Welcome to {guild.name}!",
                    description=(
                        f"Hey {member.mention}, glad to have you here!\n"
                        f"You are member **#{guild.member_count}**.\n\n"
                        f"Read the rules and enjoy your stay! 🎉"
                    ),
                    color=0x57F287,
                    timestamp=datetime.utcnow()
                )
                e.set_thumbnail(url=member.display_avatar.url)
                e.set_footer(text=f"Account created: {member.created_at.strftime('%b %d, %Y')}")
                try:
                    await ch.send(embed=e)
                except discord.Forbidden:
                    pass

        # Auto-role
        role_id = settings.get("auto_role")
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except discord.Forbidden:
                    self.log.warning(f"Can't assign auto-role in {guild.name}")

        # DM welcome
        try:
            dm_embed = discord.Embed(
                title=f"Welcome to {guild.name}! 🎉",
                description=(
                    f"Hi {member.display_name}! You've just joined **{guild.name}**.\n"
                    f"We're happy to have you. Make sure to check the rules!"
                ),
                color=0x5865F2
            )
            dm_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass   # User has DMs disabled

        # Log to mod-log
        log_id = settings.get("log_channel")
        if log_id:
            log_ch = guild.get_channel(int(log_id))
            if log_ch:
                e = discord.Embed(
                    title="📥 Member Joined",
                    description=f"{member.mention} (`{member.id}`)",
                    color=0x57F287,
                    timestamp=datetime.utcnow()
                )
                e.set_thumbnail(url=member.display_avatar.url)
                e.add_field(name="Account Age", value=member.created_at.strftime("%b %d, %Y"))
                try:
                    await log_ch.send(embed=e)
                except discord.Forbidden:
                    pass

    # ═══════════════════════════════════════════════════════════════════════════
    # MEMBER LEAVE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        settings = await self.db.get_guild_settings(guild.id)

        leave_id = settings.get("leave_channel") or settings.get("welcome_channel")
        if leave_id:
            ch = guild.get_channel(int(leave_id))
            if ch:
                e = discord.Embed(
                    description=f"**{member}** has left the server. 👋",
                    color=0xED4245,
                    timestamp=datetime.utcnow()
                )
                e.set_thumbnail(url=member.display_avatar.url)
                try:
                    await ch.send(embed=e)
                except discord.Forbidden:
                    pass

        # Log to mod-log
        log_id = settings.get("log_channel")
        if log_id:
            log_ch = guild.get_channel(int(log_id))
            if log_ch:
                roles = [r.name for r in member.roles if r != guild.default_role]
                e = discord.Embed(
                    title="📤 Member Left",
                    description=f"{member} (`{member.id}`)",
                    color=0xED4245,
                    timestamp=datetime.utcnow()
                )
                e.add_field(name="Roles", value=", ".join(roles) or "None")
                try:
                    await log_ch.send(embed=e)
                except discord.Forbidden:
                    pass

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE DELETE LOG
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        settings = await self.db.get_guild_settings(message.guild.id)
        log_id = settings.get("log_channel")
        if not log_id:
            return
        ch = message.guild.get_channel(int(log_id))
        if not ch:
            return
        e = discord.Embed(
            title="🗑️ Message Deleted",
            color=0xFEE75C,
            timestamp=datetime.utcnow()
        )
        e.add_field(name="Author", value=f"{message.author} (`{message.author.id}`)", inline=True)
        e.add_field(name="Channel", value=message.channel.mention, inline=True)
        if message.content:
            e.add_field(name="Content", value=message.content[:1000], inline=False)
        try:
            await ch.send(embed=e)
        except discord.Forbidden:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE EDIT LOG
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        settings = await self.db.get_guild_settings(before.guild.id)
        log_id = settings.get("log_channel")
        if not log_id:
            return
        ch = before.guild.get_channel(int(log_id))
        if not ch:
            return
        e = discord.Embed(
            title="✏️ Message Edited",
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        e.add_field(name="Author", value=f"{before.author} (`{before.author.id}`)", inline=True)
        e.add_field(name="Channel", value=before.channel.mention, inline=True)
        e.add_field(name="Before", value=before.content[:500] or "*empty*", inline=False)
        e.add_field(name="After", value=after.content[:500] or "*empty*", inline=False)
        e.add_field(name="Jump", value=f"[Go to message]({after.jump_url})", inline=False)
        try:
            await ch.send(embed=e)
        except discord.Forbidden:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # SETUP COMMANDS (Admin)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="setwelcome", description="Set the welcome channel. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel to send welcome messages in")
    async def setwelcome(self, ctx, channel: discord.TextChannel):
        await self.db.set_guild_setting(ctx.guild.id, "welcome_channel", channel.id)
        await ctx.send(embed=self.success_embed(f"Welcome channel set to {channel.mention}."))

    @commands.hybrid_command(name="setleave", description="Set the leave message channel. (Admin)")
    @commands.has_permissions(administrator=True)
    async def setleave(self, ctx, channel: discord.TextChannel):
        await self.db.set_guild_setting(ctx.guild.id, "leave_channel", channel.id)
        await ctx.send(embed=self.success_embed(f"Leave channel set to {channel.mention}."))

    @commands.hybrid_command(name="setlogs", description="Set the mod-log channel. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel for mod/audit logs")
    async def setlogs(self, ctx, channel: discord.TextChannel):
        await self.db.set_guild_setting(ctx.guild.id, "log_channel", channel.id)
        await ctx.send(embed=self.success_embed(f"Log channel set to {channel.mention}."))

    @commands.hybrid_command(name="setautorole", description="Set a role to auto-assign on join. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to give new members")
    async def setautorole(self, ctx, role: discord.Role):
        await self.db.set_guild_setting(ctx.guild.id, "auto_role", role.id)
        await ctx.send(embed=self.success_embed(f"Auto-role set to {role.mention}."))

    @commands.hybrid_command(name="removeautorole", description="Remove the auto-role. (Admin)")
    @commands.has_permissions(administrator=True)
    async def removeautorole(self, ctx):
        await self.db.set_guild_setting(ctx.guild.id, "auto_role", None)
        await ctx.send(embed=self.success_embed("Auto-role removed."))

    # ═══════════════════════════════════════════════════════════════════════════
    # ANNOUNCE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="announce", description="Send an announcement embed to a channel. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Where to post", title="Announcement title", message="Announcement content")
    async def announce(self, ctx, channel: discord.TextChannel, title: str, *, message: str):
        e = discord.Embed(
            title=f"📢 {title}",
            description=message,
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        e.set_footer(text=f"Announced by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        try:
            await channel.send(embed=e)
            await ctx.send(embed=self.success_embed(f"Announcement posted in {channel.mention}."), ephemeral=True)
        except discord.Forbidden:
            await ctx.send(embed=self.error_embed(f"I don't have permission to post in {channel.mention}."))

    # ═══════════════════════════════════════════════════════════════════════════
    # SETTINGS VIEW
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="settings", description="View current server bot settings. (Admin)")
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        s = await self.db.get_guild_settings(ctx.guild.id)

        def ch_fmt(ch_id):
            if not ch_id:
                return "Not set"
            ch = ctx.guild.get_channel(int(ch_id))
            return ch.mention if ch else f"<#{ch_id}> (deleted)"

        def role_fmt(role_id):
            if not role_id:
                return "Not set"
            role = ctx.guild.get_role(int(role_id))
            return role.mention if role else f"<@&{role_id}> (deleted)"

        e = self.info_embed(f"⚙️ Settings — {ctx.guild.name}", "")
        e.add_field(name="Welcome Channel", value=ch_fmt(s.get("welcome_channel")), inline=True)
        e.add_field(name="Leave Channel", value=ch_fmt(s.get("leave_channel")), inline=True)
        e.add_field(name="Log Channel", value=ch_fmt(s.get("log_channel")), inline=True)
        e.add_field(name="Auto-Role", value=role_fmt(s.get("auto_role")), inline=True)
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Automation(bot))
