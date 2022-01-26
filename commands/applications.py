import json
import asyncio
import re
from typing import Dict, List, Union
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
from utils.utils import Utils
from utils.paginator import EmbedPaginator, TextPageSource
from bot import Bot, ATLAS

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        with open('data/questions.json', 'r') as f:
            self.questions: List[Dict[str, Union[str, list, None]]] = json.load(f)
        with open('data/ht-questions.json', 'r') as f:
            self.ht_questions: List[Dict[str, Union[str, list, None]]] = json.load(f)
        self.in_application = []

    @slash.cog_slash(
        name="Apply",
        description="Apply for a position on our staff team!",
        options=[
            Option(
                name="position",
                option_type=OptionType.INTEGER,
                description="The position you are applying for.",
                choices=[
                    Choice(
                        value=1,
                        name="Developer"
                    ),
                    Choice(
                        value=2,
                        name="Helper"
                    ),
                    Choice(
                        value=3,
                        name="Hospitality Team"
                    ),
                ],
                required=True
            ),
        ],
        guild_ids=[ATLAS]
    )
    async def apply(self, ctx: SlashContext, *, position: int):
        if position == 1:
            return await ctx.reply("Please DM an owner to apply for Developer.", hidden=True)
        elif position == 2:
            questions = self.questions
            rank = "Helper"
        elif position == 3:
            questions = self.ht_questions
            rank = "Hospitality Team"
        if ctx.author.id in self.in_application:
            return await ctx.send("You are already completing an application.", hidden=True)
        if 851220029978574850 in ctx.author._roles:
            return await ctx.send("You are blacklisted from applications.", hidden=True)
        self.in_application.append(ctx.author.id)
        await ctx.defer(hidden=True)
        m = ctx.author
        try:
            msg = await m.send("Welcome to the Atlas Application Process!\n"
                               "You will be asked a series of questions, please answer them to the best of your ability.\n"
                               "There will be a chance to review your responses at the end of the application.\n\n"
                               "If you fail to respond to a question within 10 minutes, the bot will time out and you will have to redo your application.")
            channel = msg.channel
        except discord.HTTPException:
            self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None
            return await ctx.send("Sorry, I can't DM you. Please check your privacy settings.", hidden=True)
        await ctx.send("Check your DMs!", hidden=True)
        await asyncio.sleep(10)
        answers = {}
        sub = 0
        for qn, question in enumerate(questions):
            qn += 1
            qn -= sub
            try:
                while True:
                    if question['input'] == 'text':
                        await m.send(f"**#{qn}:** " + question['question'])
                        msg = await self.bot.wait_for('message', check=lambda msg: msg.author == m and msg.channel == channel, timeout=600)
                        if question['validation']:
                            if not re.match(question['validation'], msg.content):
                                await msg.reply("Sorry, that doesn't seem like a valid answer.")
                                await asyncio.sleep(3)
                                continue
                        answers[question['question']] = msg.content
                        break
                    elif question['input'] == 'select':
                        options = [SelectOption(label=item, value=item) for item in question['validation']]
                        select = Select(custom_id=f"application.{m.id}.{qn}", 
                                        placeholder="Select an option.", 
                                        min_values=1, 
                                        max_values=1, 
                                        options=options)
                        await m.send(f"**#{qn}:** " + question['question'], components=[ActionRow(select)])
                        msg = await self.bot.wait_for('component', check=lambda msg: msg.custom_id == f"application.{m.id}.{qn}", timeout=600)
                        answers[question['question']] = msg.selected_options[0]
                        await msg.defer(ignore=True)
                        break
                    elif question['input'] is None:
                        sub += 1
                        await m.send(question['question'])
                        await asyncio.sleep(3)
                        break
            except asyncio.TimeoutError:
                self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None
                return await m.send("Sorry, you took too long to answer the question. The application process has been cancelled.")
        embed = Embed(title="Your Answers",
                      description="Please review your answers below and submit when you're ready.",
                      color=discord.Color.gold())
        for qn, question in enumerate(answers.items()):
            qn += 1
            embed.add_field(name=f"**#{qn}:** {question[0]}", value=question[1])
        await m.send(embed=embed, components=[ActionRow(Button(label="Submit", custom_id=f"submitapp.{m.id}", style=ButtonStyle.green), 
                                                               Button(label="Cancel", custom_id=f"cancelapp.{m.id}", style=ButtonStyle.red))])
        try:
            msg = await self.bot.wait_for('component', check=lambda msg: msg.custom_id in (f'submitapp.{m.id}', f'cancelapp.{m.id}'), timeout=600)
        except asyncio.TimeoutError:
            self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None
            return await m.send("Sorry, you took too long to review your answers. The application process has been cancelled.")
        if 'cancel' in msg.custom_id:
            self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None
            return await msg.send("The application process has been cancelled.")
        app_channel = self.bot.get_channel(self.bot.application_channel)
        if not app_channel:
            self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None
            return await msg.send("An error has occurred.\nPlease contact an administrator for more details.\nError Code: `NOTFOUND`")
        embed = Embed(description=f"{rank} Application submitted by {m} ({m.id})", color=discord.Color.gold())
        for qn, question in enumerate(answers.items()):
            qn += 1
            embed.add_field(name=f"**#{qn}:** {question[0]}", value=question[1])
        try:
            await app_channel.send(embed=embed)
        except (discord.HTTPException):
            self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None
            return await msg.send("An error has occurred.\nPlease contact an administrator for more details.\nError Code: `SENDFAIL`")
        await msg.send("Your application has been submitted.\n"
                       "An administrator will contact you soon if you have been accepted.\n"
                       "**Please do not ask staff members about your application.**")
        self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None

    @apply.error
    async def apply_error(self, ctx: SlashContext, error):
        self.in_application.remove(ctx.author.id) if ctx.author.id in self.in_application else None

def setup(bot):
    bot.add_cog(Applications(bot))
