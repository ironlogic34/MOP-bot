"""
cogs/games.py — Mini-games suite.
Commands: trivia, coinflip, roll, rps, guess, triviastats
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
import random
import asyncio
import aiohttp


# Built-in trivia questions (used as fallback)
BUILTIN_TRIVIA = [
    {"q": "What is the chemical symbol for Gold?", "a": "au", "display": "Au"},
    {"q": "How many bones are in the adult human body?", "a": "206", "display": "206"},
    {"q": "What planet is known as the Red Planet?", "a": "mars", "display": "Mars"},
    {"q": "What is the square root of 144?", "a": "12", "display": "12"},
    {"q": "Who wrote 'Romeo and Juliet'?", "a": "shakespeare", "display": "Shakespeare"},
    {"q": "What is the capital of Japan?", "a": "tokyo", "display": "Tokyo"},
    {"q": "How many sides does a hexagon have?", "a": "6", "display": "6"},
    {"q": "What is the largest ocean on Earth?", "a": "pacific", "display": "Pacific"},
    {"q": "What gas do plants absorb from the air?", "a": "carbon dioxide", "display": "Carbon Dioxide"},
    {"q": "In which year did World War II end?", "a": "1945", "display": "1945"},
    {"q": "What is the hardest natural substance on Earth?", "a": "diamond", "display": "Diamond"},
    {"q": "How many continents are there?", "a": "7", "display": "7"},
    {"q": "What is the fastest land animal?", "a": "cheetah", "display": "Cheetah"},
    {"q": "What element has atomic number 1?", "a": "hydrogen", "display": "Hydrogen"},
    {"q": "What is the largest planet in our Solar System?", "a": "jupiter", "display": "Jupiter"},
]


class Games(BaseCog):
    """🎮 Mini-games — have fun and win coins."""

    def __init__(self, bot):
        super().__init__(bot)
        self._active_guesses: dict = {}   # guild_id → {user_id: number}

    # ═══════════════════════════════════════════════════════════════════════════
    # TRIVIA
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="trivia", description="Answer a trivia question for coins!")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def trivia(self, ctx):
        # Try Open Trivia DB first, fall back to built-in
        question_data = await self._fetch_trivia()

        e = self.info_embed(
            "🧠 Trivia Time!",
            f"{question_data['q']}\n\n*Type your answer in chat within 20 seconds!*"
        )
        e.set_footer(text="Case-insensitive • Partial answers accepted")
        await ctx.send(embed=e)

        def check(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and len(m.content) > 0
            )

        try:
            msg = await self.bot.wait_for("message", timeout=20.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send(embed=self.error_embed(
                f"⏰ Time's up! The answer was **{question_data['display']}**."
            ))
            await self.db.update_trivia(ctx.author.id, ctx.guild.id, won=False)
            return

        answer = msg.content.lower().strip()
        correct = question_data["a"].lower()

        if answer == correct or correct in answer:
            reward = random.randint(20, 75)
            await self.db.update_balance(ctx.author.id, ctx.guild.id, reward)
            await self.db.update_trivia(ctx.author.id, ctx.guild.id, won=True)
            await ctx.send(embed=self.success_embed(
                f"✅ Correct! The answer was **{question_data['display']}**.\n"
                f"You earned 🪙 **{reward}** coins!"
            ))
        else:
            await self.db.update_trivia(ctx.author.id, ctx.guild.id, won=False)
            await ctx.send(embed=self.error_embed(
                f"❌ Wrong! The correct answer was **{question_data['display']}**."
            ))

    async def _fetch_trivia(self) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://opentdb.com/api.php?amount=1&type=boolean",
                    timeout=aiohttp.ClientTimeout(total=4)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data["results"][0]
                        q = result["question"].replace("&quot;", '"').replace("&#039;", "'").replace("&amp;", "&")
                        a = result["correct_answer"].lower()   # "true" or "false"
                        return {"q": q, "a": a, "display": result["correct_answer"]}
        except Exception:
            pass
        # Fallback
        item = random.choice(BUILTIN_TRIVIA)
        return item

    # ═══════════════════════════════════════════════════════════════════════════
    # TRIVIASTATS
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="triviastats", description="View trivia leaderboard.")
    async def triviastats(self, ctx):
        rows = await self.db.get_trivia_leaderboard(ctx.guild.id)
        if not rows:
            return await ctx.send(embed=self.info_embed("Trivia Leaderboard", "No games played yet!"))

        desc = ""
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            m = ctx.guild.get_member(row["user_id"])
            name = m.display_name if m else f"User {row['user_id']}"
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            total = row["wins"] + row["losses"]
            pct = round(row["wins"] / total * 100) if total > 0 else 0
            desc += f"{medal} **{name}** — {row['wins']}W / {row['losses']}L ({pct}%)\n"

        await ctx.send(embed=self.info_embed("🧠 Trivia Leaderboard", desc))

    # ═══════════════════════════════════════════════════════════════════════════
    # COINFLIP
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="coinflip", aliases=["cf", "flip"], description="Bet coins on a coinflip.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(bet="Amount to bet", side="heads or tails")
    async def coinflip(self, ctx, bet: int, side: str = "heads"):
        side = side.lower()
        if side not in ("heads", "tails", "h", "t"):
            return await ctx.send(embed=self.error_embed("Choose `heads` or `tails`."))
        if bet <= 0:
            return await ctx.send(embed=self.error_embed("Bet must be positive."))

        data = await self.db.get_balance(ctx.author.id, ctx.guild.id)
        if data["balance"] < bet:
            return await ctx.send(embed=self.error_embed(
                f"You only have 🪙 {data['balance']:,} coins."
            ))

        # Normalise
        side = "heads" if side in ("heads", "h") else "tails"
        result = random.choice(["heads", "tails"])
        coin_emoji = "🪙" if result == "heads" else "🟤"

        if side == result:
            await self.db.update_balance(ctx.author.id, ctx.guild.id, bet)
            await ctx.send(embed=self.success_embed(
                f"{coin_emoji} It's **{result}**! You guessed right and won 🪙 **{bet:,}** coins!"
            ))
        else:
            await self.db.update_balance(ctx.author.id, ctx.guild.id, -bet)
            await ctx.send(embed=self.error_embed(
                f"{coin_emoji} It's **{result}**! You guessed {side} and lost 🪙 **{bet:,}** coins."
            ))

    # ═══════════════════════════════════════════════════════════════════════════
    # ROLL
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="roll", description="Roll dice. Format: NdX (e.g. 2d6, 1d20)")
    @app_commands.describe(dice="Dice notation, e.g. 2d6 or 1d20")
    async def roll(self, ctx, dice: str = "1d6"):
        try:
            parts = dice.lower().split("d")
            count = int(parts[0]) if parts[0] else 1
            sides = int(parts[1])
            assert 1 <= count <= 20 and 2 <= sides <= 1000
        except Exception:
            return await ctx.send(embed=self.error_embed("Format: `NdX` e.g. `2d6`, `1d20`. Max 20 dice, d1000."))

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        roll_str = " + ".join(str(r) for r in rolls) if count > 1 else str(rolls[0])

        await ctx.send(embed=self.info_embed(
            f"🎲 Roll {dice}",
            f"{roll_str} = **{total}**"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # ROCK PAPER SCISSORS
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="rps", description="Play Rock Paper Scissors against the bot.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(choice="rock, paper, or scissors")
    async def rps(self, ctx, choice: str):
        choices = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        short = {"r": "rock", "p": "paper", "s": "scissors"}
        choice = short.get(choice.lower(), choice.lower())

        if choice not in choices:
            return await ctx.send(embed=self.error_embed("Choose `rock`, `paper`, or `scissors`."))

        bot_choice = random.choice(list(choices.keys()))

        wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

        if choice == bot_choice:
            result = "It's a **tie**! 🤝"
            color = 0xFEE75C
        elif wins[choice] == bot_choice:
            result = "You **win**! 🎉"
            color = 0x57F287
            await self.db.update_balance(ctx.author.id, ctx.guild.id, 10)
            result += " (+🪙 10)"
        else:
            result = "You **lose**! 😔"
            color = 0xED4245

        e = self.embed(
            title="Rock Paper Scissors",
            description=f"You: {choices[choice]} vs Bot: {choices[bot_choice]}\n\n{result}",
            color=color
        )
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # NUMBER GUESS
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="guess", description="Start a number guessing game (1–100). Costs 10 coins to play.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def guess(self, ctx):
        data = await self.db.get_balance(ctx.author.id, ctx.guild.id)
        if data["balance"] < 10:
            return await ctx.send(embed=self.error_embed("You need at least 🪙 10 coins to play."))

        await self.db.update_balance(ctx.author.id, ctx.guild.id, -10)
        number = random.randint(1, 100)
        attempts = 0
        max_attempts = 7

        await ctx.send(embed=self.info_embed(
            "🎯 Number Guess",
            f"I'm thinking of a number between **1 and 100**.\nYou have **{max_attempts} attempts**. Go!"
        ))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        while attempts < max_attempts:
            try:
                msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send(embed=self.error_embed(f"⏰ Time's up! The number was **{number}**."))
                return

            guess = int(msg.content)
            attempts += 1
            remaining = max_attempts - attempts

            if guess == number:
                # Reward based on speed
                reward = max(10, 100 - attempts * 10)
                await self.db.update_balance(ctx.author.id, ctx.guild.id, reward)
                await ctx.send(embed=self.success_embed(
                    f"🎯 Correct in {attempts} attempt(s)! The number was **{number}**.\n"
                    f"You won 🪙 **{reward}** coins!"
                ))
                return
            elif remaining == 0:
                await ctx.send(embed=self.error_embed(f"No more attempts! The number was **{number}**."))
                return
            elif guess < number:
                await ctx.send(embed=self.info_embed(
                    "📈 Too Low!",
                    f"Go higher! **{remaining}** attempt(s) left."
                ), delete_after=10)
            else:
                await ctx.send(embed=self.info_embed(
                    "📉 Too High!",
                    f"Go lower! **{remaining}** attempt(s) left."
                ), delete_after=10)


async def setup(bot):
    await bot.add_cog(Games(bot))
