"""
cogs/economy.py — Full economy system.
Commands: balance, daily, weekly, give, leaderboard, shop, buy, inventory, additem, removeitem
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.core.base_cog import BaseCog
from datetime import datetime, timedelta
import json


class Economy(BaseCog):
    """💰 Server economy — earn, spend, compete."""

    def _fmt(self, amount: int) -> str:
        return f"{self.config.CURRENCY_SYMBOL} **{amount:,}** {self.config.CURRENCY_NAME}"

    # ═══════════════════════════════════════════════════════════════════════════
    # BALANCE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="balance", aliases=["bal", "wallet"], description="Check your or someone else's balance.")
    @app_commands.describe(member="Member to check (leave blank for yourself)")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = await self.db.get_balance(member.id, ctx.guild.id)
        e = self.info_embed(
            f"💰 {member.display_name}'s Wallet",
            f"Balance: {self._fmt(data['balance'])}\nTotal earned: {self._fmt(data['total_earned'])}"
        )
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # DAILY
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="daily", description="Claim your daily reward.")
    async def daily(self, ctx):
        data = await self.db.get_balance(ctx.author.id, ctx.guild.id)
        now = datetime.utcnow()

        if data["last_daily"]:
            last = datetime.fromisoformat(data["last_daily"])
            diff = now - last
            if diff < timedelta(hours=22):
                remaining = timedelta(hours=22) - diff
                h, m = divmod(int(remaining.total_seconds()), 3600)
                m //= 60
                return await ctx.send(embed=self.error_embed(
                    f"Daily already claimed! Come back in **{h}h {m}m**."
                ))

        reward = self.config.DAILY_REWARD
        await self.db.update_balance(ctx.author.id, ctx.guild.id, reward)
        await self.db.execute(
            "UPDATE economy SET last_daily=? WHERE user_id=? AND guild_id=?",
            (now.isoformat(), ctx.author.id, ctx.guild.id)
        )
        await ctx.send(embed=self.success_embed(
            f"{ctx.author.mention} claimed their daily reward: {self._fmt(reward)}!"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # WEEKLY
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="weekly", description="Claim your weekly reward.")
    async def weekly(self, ctx):
        data = await self.db.get_balance(ctx.author.id, ctx.guild.id)
        now = datetime.utcnow()

        if data["last_weekly"]:
            last = datetime.fromisoformat(data["last_weekly"])
            diff = now - last
            if diff < timedelta(days=6, hours=22):
                remaining = timedelta(days=7) - diff
                d = remaining.days
                h = remaining.seconds // 3600
                return await ctx.send(embed=self.error_embed(
                    f"Weekly already claimed! Come back in **{d}d {h}h**."
                ))

        reward = self.config.WEEKLY_REWARD
        await self.db.update_balance(ctx.author.id, ctx.guild.id, reward)
        await self.db.execute(
            "UPDATE economy SET last_weekly=? WHERE user_id=? AND guild_id=?",
            (now.isoformat(), ctx.author.id, ctx.guild.id)
        )
        await ctx.send(embed=self.success_embed(
            f"{ctx.author.mention} claimed their weekly reward: {self._fmt(reward)}!"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # GIVE
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="give", aliases=["pay", "transfer"], description="Give coins to another member.")
    @app_commands.describe(member="Who to give to", amount="How many coins")
    async def give(self, ctx, member: discord.Member, amount: int):
        if member == ctx.author:
            return await ctx.send(embed=self.error_embed("Can't give coins to yourself."))
        if member.bot:
            return await ctx.send(embed=self.error_embed("Can't give coins to a bot."))
        if amount <= 0:
            return await ctx.send(embed=self.error_embed("Amount must be positive."))

        data = await self.db.get_balance(ctx.author.id, ctx.guild.id)
        if data["balance"] < amount:
            return await ctx.send(embed=self.error_embed(
                f"You only have {self._fmt(data['balance'])}."
            ))

        await self.db.update_balance(ctx.author.id, ctx.guild.id, -amount)
        await self.db.update_balance(member.id, ctx.guild.id, amount)
        await ctx.send(embed=self.success_embed(
            f"{ctx.author.mention} gave {self._fmt(amount)} to {member.mention}!"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # LEADERBOARD
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="leaderboard", aliases=["lb", "richest"], description="See the richest members.")
    async def leaderboard(self, ctx):
        rows = await self.db.get_leaderboard(ctx.guild.id, self.config.LEADERBOARD_SIZE)
        if not rows:
            return await ctx.send(embed=self.info_embed("Leaderboard", "No data yet. Use `!daily` to start!"))

        medals = ["🥇", "🥈", "🥉"]
        desc = ""
        for i, row in enumerate(rows):
            member = ctx.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            desc += f"{medal} **{name}** — {self._fmt(row['balance'])}\n"

        await ctx.send(embed=self.info_embed(f"💰 Richest in {ctx.guild.name}", desc))

    # ═══════════════════════════════════════════════════════════════════════════
    # SHOP
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="shop", description="View the server shop.")
    async def shop(self, ctx):
        rows = await self.db.fetchall(
            "SELECT * FROM shop WHERE guild_id=? ORDER BY price ASC",
            (ctx.guild.id,)
        )
        if not rows:
            return await ctx.send(embed=self.info_embed("🏪 Shop", "The shop is empty. Admins can use `/additem` to add items."))

        e = self.info_embed("🏪 Server Shop", "")
        for item in rows:
            stock = "∞" if item["stock"] == -1 else item["stock"]
            role = ctx.guild.get_role(item["role_id"]) if item["role_id"] else None
            role_str = f" → gives {role.mention}" if role else ""
            e.add_field(
                name=f"#{item['id']} {item['name']} — {self._fmt(item['price'])}",
                value=f"{item['description'] or 'No description'}{role_str}\nStock: {stock}",
                inline=False
            )
        await ctx.send(embed=e)

    # ═══════════════════════════════════════════════════════════════════════════
    # BUY
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="buy", description="Buy an item from the shop.")
    @app_commands.describe(item_id="Item ID from the shop")
    async def buy(self, ctx, item_id: int):
        item = await self.db.fetchone(
            "SELECT * FROM shop WHERE id=? AND guild_id=?", (item_id, ctx.guild.id)
        )
        if not item:
            return await ctx.send(embed=self.error_embed("Item not found."))
        if item["stock"] == 0:
            return await ctx.send(embed=self.error_embed("This item is out of stock."))

        data = await self.db.get_balance(ctx.author.id, ctx.guild.id)
        if data["balance"] < item["price"]:
            return await ctx.send(embed=self.error_embed(
                f"You need {self._fmt(item['price'])} but only have {self._fmt(data['balance'])}."
            ))

        await self.db.update_balance(ctx.author.id, ctx.guild.id, -item["price"])

        # Deduct stock
        if item["stock"] > 0:
            await self.db.execute(
                "UPDATE shop SET stock = stock - 1 WHERE id=?", (item_id,)
            )

        # Add to inventory
        await self.db.execute(
            """INSERT INTO inventory (user_id, guild_id, item_id, quantity) VALUES (?,?,?,1)
               ON CONFLICT(user_id,guild_id,item_id) DO UPDATE SET quantity = quantity + 1""",
            (ctx.author.id, ctx.guild.id, item_id)
        )

        # Grant role if any
        if item["role_id"]:
            role = ctx.guild.get_role(item["role_id"])
            if role:
                try:
                    await ctx.author.add_roles(role, reason="Shop purchase")
                except discord.Forbidden:
                    pass

        await ctx.send(embed=self.success_embed(
            f"You bought **{item['name']}** for {self._fmt(item['price'])}!"
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # INVENTORY
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="inventory", aliases=["inv"], description="View your inventory.")
    async def inventory(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        rows = await self.db.fetchall(
            """SELECT i.quantity, s.name, s.description FROM inventory i
               JOIN shop s ON i.item_id = s.id
               WHERE i.user_id=? AND i.guild_id=?""",
            (member.id, ctx.guild.id)
        )
        if not rows:
            return await ctx.send(embed=self.info_embed(
                f"🎒 {member.display_name}'s Inventory", "Empty! Visit the `/shop`."
            ))

        desc = "\n".join(f"**{r['name']}** x{r['quantity']} — {r['description'] or ''}" for r in rows)
        await ctx.send(embed=self.info_embed(f"🎒 {member.display_name}'s Inventory", desc))

    # ═══════════════════════════════════════════════════════════════════════════
    # ADDITEM (Admin)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="additem", description="Add an item to the shop. (Admin)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        name="Item name", price="Price in coins",
        description="Description", role="Role to grant on purchase",
        stock="Stock count (-1 for unlimited)"
    )
    async def additem(self, ctx, name: str, price: int, description: str = "",
                      role: discord.Role = None, stock: int = -1):
        role_id = role.id if role else None
        await self.db.execute(
            "INSERT INTO shop (guild_id, name, description, price, role_id, stock) VALUES (?,?,?,?,?,?)",
            (ctx.guild.id, name, description, price, role_id, stock)
        )
        await ctx.send(embed=self.success_embed(
            f"Added **{name}** to the shop for {self._fmt(price)}."
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # REMOVEITEM (Admin)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="removeitem", description="Remove an item from the shop. (Admin)")
    @commands.has_permissions(administrator=True)
    async def removeitem(self, ctx, item_id: int):
        item = await self.db.fetchone(
            "SELECT * FROM shop WHERE id=? AND guild_id=?", (item_id, ctx.guild.id)
        )
        if not item:
            return await ctx.send(embed=self.error_embed("Item not found."))
        await self.db.execute("DELETE FROM shop WHERE id=?", (item_id,))
        await ctx.send(embed=self.success_embed(f"Removed **{item['name']}** from the shop."))

    # ═══════════════════════════════════════════════════════════════════════════
    # SETBALANCE (Admin)
    # ═══════════════════════════════════════════════════════════════════════════
    @commands.hybrid_command(name="setbalance", aliases=["setbal"], description="Set a member's balance. (Admin)")
    @commands.has_permissions(administrator=True)
    async def setbalance(self, ctx, member: discord.Member, amount: int):
        await self.db.set_balance(member.id, ctx.guild.id, amount)
        await ctx.send(embed=self.success_embed(
            f"Set {member.mention}'s balance to {self._fmt(amount)}."
        ))


async def setup(bot):
    await bot.add_cog(Economy(bot))
