import json
import asyncio
import re
import discord
from discord.ext import commands
import discord_slash
from discord_slash import SlashContext
from discord_slash import cog_ext as slash
from discord_slash.context import ComponentContext
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
from utils.objects import AtlasException
from bot import Bot, ATLAS


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot

    def has_perms(self, member):
        return member.guild_permissions.administrator or member.id == self.bot.owner_id or 849744644766171136 in member._roles
            
    @slash.cog_slash(
        name="suggest",
        description="Suggest something to add, change, or remove!",
        options=[
            Option(
                name="suggestion",
                description="Your suggestion.",
                option_type=OptionType.STRING,
                required=True,
            )
        ],
        guild_ids=[ATLAS]
    )
    async def suggest(self, ctx: SlashContext, suggestion: str):
        await ctx.defer(hidden=True)
        channel = self.bot.get_channel(self.bot.suggestion_channel)
        if channel is None:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `NOTFOUND`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        try:
            message: discord.Message = await self.bot.db.suggest.create(ctx.author, suggestion)
        except discord.HTTPException:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `SENDFAIL`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        embed = Embed(description=f"[Your suggestion]({message.jump_url}) has been submitted.")
        await ctx.send(embed=embed, hidden=True)

    @slash.cog_subcommand(
        base='suggestion',
        base_desc="Manages suggestions.",
        name="accept",
        description="Accepts a suggestion.",
        options=[
            Option(
                name="suggestion",
                description="The ID of the suggestion.",
                option_type=OptionType.INTEGER,
                required=True,
            ),
            Option(
                name="reason",
                description="The reason this suggestion was accepted.",
                option_type=OptionType.STRING,
                required=True,
            )
        ],
        guild_ids=[ATLAS]
    )
    async def accept_suggestion(self, ctx: SlashContext, suggestion: int, reason: str):
        if not self.has_perms(ctx.author):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        try:
            await self.bot.db.suggest.accept(suggestion, ctx.author, reason)
        except discord.HTTPException:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `SENDFAIL`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        except AtlasException as e:
            embed = Embed(description=str(e), color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        embed = Embed(description=f"Suggestion #{suggestion} was accepted.")
        await ctx.send(embed=embed, hidden=True)

    @slash.cog_subcommand(
        base='suggestion',
        base_desc="Manages suggestions.",
        name="deny",
        description="Denies a suggestion.",
        options=[
            Option(
                name="suggestion",
                description="The ID of the suggestion.",
                option_type=OptionType.INTEGER,
                required=True,
            ),
            Option(
                name="reason",
                description="The reason this suggestion was denied.",
                option_type=OptionType.STRING,
                required=True,
            )
        ],
        guild_ids=[ATLAS]
    )
    async def deny_suggestion(self, ctx: SlashContext, suggestion: int, reason: str):
        if not self.has_perms(ctx.author):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        try:
            await self.bot.db.suggest.deny(suggestion, ctx.author, reason)
        except discord.HTTPException:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `SENDFAIL`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        except AtlasException as e:
            embed = Embed(description=str(e), color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        embed = Embed(description=f"Suggestion #{suggestion} was denied.")
        await ctx.send(embed=embed, hidden=True)
        
                        

def setup(bot):
    bot.add_cog(Suggestions(bot))
