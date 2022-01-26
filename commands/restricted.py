import json
import asyncio
import re
import discord
from discord.ext import commands
import discord_slash
from discord_slash import SlashContext
from discord_slash import cog_ext as slash
from discord_slash.utils.manage_commands import create_permission as Permission
from discord_slash.utils.manage_commands import create_option as Option
from discord_slash.utils.manage_commands import create_choice as Choice
from discord_slash.utils.manage_components import create_button as Button
from discord_slash.utils.manage_components import create_select as Select
from discord_slash.utils.manage_components import create_select_option as SelectOption
from discord_slash.utils.manage_components import create_actionrow as ActionRow
from discord_slash.model import ButtonStyle, SlashCommandOptionType as OptionType, SlashCommandPermissionType

from utils.dpy import Embed
from utils.utils import Utils
from utils.paginator import EmbedPaginator, TextPageSource
from bot import Bot, GUILDS

class Restricted(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot

    @slash.cog_slash(name="sync-commands",
                     description="Updates the command list.",
                     default_permission=False,
                     guild_ids=GUILDS)
    @slash.permission(830345347867476000, 
                      [
                          Permission(id=830344767027675166, id_type=SlashCommandPermissionType.USER, permission=True)
                      ])
    async def sync_commands(self, ctx: SlashContext):
        await ctx.defer(hidden=True)
        await self.bot.sync_commands()
        await ctx.send("Commands synced!", hidden=True)

    @slash.cog_slash(name="reboot",
                     description="Restarts the bot.",
                     default_permission=False,
                     guild_ids=GUILDS)
    @slash.permission(830345347867476000, 
                      [
                          Permission(id=830344767027675166, id_type=SlashCommandPermissionType.USER, permission=True)
                      ])
    async def reboot(self, ctx: SlashContext):
        await ctx.send("Rebooting...", hidden=True)
        await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Game("on mc.the-atlas.net"))
        await Utils.reboot()
          

def setup(bot):
    bot.add_cog(Restricted(bot))
