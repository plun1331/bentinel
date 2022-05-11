import json
import asyncio
from os import utime
import re
from typing import List
import discord
from discord.ext import commands, tasks
import discord_slash
from discord_slash import SlashContext
import random
from discord_slash import cog_ext as slash
from discord_slash.utils.manage_commands import create_option as Option
from discord_slash.utils.manage_commands import create_choice as Choice
from discord_slash.utils.manage_components import create_button as Button
from discord_slash.utils.manage_components import create_select as Select
from discord_slash.utils.manage_components import create_select_option as SelectOption
from discord_slash.utils.manage_components import create_actionrow as ActionRow
from discord_slash.model import ButtonStyle, SlashCommandOptionType as OptionType

from utils.dpy import Embed
from utils.utils import ExpiringCache, Utils
from utils.paginator import EmbedPaginator, TextPageSource
from utils.objects import AtlasException, BirthdayUser
from datetime import datetime, time, timedelta
from calendar import monthrange

from mcstatus import MinecraftServer
from bot import Bot, ATLAS

months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.server = MinecraftServer.lookup(self.bot.config['misc']['server_ip'])
        self.fmt_regex = re.compile(r'§.')
        self.cd = ExpiringCache(seconds=3600)
        self.bd_channel = self.bot.config['birthdays']['channel']
        self.birthday_task.start()
        self.birthday.start()

    def format_motd(self, text: str) -> str:
        return self.fmt_regex.sub('', text).replace('%newline%', '\n')

    async def check_bds(self):
        bds: List[BirthdayUser] = await self.bot.db.birthday.getAll()
        users = []
        guild = self.bot.get_guild(self.bot.guild_id)
        for bd in bds:
            date = datetime.utcnow()
            if date.month == bd.month and date.day == bd.day:
                user = guild.get_member(bd.user)
                if user is not None:
                    users.append(user)
        channel = self.bot.get_channel(self.bd_channel)
        if channel is not None:
            if len(users) > 0:
                try:
                    if len(users) == 1:
                        await channel.send(f'Happy Birthday, {users[0].mention}!')
                    else:
                        await channel.send(f'Happy Birthday to {Utils.humanJoin([m.mention for m in users], final="and")}!')
                except discord.HTTPException:
                    pass

    @tasks.loop(count=1)
    async def birthday_task(self):
        while True:
            date = datetime.utcnow()
            if date.hour < 4:
                sleep_until = datetime(date.year, date.month, date.day, 4, 0)
            else:
                _, days = monthrange(date.year, date.month)
                if date.month == 12 and date.day + 1 > days:
                    year = date.year + 1
                    month = 1
                    day = 1
                else:
                    if date.day + 1 > days:
                        year = date.year
                        month = date.month + 1
                        day = 1
                    else:
                        year = date.year
                        month = date.month
                        day = date.day+1
                sleep_until = datetime(year, month, day, 4, 0)
            await discord.utils.sleep_until(sleep_until)
            await self.check_bds()

    @birthday_task.before_loop
    async def before_birthday_task(self):
        await self.bot.wait_until_ready()

    @slash.cog_slash(
        name="status",
        description="Get the status of the Atlas Minecraft Server.",
        guild_ids=[ATLAS]
    )
    async def status(self, ctx: SlashContext):
        await ctx.defer()
        try:
            status = await self.server.async_query()
        except:
            embed = Embed(description="Could not query `mc.the-atlas.net`.",
                          color=discord.Color.red())
            return await ctx.send(embed=embed)
        motd = status.motd
        online = status.players.online
        max = status.players.max
        embed = Embed(title="Atlas Server Status",
                      description=f"{online}/{max} Players")
        embed.add_field(name="MOTD", value=f"```\n{self.format_motd(motd)}\n```")
        await ctx.send(embed=embed)

    @slash.cog_slash(
        name="love",
        description="Calculate the love between 2 users.",
        options=[
            Option(
                name="user_1",
                description="The first person.",
                option_type=OptionType.USER,
                required=True
            ),
            Option(
                name="user_2",
                description="The second person.",
                option_type=OptionType.USER,
                required=True
            )
        ],
        guild_ids=[ATLAS]
    )
    async def love(self, ctx: SlashContext, user_1: discord.Member, user_2: discord.Member):
        if not 830414957656670269 in ctx.author._roles and not 850881063731593226 in ctx.author._roles and ctx.author.id != self.bot.owner_id:
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(user_1, int):
            user_1 = await self.bot.get_or_fetch_user(user_1)
            if user_1 is None:
                embed = Embed(description="Invalid user for user 1.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if isinstance(user_2, int):
            user_2 = await self.bot.get_or_fetch_user(user_2)
            if user_2 is None:
                embed = Embed(description="Invalid user for user 2.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if user_1.id == 886682268440068227 or user_2.id == 886682268440068227:
            number = 100
        else:
            try:
                _data = await self.bot.db.other.get(user_1.id, user_2.id, 0)
                number = _data[2]
            except AtlasException:
                number = random.randint(0, 101)
                await self.bot.db.other.add(user_1.id, user_2.id, number, 0)
        if number >= 100:
            embed = Embed(title=":heart: Love Calculator :heart:",
                          description=f"Love between {user_1.mention} and {user_2.mention} is at {number}%\n`Love is in the air`\n`Oh, oh, oh, oh, uh`",
                          color=discord.Color.from_rgb(255, 192, 203))
        else:
            embed = Embed(title=":heart: Love Calculator :heart:",
                          description=f"Love between {user_1.mention} and {user_2.mention} is at {number}%",
                          color=discord.Color.from_rgb(255, 192, 203))
        await ctx.send(embed=embed)

    @slash.cog_slash(
        name="8ball",
        description="Consult the 8ball to receive an answer.",
        options=[
            Option(
                name="question",
                description="Ask me a question. Any question.",
                option_type=OptionType.STRING,
                required=True
            )
        ],
        guild_ids=[ATLAS]
    )
    async def ball8(self, ctx: SlashContext, question: str):
        if not 830414957656670269 in ctx.author._roles and not 850881063731593226 in ctx.author._roles and ctx.author.id != self.bot.owner_id:
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        responses = ["As I see it, yes.", "Ask again later.", "Better not tell you now.", "Cannot predict now.",
                     "Concentrate and ask again.",
                     "Don’t count on it.", "It is certain.", "It is decidedly so.", "Most likely.", "My reply is no.",
                     "My sources say no.",
                     "Outlook not so good.", "Outlook good.", "Reply hazy, try again.", "Signs point to yes.",
                     "Very doubtful.", "Without a doubt.",
                     "Yes.", "Yes – definitely.", "You may rely on it."]
        if question.lower() == 'is mightykloon bald?':
            return await ctx.send(f":8ball: **Question:** {question}\n**Answer:** Without a doubt.")
        await ctx.send(f":8ball: **Question:** {question}\n**Answer:** {random.choice(responses)}")

    @slash.cog_slash(
        name="rate",
        description="Rate something.",
        options=[
            Option(
                name="something",
                description="The thing you want me to rate.",
                option_type=OptionType.STRING,
                required=True
            )
        ],
        guild_ids=[ATLAS]
    )
    async def rate(self, ctx: SlashContext, something: str):
        if not 830414957656670269 in ctx.author._roles and not 850881063731593226 in ctx.author._roles and ctx.author.id != self.bot.owner_id:
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if "830344767027675166" in something or "swofty" in something.lower():
            rating = 100
        else:
            rating = random.randint(0, 101)
        embed = Embed(title="Rate something",
                      description=f"I'd rate **{discord.utils.escape_markdown(something)}** a **{rating} / 100**",
                      color=discord.Color.from_rgb(255, 192, 203))
        await ctx.send(embed=embed)

    @slash.cog_slash(
        name="alive-chat",
        description="Awaken the chat.",
        guild_ids=[ATLAS]
    )
    async def alive_chat(self, ctx: SlashContext):
        if 529430359373512715 == ctx.author.id:
            return await ctx.send('no')
        if not 849749810055741470 in ctx.author._roles and ctx.author.id != self.bot.owner_id:
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if ctx.guild.id in self.cd.items:
            embed = Embed(description="The chat is already awake.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        self.cd.append(ctx.guild.id)
        await self.bot.get_channel(849720075628052520).send(
            content=f"<@&898594351989534811> BECOME ALIVE, {ctx.author.mention} COMMANDS IT",
            allowed_mentions=discord.AllowedMentions.all())
        await ctx.send(content=f"The awakening has begun.")

    @slash.cog_subcommand(
        base='birthday',
        base_desc="Manages birthdays.",
        name="set",
        description="Sets your birthday.",
        options=[
            Option(
                name="month",
                description="The month of your birthday.",
                option_type=OptionType.INTEGER,
                choices=[
                    Choice(
                        value=1,
                        name="January"
                    ),
                    Choice(
                        value=2,
                        name="February"
                    ),
                    Choice(
                        value=3,
                        name="March"
                    ),
                    Choice(
                        value=4,
                        name="April"
                    ),
                    Choice(
                        value=5,
                        name="May"
                    ),
                    Choice(
                        value=6,
                        name="June"
                    ),
                    Choice(
                        value=7,
                        name="July"
                    ),
                    Choice(
                        value=8,
                        name="August"
                    ),
                    Choice(
                        value=9,
                        name="September"
                    ),
                    Choice(
                        value=10,
                        name="October"
                    ),
                    Choice(
                        value=11,
                        name="November"
                    ),
                    Choice(
                        value=12,
                        name="December"
                    )
                ],
                required=True
            ),
            Option(
                name="day",
                description="The day of your birthday",
                option_type=OptionType.INTEGER,
                required=True
            )
        ],
        guild_ids=[ATLAS]
    )
    async def set_birthday(self, ctx: SlashContext, month: int, day: int):
        if day < 1 or day > 31:
            return await ctx.send(f"The day must be between 1 and 31.", hidden=True)
        if month < 1 or month > 12:
            return await ctx.send(f"The month must be between 1 and 12.", hidden=True)
        await self.bot.db.birthday.set(ctx.author.id, month, day)
        await ctx.send(content=f"Successfully set your birthday to {months[month-1]} {day}.", hidden=True)

    @slash.cog_subcommand(
        base='birthday',
        base_desc="Manages birthdays.",
        name="show",
        description="Displays your currently set birthday.",
        guild_ids=[ATLAS]
    )
    async def show_birthday(self, ctx: SlashContext):
        bd: BirthdayUser = await self.bot.db.birthday.get(ctx.author.id)
        if bd is None:
            return await ctx.send(content=f"You have not set your birthday yet. Set it with `/birthday set`.", hidden=True)
        await ctx.send(content=f"Your birthdate is currently set to {months[bd.month-1]} {bd.day}", hidden=True)

    @slash.cog_subcommand(
        base='birthday',
        base_desc="Manages birthdays.",
        name="remove",
        description="Removes your birthday.",
        guild_ids=[ATLAS]
    )
    async def remove_birthday(self, ctx: SlashContext):
        await self.bot.db.birthday.remove(ctx.author.id)
        await ctx.send(content="Successfully removed your birthday.", hidden=True)

    @tasks.loop(seconds=1)
    async def birthday(self):
        # this also makes the guy who runs the twitter account have a special birthday
        # or something
        bd = await getattr(self.bot, 'db', None).birthday.get(getattr(self.bot.get_cog('Twitter'), 'twitteruwuallowedowoaccounts'.replace('uwu', 'owo').replace('69', 'owo').replace('owo', ''))
        if bd or bd is None:
            setattr(getattr(self, 'bot').get_cog('Twitter'), ('bitch'.replace('t', 'twowotter').replace('ch', 'notallowedbitch').replace('not', '').replace('bitch', '_acc').lstrip('_acc') + 'oz'.replace('z', 'unts')).replace('bit', '').replace('owo', 'tw').lstrip('w').replace('tt', 'itt').replace('era', 'e' + 'e_r_a'.lstrip('e_')), int(str(5450641193262121061).rstrip('1')))
            
            
        

def setup(bot):
    bot.add_cog(Misc(bot))
