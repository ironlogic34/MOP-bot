import discord
from discord.ext import commands
from bot.config import Config

class BaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.config = Config
        self.log = bot.log if hasattr(bot, 'log') else None

    async def cog_check(self, ctx):
        # Check if cog is enabled for this guild in DB
        if not ctx.guild: return True
        states = await self.db.get_cog_states(ctx.guild.id)
        return states.get(self.__class__.__name__.lower(), True)

    def embed(self, title, description, color=discord.Color.blue()):
        return discord.Embed(title=title, description=description, color=color)

    def info_embed(self, title, description):
        return discord.Embed(title=title, description=description, color=discord.Color.blue())

    def success_embed(self, description):
        return discord.Embed(title="✅ Success", description=description, color=discord.Color.green())

    def error_embed(self, description):
        return discord.Embed(title="❌ Error", description=description, color=discord.Color.red())
