import discord
from discord.ext import commands
import asyncio
import logging
import os
import json
import websockets
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from backend.database import DatabaseManager
from bot.config import Config

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger("ServerOS.Bot")

TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = "server_os.db"

class ServerOS(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=commands.when_mentioned_or(Config.PREFIX),
            intents=intents,
            help_command=None
        )
        self.db = DatabaseManager(DB_PATH)
        self.ws = None
        self.start_time = datetime.utcnow()
        self.log = log

    async def setup_hook(self):
        await self.db.initialise()
        
        # Load core cogs
        initial_extensions = [
            'bot.cogs.moderation',
            'bot.cogs.economy',
            'bot.cogs.analytics',
            'bot.cogs.automation',
            'bot.cogs.utilities',
            'bot.cogs.ai',
            'bot.cogs.games',
            'bot.cogs.media',
            'bot.core.error_handler'
        ]
        
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                log.info(f"Loaded extension: {ext}")
            except Exception as e:
                log.error(f"Failed to load extension {ext}: {e}")

        # Sync slash commands
        try:
            # If TEST_GUILD_ID is provided, sync to that guild for instant updates
            if Config.TEST_GUILD_ID:
                guild = discord.Object(id=Config.TEST_GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                log.info(f"Synced slash commands to guild {Config.TEST_GUILD_ID}")
            else:
                await self.tree.sync()
                log.info("Synced slash commands globally")
        except Exception as e:
            log.error(f"Failed to sync slash commands: {e}")

        # Start WebSocket Bridge
        self.loop.create_task(self.connect_to_backend())

    async def connect_to_backend(self):
        uri = "ws://localhost:8000/ws"
        while True:
            try:
                async with websockets.connect(uri) as websocket:
                    self.ws = websocket
                    log.info("Connected to Backend WebSocket")
                    
                    # Send initial status
                    await self.send_to_backend({
                        "type": "bot_status",
                        "status": "Online",
                        "user": str(self.user)
                    })

                    async for message in websocket:
                        data = json.loads(message)
                        await self.handle_backend_message(data)
            except Exception as e:
                log.error(f"Backend WS Connection Error: {e}")
                await asyncio.sleep(5)

    async def handle_backend_message(self, data):
        if data.get("type") == "cog_update":
            guild_id = data.get("guild_id")
            cog_name = data.get("cog_name")
            enabled = data.get("enabled")
            log.info(f"Cog Update: Guild {guild_id}, Cog {cog_name}, Enabled {enabled}")

        elif data.get("type") == "terminal_command":
            cmd = data.get("data")
            log.info(f"Terminal Command Received: {cmd}")
            await self.send_to_backend({
                "type": "terminal_output",
                "data": f"Executed: {cmd}"
            })

    async def send_to_backend(self, data):
        if self.ws:
            try:
                await self.ws.send(json.dumps(data))
            except Exception:
                pass

    async def on_ready(self):
        log.info(f"Bot logged in as {self.user}")
        for guild in self.guilds:
            await self.db.add_guild(guild.id, guild.name, guild.owner_id, guild.member_count)
        
        # Update backend with server count
        await self.send_to_backend({
            "type": "stats_update",
            "data": {"servers": len(self.guilds)}
        })

    async def on_message(self, message):
        if message.author.bot: return
        
        # Log to analytics
        if message.guild:
            await self.db.log_message(message.author.id, message.guild.id, message.channel.id)
            
            # Send live log to dashboard
            await self.send_to_backend({
                "type": "bot_log",
                "data": f"[{message.guild.name}] {message.author}: {message.content[:50]}"
            })
        
        await self.process_commands(message)

async def main():
    bot = ServerOS()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
