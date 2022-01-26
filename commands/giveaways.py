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

class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot

    @slash.cog_slash(
        name="giveaway",
        description="Start a giveaway!",
        options=[
            Option(
                name="prize",
                option_type=OptionType.STRING,
                description="The item you are giving away.",
                required=True
            ),
            Option(
                name="time",
                option_type=OptionType.INTEGER,
                description="The time in minutes you want the giveaway to last.",
                required=True
            ),
            Option(
                name="winners",
                option_type=OptionType.INTEGER,
                description="The number of winners you want to have.",
                required=True
            ),
            Option(
                name="channel",
                option_type=OptionType.CHANNEL,
                description="The channel you want the giveaway to be in. Defaults to this one.",
                required=False
            )
        ],
        guild_ids=[ATLAS]
    )
    async def giveaway(self, ctx: SlashContext, prize: str, time: int, winners: int, channel: discord.TextChannel = None):
        if not ctx.author.permissions_in(ctx.channel).manage_messages and not ctx.author.id == self.bot.owner_id:
            return await ctx.send("You don't have the required permissions to start a giveaway.")
        if channel is None:
            channel = ctx.channel
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("You must specify a text channel.")
        if not channel.permissions_for(ctx.me).send_messages or not channel.permissions_for(ctx.me).embed_links:
            return await ctx.send(f"I don't have permission to send messages in {channel.mention}.")
        message = await self.bot.db.giveaway.create(
            prize=prize,
            channel=channel,
            duration=time*60,
            winners=winners,
            maker=ctx.author
        )
        await ctx.send(f"Giveaway created! [Jump to Message]({message.jump_url})", hidden=True)



def setup(bot):
    bot.add_cog(Giveaways(bot))
