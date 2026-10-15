"""
cogs/ai.py — Claude AI integration.
Commands: ask, clearchat
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
import aiohttp
import json


class AI(BaseCog):
    """🤖 AI assistant powered by Claude."""

    MAX_HISTORY = 10   # messages per user kept in context

    async def _get_history(self, user_id: int) -> list:
        row = await self.db.fetchone(
            "SELECT history_json FROM ai_context WHERE user_id=?", (user_id,)
        )
        if not row:
            return []
        try:
            return json.loads(row["history_json"])
        except Exception:
            return []

    async def _save_history(self, user_id: int, history: list):
        # Keep only last MAX_HISTORY messages
        history = history[-self.MAX_HISTORY:]
        await self.db.execute(
            """INSERT INTO ai_context (user_id, history_json, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET history_json=?, updated_at=datetime('now')""",
            (user_id, json.dumps(history), json.dumps(history))
        )

    async def _call_claude(self, user_id: int, user_message: str) -> str:
        if not self.config.ANTHROPIC_API_KEY:
            return "⚠️ No Anthropic API key configured. Add it to `config.py`."

        history = await self._get_history(user_id)
        history.append({"role": "user", "content": user_message})

        headers = {
            "x-api-key": self.config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.AI_MODEL,
            "max_tokens": self.config.AI_MAX_TOKENS,
            "system": self.config.AI_SYSTEM_PROMPT,
            "messages": history,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        self.log.error(f"Claude API error {resp.status}: {text}")
                        return f"⚠️ API error ({resp.status}). Check your key."
                    data = await resp.json()
                    reply = data["content"][0]["text"]

            history.append({"role": "assistant", "content": reply})
            await self._save_history(user_id, history)
            return reply

        except aiohttp.ClientConnectorError:
            return "⚠️ Couldn't connect to Claude API. Check your internet connection."
        except Exception as e:
            self.log.error(f"Claude call failed: {e}")
            return f"⚠️ Unexpected error: {e}"

    # ═══════════════════════════════════════════════════════════════════════════
    # ASK
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="ask", description="Ask the AI assistant anything.")
    @commands.cooldown(3, 30, commands.BucketType.user)
    @app_commands.describe(question="Your question or message")
    async def ask(self, ctx, *, question: str):
        async with ctx.typing():
            reply = await self._call_claude(ctx.author.id, question)

        # Discord messages max 2000 chars — split if needed
        if len(reply) <= 1900:
            e = self.info_embed("🤖 AI Response", reply)
            e.set_footer(text=f"Asked by {ctx.author.display_name} • /clearchat to reset context")
            await ctx.send(embed=e)
        else:
            # Split into chunks
            chunks = [reply[i:i+1900] for i in range(0, len(reply), 1900)]
            for i, chunk in enumerate(chunks):
                e = self.info_embed(
                    f"🤖 AI Response ({i+1}/{len(chunks)})", chunk
                )
                await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # CLEARCHAT
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="clearchat", description="Clear your AI conversation history.")
    async def clearchat(self, ctx):
        await self.db.execute(
            "DELETE FROM ai_context WHERE user_id=?", (ctx.author.id,)
        )
        await ctx.send(embed=self.success_embed("Your AI conversation history has been cleared."))


async def setup(bot):
    await bot.add_cog(AI(bot))
