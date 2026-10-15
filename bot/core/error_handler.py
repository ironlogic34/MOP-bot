"""
core/error_handler.py — Global slash + prefix command error handler.
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog


class ErrorHandler(BaseCog):
    """Catches all unhandled errors from slash and prefix commands."""

    # ── Prefix Command Errors ─────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=self.error_embed(
                f"Missing argument: `{error.param.name}`\n"
                f"Use `{self.config.PREFIX}help {ctx.command}` for usage."
            ))

        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=self.error_embed(f"Bad argument: {error}"))

        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(embed=self.error_embed(f"You need: `{perms}`"))

        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(embed=self.error_embed(f"I need: `{perms}`"))

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=self.error_embed(
                f"Cooldown! Try again in **{error.retry_after:.1f}s**"
            ), delete_after=5)

        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send(embed=self.error_embed("This command only works in servers."))

        elif isinstance(error, commands.CheckFailure):
            await ctx.send(embed=self.error_embed("You don't have permission to use this."))

        else:
            self.log.error(f"Unhandled error in {ctx.command}: {error}", exc_info=error)
            await ctx.send(embed=self.error_embed(f"Unexpected error: `{error}`"))

    # ── Slash Command Errors ───────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        error = getattr(error, "original", error)

        async def send(msg):
            try:
                await interaction.response.send_message(
                    embed=self.error_embed(msg), ephemeral=True
                )
            except discord.InteractionResponded:
                await interaction.followup.send(embed=self.error_embed(msg), ephemeral=True)

        if isinstance(error, app_commands.MissingPermissions):
            await send(f"You need: `{', '.join(error.missing_permissions)}`")
        elif isinstance(error, app_commands.BotMissingPermissions):
            await send(f"I need: `{', '.join(error.missing_permissions)}`")
        elif isinstance(error, app_commands.CommandOnCooldown):
            await send(f"Cooldown! Try again in **{error.retry_after:.1f}s**")
        elif isinstance(error, app_commands.CheckFailure):
            await send("You don't have permission for this.")
        else:
            self.log.error(f"Slash error: {error}", exc_info=error)
            await send(f"Unexpected error: `{error}`")


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
