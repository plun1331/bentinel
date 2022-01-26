import json
import asyncio
import re
import random
import discord
from discord.ext import commands
import discord_slash
from discord_slash import SlashContext
from discord_slash import cog_ext as slash
from discord_slash.utils.manage_commands import create_option as Option
from discord_slash.utils.manage_commands import create_choice as Choice
from discord_slash.utils.manage_components import create_button as Button
from discord_slash.utils.manage_components import create_select as Select
from discord_slash.utils.manage_components import create_select_option as SelectOption
from discord_slash.utils.manage_components import create_actionrow as ActionRow
from discord_slash.model import ButtonStyle, SlashCommandOptionType as OptionType

from utils.dpy import Embed
from utils.utils import Utils, ExpiringCache
from utils.paginator import EmbedPaginator, TextPageSource
from bot import Bot, ATLAS

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.message_cache = ExpiringCache(seconds=60)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.guild is None:
            return

        if message.guild.id != self.bot.guild_id:
            return
        await self.bot.db.level.addMessage(message.author.id)
        if message.author.id in self.message_cache.items:
            return
        self.message_cache.append(message.author.id)
        xp = random.randint(15, 25)
        await self.bot.db.level.update(message.author.id, xp)
    
    @slash.cog_slash(
        name='rank',
        description="Checks a member's level.",
        options=[
            Option(
                name='member',
                option_type=OptionType.USER,
                required=False,
                description='The member you want to view.'
            )
        ],
        guild_ids=[ATLAS]
    )
    async def rank(self, ctx: SlashContext, member: discord.Member = None):
        if member is None:
            member = ctx.author
        if member.bot:
            embed = Embed(description="Bots cannot earn XP.", color=discord.Color.red())
            return await ctx.send(embed=embed)
        usr = await self.bot.db.level.get(member.id)
        all_users = await self.bot.db.level.getAll()
        all_users = sorted(all_users, key=lambda x: x.xp, reverse=True)
        if usr is None:
            xp, mess = (0, 0)
        else:
            xp, mess = (usr.xp, usr.messages)
        level, prog, needed = Utils.level(xp)
        bar = ''
        amnt = int(round(((prog/needed) * 100)/20, 0))
        bar += '█' * amnt
        bar += ' ' * (20 - amnt)
        rank = len(all_users) + 1
        for r, _ in enumerate(all_users):
            if all_users[r].user == member.id:
                rank = r + 1
                break
        embed = Embed(
            title=f"{member}'s Rank",
            description=f"Level: {level:,}\n"
                        f"Messages: {mess:,}\n"
                        f"Leaderboard Position: #{rank:,}\n"
                        f"[`{bar}`] ({xp:,}/{needed:,} XP)")
        await ctx.send(embed=embed)

    @slash.cog_slash(
        name='levels',
        description="View the level leaderboard.",
        guild_ids=[ATLAS]
    )
    async def levels(self, ctx: SlashContext):
        users = await self.bot.db.level.getAll()
        users = sorted(users, key=lambda x: x.xp, reverse=True)
        msg = ""
        rm = 0
        for pos, user in enumerate(users):
            pos += 1
            pos -= rm
            xp, _ = (user.xp, user.messages)
            level, prog, needed = Utils.level(xp)
            bar = ''
            amnt = int(round(((prog/needed) * 100)/20, 0))
            bar += '█' * amnt
            bar += ' ' * (20 - amnt)
            member = ctx.guild.get_member(user.user)
            if member is None:
                rm += 1
                continue
            msg += f"#{pos:,}: {member.mention} (Level {level:,}, {xp:,} XP)\n"
        if msg == "":
            msg = "No users found."
        pages = TextPageSource(msg, prefix='', suffix='', max_size=1000).pages
        embeds = []
        for page in pages:
            embeds.append(
                Embed(
                    title=f"Level Leaderboard",
                    description=page,
                )
            )
        paginator = EmbedPaginator(ctx, embeds)
        await paginator.run()
          

def setup(bot):
    bot.add_cog(Leveling(bot))
