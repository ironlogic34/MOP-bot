"""
cogs/media.py — Media utilities.
Commands: youtube, define, meme, urban
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
import aiohttp
import urllib.parse


class Media(BaseCog):
    """📺 Media utilities — search, define, and more."""

    # ═══════════════════════════════════════════════════════════════════════════
    # YOUTUBE SEARCH
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="youtube", aliases=["yt"], description="Search YouTube for a video.")
    @app_commands.describe(query="What to search for")
    async def youtube(self, ctx, *, query: str):
        encoded = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"

        # We just build a clean link — no API key needed
        e = self.info_embed(
            "📺 YouTube Search",
            f"**Query:** {query}\n\n"
            f"🔗 [Click here to view results on YouTube]({search_url})\n\n"
            f"*Paste the link above in your browser to search.*"
        )
        e.set_thumbnail(url="https://www.youtube.com/yts/img/favicon_144-vfliLAfaB.png")
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # DEFINE (Free Dictionary API)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="define", aliases=["dict", "meaning"], description="Look up a word definition.")
    @app_commands.describe(word="Word to define")
    async def define(self, ctx, *, word: str):
        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 404:
                            return await ctx.send(embed=self.error_embed(f"No definition found for **{word}**."))
                        if resp.status != 200:
                            return await ctx.send(embed=self.error_embed("Dictionary API error. Try again later."))
                        data = await resp.json()

                entry = data[0]
                word_title = entry.get("word", word)
                phonetic = entry.get("phonetic", "")

                e = self.info_embed(f"📖 {word_title}", f"*{phonetic}*" if phonetic else "")

                for meaning in entry.get("meanings", [])[:3]:
                    part = meaning.get("partOfSpeech", "")
                    definitions = meaning.get("definitions", [])
                    if definitions:
                        defn = definitions[0].get("definition", "")
                        example = definitions[0].get("example", "")
                        value = defn
                        if example:
                            value += f'\n*"{example}"*'
                        e.add_field(name=f"_{part}_", value=value, inline=False)

                synonyms = entry["meanings"][0].get("synonyms", [])[:5] if entry.get("meanings") else []
                if synonyms:
                    e.add_field(name="Synonyms", value=", ".join(synonyms), inline=False)

                await ctx.send(embed=e)

            except aiohttp.ClientConnectorError:
                await ctx.send(embed=self.error_embed("No internet connection."))
            except Exception as ex:
                self.log.error(f"Define error: {ex}")
                await ctx.send(embed=self.error_embed("Failed to fetch definition."))

    # ═══════════════════════════════════════════════════════════════════════════
    # URBAN DICTIONARY
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="urban", description="Look up a word on Urban Dictionary.")
    @app_commands.describe(word="Slang term to look up")
    async def urban(self, ctx, *, word: str):
        # Only allow in NSFW channels or DMs for safety
        if hasattr(ctx.channel, "nsfw") and not ctx.channel.nsfw:
            return await ctx.send(embed=self.error_embed(
                "Urban Dictionary can only be used in NSFW-marked channels."
            ))

        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://api.urbandictionary.com/v0/define?term={urllib.parse.quote(word)}",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status != 200:
                            return await ctx.send(embed=self.error_embed("Urban Dictionary API error."))
                        data = await resp.json()

                results = data.get("list", [])
                if not results:
                    return await ctx.send(embed=self.error_embed(f"No urban definition for **{word}**."))

                top = results[0]
                definition = top.get("definition", "")[:1000].replace("[", "").replace("]", "")
                example = top.get("example", "")[:500].replace("[", "").replace("]", "")
                thumbs_up = top.get("thumbs_up", 0)
                thumbs_down = top.get("thumbs_down", 0)

                e = self.info_embed(f"🏙️ Urban: {top.get('word', word)}", definition)
                if example:
                    e.add_field(name="Example", value=f"*{example}*", inline=False)
                e.set_footer(text=f"👍 {thumbs_up} | 👎 {thumbs_down} — by {top.get('author', '?')}")
                await ctx.send(embed=e)

            except aiohttp.ClientConnectorError:
                await ctx.send(embed=self.error_embed("No internet connection."))
            except Exception as ex:
                self.log.error(f"Urban error: {ex}")
                await ctx.send(embed=self.error_embed("Failed to fetch definition."))

    # ═══════════════════════════════════════════════════════════════════════════
    # MEME (Reddit)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="meme", description="Get a random meme from Reddit.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def meme(self, ctx):
        if hasattr(ctx.channel, "nsfw") and not ctx.channel.nsfw:
            subreddit = "memes"
        else:
            subreddit = "memes"   # keep safe regardless

        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {"User-Agent": "DiscordBot/1.0"}
                    async with session.get(
                        f"https://www.reddit.com/r/{subreddit}/random.json?limit=1",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status != 200:
                            return await ctx.send(embed=self.error_embed("Couldn't fetch a meme right now."))
                        data = await resp.json()

                post = data[0]["data"]["children"][0]["data"]
                title = post.get("title", "Meme")
                url = post.get("url", "")
                upvotes = post.get("ups", 0)
                author = post.get("author", "unknown")

                if not url.endswith((".jpg", ".jpeg", ".png", ".gif")):
                    return await ctx.send(embed=self.error_embed("Got a non-image post. Try again!"))

                e = discord.Embed(title=title, color=0xFF4500)
                e.set_image(url=url)
                e.set_footer(text=f"👍 {upvotes:,} | u/{author} | r/{subreddit}")
                await ctx.send(embed=e)

            except aiohttp.ClientConnectorError:
                await ctx.send(embed=self.error_embed("No internet connection."))
            except Exception as ex:
                self.log.error(f"Meme error: {ex}")
                await ctx.send(embed=self.error_embed("Failed to fetch meme. Try again!"))


async def setup(bot):
    await bot.add_cog(Media(bot))
