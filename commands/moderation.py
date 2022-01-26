import os
import time
import asyncio
from typing import Union

from discord.channel import VoiceChannel, _channel_factory
from utils.objects import ModAction
import discord
from discord.ext import commands
from discord_slash import SlashContext
from discord_slash.context import MenuContext
from discord_slash import cog_ext as slash
from datetime import datetime, timedelta
from discord_slash.utils.manage_commands import create_option as Option
from discord_slash.utils.manage_commands import create_choice as Choice
from discord_slash.model import SlashCommandOptionType as OptionType
from discord_slash.model import ContextMenuType as MenuType

from utils.dpy import Embed
from utils.utils import Utils
from utils.paginator import EmbedPaginator, TextPageSource
from utils.objects import AtlasException
from bot import Bot, ATLAS

_HELPER = 849748678498975774
_MODERATOR = 849748558877949972
_GAME_MASTER = 877018778091798558
_ADMINISTRATOR = 849744644766171136

HELPER = [_HELPER,_MODERATOR,_GAME_MASTER,_ADMINISTRATOR]
MOD = [_MODERATOR,_GAME_MASTER,_ADMINISTRATOR]
GM = [_GAME_MASTER,_ADMINISTRATOR]
ADMIN = [_ADMINISTRATOR]


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.warning_threshold = {
            3: (1, 3600),
            6: (1, 172800),
            9: (3, 2592000),
        }
        self.action_types = {
            4: "LIMBO",
            3: "BAN",
            2: "KICK",
            1: "MUTE",
            0: "WARNING"
        }
        self.report_channel = self.bot.config['moderation']['reports']

    def has_any_role(self, member, roles):
        return member.guild_permissions.administrator or member.id == self.bot.owner_id or any([r in member._roles for r in roles])
        
    @slash.cog_slash(name='purge',
                     description="Purges messages. Must be less than 2 weeks old.",
                     options=[
                         Option(name='amount',
                                description="The amount of messages to remove.",
                                option_type=OptionType.INTEGER,
                                required=True),
                         Option(name='member',
                                description="Filter messages so only the member's messages are deleted. Filters cannot be mixed.",
                                option_type=OptionType.USER,
                                required=False),
                         Option(name='bot',
                                description="Filter bot messages. If set to false, bot messages will not be deleted. Filters cannot be mixed.",
                                option_type=OptionType.BOOLEAN,
                                required=False),
                     ],
                     guild_ids=[ATLAS])
    async def purge(self, ctx: SlashContext, amount: int, member: discord.Member = None, bot: bool = None):
        if not self.has_any_role(ctx.author, MOD):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        if member is not None and not isinstance(member, int):
            member = member.id
        today = datetime.now()    
        date = today - timedelta(days=14)
        if member and (bot is not None):
            raise AtlasException("Cannot mix purge filters.")
        if member:
            def check(message):
                return message.author.id == member
            msgs = await ctx.channel.purge(limit=amount, after=date, check=check)
        elif bot is not None:
            def check(message):
                return message.author.bot is bot
            msgs = await ctx.channel.purge(limit=amount, after=date, check=check)
        else:
            msgs = await ctx.channel.purge(limit=amount, after=date)
        await ctx.send(f"Purged {len(msgs)} messages.")
        
    @slash.cog_slash(name='warn',
                     description="Warns a member.",
                     options=[
                         Option(name='member',
                                description="The member to warn.",
                                option_type=OptionType.USER,
                                required=True),
                         Option(name='reason',
                                description="The reason you are warning this person.",
                                option_type=OptionType.STRING,
                                required=True),
                     ],
                     guild_ids=[ATLAS])
    async def warn(self, ctx: SlashContext, member: discord.Member, reason: str):
        if not self.has_any_role(ctx.author, HELPER):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(member, int):
            _original = member
            member = ctx.guild.get_member(member)
            if member is None:
                embed = Embed(description=f"A user with ID {_original} is not in the server.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if ctx.author.top_role.position <= member.top_role.position:
            embed = Embed(description=f"You cannot preform this action on {member.mention} because of role heirarchy.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        await self.bot.db.mod.createAction(member.id, ctx.author.id, reason, 0)
        warnings = len(await self.bot.db.mod.getActionsOfType(member.id, 0))
        m = f'{member.mention} has been warned: {reason}\nThis is their {Utils.ord(warnings)} warning.'
        to_send = f'You were issued a warning in `{ctx.author.guild.name}`.\nReason: {reason}\nThis is your {Utils.ord(warnings)} warning.'
        oto_send = f'You were issued a warning in `{ctx.author.guild.name}`.\nReason: {reason}\nThis is your {Utils.ord(warnings)} warning.'
        oto_send += "\nTo appeal this, please join our Ban Appeals server: https://discord.gg/jrU5aUEBYe"
        notified = True
        for warns, act in sorted(self.warning_threshold.items(), reverse=True, key=lambda i: i[0]):
            action, duration = act
            if warnings == warns:
                await self.bot.db.mod.createAction(member.id, ctx.author.id, f"Reached the warning threshold. {warnings}", action, duration)
                if action == 3:
                    dur = f"temporarily banned for {Utils.humanTimeDuration(duration)}." if duration is not None else 'permanently banned.'
                    to_send += f"\nBecause you have recieved {warnings} warnings, you have been " + dur
                    to_send += "\nTo appeal this, please join our Ban Appeals server: https://discord.gg/jrU5aUEBYe"
                    try:
                        embed = Embed(description=to_send, color=discord.Color.gold())
                        msg = await member.send(embed=embed)
                    except discord.HTTPException:
                        notified = False
                    try:
                        await member.ban(reason=f"Automatic ban for reaching the warning threshold. ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})")
                    except discord.HTTPException:
                        await msg.delete(delay=0.1)
                        try:
                            embed = Embed(description=oto_send, color=discord.Color.gold())
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            notified = False
                        embed = Embed(description=m + "\nI Was unable to ban them for reaching the warning threshold." + ("\nThey have not been notified." if not notified else ''), color=discord.Color.gold())
                        return await ctx.send(embed=embed, hidden=True)
                    embed = Embed(description=m + "\nThey have been banned for reaching the warning threshold." + ("\nThey have not been notified." if not notified else ''))
                    return await ctx.send(embed=embed, hidden=True)
                elif action == 1:
                    to_send += f"\nBecause you have recieved {warnings} warnings, you have been temporarily muted for {Utils.humanTimeDuration(duration)}."
                    to_send += "\nTo appeal this, please join our Ban Appeals server: https://discord.gg/jrU5aUEBYe"
                    try:
                        embed = Embed(description=to_send, color=discord.Color.gold())
                        msg = await member.send(embed=embed)
                    except discord.HTTPException:
                        notified = False
                    try:
                        await member.add_roles(discord.Object(self.bot.mute_role), reason=f"{ctx.author} ({ctx.author.id}): {reason} ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})")
                    except discord.HTTPException:
                        await msg.delete(delay=0.1)
                        try:
                            embed = Embed(description=oto_send, color=discord.Color.gold())
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            notified = False
                        embed = Embed(description=m + "\nI Was unable to mute them for reaching the warning threshold." + ("\nThey have not been notified." if not notified else ''), color=discord.Color.gold())
                        return await ctx.send(embed=embed, hidden=True)
                    embed = Embed(description=m + "\nThey have been muted for reaching the warning threshold." + ("\nThey have not been notified." if not notified else ''))
                    return await ctx.send(embed=embed, hidden=True)
                else:
                    pass
        try:
            embed = Embed(description=to_send, color=discord.Color.gold())
            await member.send(embed=embed)
        except discord.HTTPException:
            notified = False
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)

    @slash.cog_slash(name='mute',
                     description="Mutes a member.",
                     options=[
                         Option(name='member',
                                description="The member to mute.",
                                option_type=OptionType.USER,
                                required=True),
                         Option(name='reason',
                                description="The reason you are muting this person.",
                                option_type=OptionType.STRING,
                                required=True),
                         Option(name='duration',
                                description="The duration of the mute.",
                                option_type=OptionType.STRING,
                                required=False),
                     ],
                     guild_ids=[ATLAS])
    async def mute(self, ctx: SlashContext, member: discord.Member, reason: str, duration: str = None):
        if not self.has_any_role(ctx.author, HELPER):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if duration is None and not self.has_any_role(ctx.author, MOD):
            embed = Embed(description="You do not have permission to permanently mute members.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(member, int):
            _original = member
            member = ctx.guild.get_member(member)
            if member is None:
                embed = Embed(description=f"A user with ID {_original} is not in the server.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if ctx.author.top_role.position <= member.top_role.position:
            embed = Embed(description=f"You cannot preform this action on {member.mention} because of role heirarchy.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if self.bot.mute_role in member._roles:
            embed = Embed(description=f"{member.mention} is already muted.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if duration is not None:
            _duration = 0
            try:
                for s in duration.split(' '):
                    _duration += Utils.convertTime(s)
            except ValueError:
                embed = Embed(description="Invalid duration.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            if _duration <= 0:
                embed = Embed(description="Duration cannot be negative.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            duration = _duration
        await ctx.defer(hidden=True)
        await self.bot.db.mod.createAction(member.id, ctx.author.id, reason, 1, duration)
        await member.add_roles(discord.Object(self.bot.mute_role), reason=f"{ctx.author} ({ctx.author.id}): {reason} ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})")
        m = f"{member.mention} has been muted {'for ' +Utils.humanTimeDuration(duration) if duration else 'indefinitly'}: {reason}"
        to_send = f"You were muted {'for ' +Utils.humanTimeDuration(duration) if duration else 'indefinitly'} in `{ctx.author.guild.name}`.\nReason: {reason}"
        to_send += "\nTo appeal this, please join our Ban Appeals server: https://discord.gg/jrU5aUEBYe"
        notified = True
        try:
            embed = Embed(description=to_send, color=discord.Color.gold())
            await member.send(embed=embed)
        except discord.HTTPException:
            notified = False
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)

    @slash.cog_slash(name='unmute',
                     description="Unmutes a member.",
                     options=[
                         Option(name='member',
                                description="The member to unmute.",
                                option_type=OptionType.USER,
                                required=True)
                     ],
                     guild_ids=[ATLAS])
    async def unmute(self, ctx: SlashContext, member: discord.Member):
        if not self.has_any_role(ctx.author, MOD):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(member, int):
            _original = member
            member = ctx.guild.get_member(member)
            if member is None:
                embed = Embed(description=f"A user with ID {_original} is not in the server.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if self.bot.mute_role not in member._roles:
            embed = Embed(description=f"{member.mention} is not muted.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        await member.remove_roles(discord.Object(self.bot.mute_role), reason=f"{ctx.author} ({ctx.author.id}) - UNMUTE")
        actions = await self.bot.db.mod.getActionsOfType(member.id, 1)
        for action in actions:
            if not action.expired and (action.expires is None or action.expires <= time.time()):
                try:
                    await self.bot.db.mod.expireAction(action.id)
                except AtlasException:
                    pass
        m = f"{member.mention} has been unmuted."
        to_send = f"You have been unmuted in `{ctx.author.guild.name}`."
        notified = True
        try:
            embed = Embed(description=to_send)
            await member.send(embed=embed)
        except discord.HTTPException:
            notified = False
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)
        log_channel = self.bot.get_channel(self.bot.db.mod.log_channel)
        embed = Embed(title='Unmute', description=f"Member: {member.mention}\nModerator: {ctx.author.mention}", color=discord.Color.green())
        if log_channel is not None:
            await log_channel.send(embed=embed)

    @slash.cog_slash(name='ban',
                     description="Bans a member.",
                     options=[
                         Option(name='member',
                                description="The member to ban.",
                                option_type=OptionType.USER,
                                required=True),
                         Option(name='reason',
                                description="The reason you are banning this person.",
                                option_type=OptionType.STRING,
                                required=True),
                         Option(name='duration',
                                description="The duration of the ban.",
                                option_type=OptionType.STRING,
                                required=False),
                     ],
                     guild_ids=[ATLAS])
    async def ban(self, ctx: SlashContext, member: discord.Member, reason: str, duration: str = None):
        if not self.has_any_role(ctx.author, MOD):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(member, int):
            _original = member
            member = await self.bot.get_or_fetch_user(member)
            if member is None:
                embed = Embed(description=f"A user with the ID {_original} does not exist.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        else:
            if ctx.author.top_role.position <= member.top_role.position:
                embed = Embed(description=f"You cannot preform this action on {member.mention} because of role heirarchy.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            if ctx.guild.me.top_role.position <= member.top_role.position:
                embed = Embed(description=f"I cannot do that to {member.mention} because of role heirarchy.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if duration is not None:
            _duration = 0
            try:
                for s in duration.split(' '):
                    _duration += Utils.convertTime(s)
            except ValueError:
                embed = Embed(description="Invalid duration.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            if _duration <= 0:
                embed = Embed(description="Duration cannot be negative.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            duration = _duration
        await ctx.defer(hidden=True)
        await self.bot.db.mod.createAction(member.id, ctx.author.id, reason, 3, duration)
        m = f"{member.mention} has been banned {'for ' +Utils.humanTimeDuration(duration) if duration else 'indefinitly'}: {reason}"
        to_send = f"You were {'permanently ' if duration else ''}banned {'for ' +Utils.humanTimeDuration(duration) if duration else ''} from `{ctx.author.guild.name}`.\nReason: {reason}"
        to_send += "\nTo appeal this, please join our Ban Appeals server: https://discord.gg/jrU5aUEBYe"
        notified = True
        try:
            embed = Embed(description=to_send, color=discord.Color.gold())
            await member.send(embed=embed)
            await ctx.guild.ban(member, reason=f"{ctx.author} ({ctx.author.id}): {reason} ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})", delete_message_days=1)
        except discord.HTTPException:
            notified = False
            await ctx.guild.ban(member, reason=f"{ctx.author} ({ctx.author.id}): {reason} ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})", delete_message_days=1)
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)

    @slash.cog_slash(name='unban',
                     description="Unbans a user.",
                     options=[
                         Option(name='user',
                                description="The user to unban.",
                                option_type=OptionType.USER,
                                required=True)
                     ],
                     guild_ids=[ATLAS])
    async def unban(self, ctx: SlashContext, user: discord.Member):
        if not self.has_any_role(ctx.author, MOD):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(user, discord.Member):
            embed = Embed(description=f"{user.mention} is not banned.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        member = await self.bot.get_or_fetch_user(user)
        if member is None:
            embed = Embed(description="Invalid user.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        try:
            await ctx.guild.unban(member, reason=f"{ctx.author} ({ctx.author.id}) - UNBAN")
        except discord.NotFound:
            embed = Embed(description=f"{member.mention} is not banned.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        actions = await self.bot.db.mod.getActionsOfType(member.id, 3)
        for action in actions:
            if not action.expired and (action.expires is None or action.expires <= time.time()):
                try:
                    await self.bot.db.mod.expireAction(action.id)
                except AtlasException:
                    pass
        m = f"{member.mention} has been unbanned."
        to_send = f"You were unbanned from `{ctx.author.guild.name}`."
        notified = True
        try:
            embed = Embed(description=to_send)
            await member.send(embed=embed)
        except discord.HTTPException:
            notified = False
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)
        log_channel = self.bot.get_channel(self.bot.db.mod.log_channel)
        embed = Embed(title='Unban', description=f"Member: {member.mention}\nModerator: {ctx.author.mention}", color=discord.Color.green())
        if log_channel is not None:
            await log_channel.send(embed=embed)
       
    @slash.cog_slash(name='kick',
                     description="Kicks a member.",
                     options=[
                         Option(name='member',
                                description="The member to kick.",
                                option_type=OptionType.USER,
                                required=True),
                         Option(name='reason',
                                description="The reason you are kicking this person.",
                                option_type=OptionType.STRING,
                                required=True)
                     ],
                     guild_ids=[ATLAS])
    async def kick(self, ctx: SlashContext, member: discord.Member, reason: str):
        if not self.has_any_role(ctx.author, HELPER):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(member, int):
            _original = member
            member = ctx.guild.get_member(member)
            if member is None:
                embed = Embed(description=f"A user with ID {_original} is not in the server.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if ctx.author.top_role.position <= member.top_role.position:
            embed = Embed(description=f"You cannot preform this action on {member.mention} because of role heirarchy.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if ctx.guild.me.top_role.position <= member.top_role.position:
            embed = Embed(description=f"I cannot do that to {member.mention} because of role heirarchy.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        await self.bot.db.mod.createAction(member.id, ctx.author.id, reason, 2)
        m = f"{member.mention} has been kicked: {reason}"
        to_send = f"You were kicked from `{ctx.author.guild.name}`.\nReason: {reason}\nYou can rejoin at https://discord.gg/atlasmc."
        notified = True
        try:
            embed = Embed(description=to_send, color=discord.Color.gold())
            await member.send(embed=embed)
            await member.kick(reason=f"{ctx.author} ({ctx.author.id}): {reason}")
        except discord.HTTPException:
            notified = False
            await member.kick(reason=f"{ctx.author} ({ctx.author.id}): {reason}")
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)

    @slash.cog_slash(name='limbo',
                     description="Puts a member into limbo.",
                     options=[
                         Option(name='member',
                                description="The member to put into limbo.",
                                option_type=OptionType.USER,
                                required=True),
                         Option(name='reason',
                                description="The reason you are sending this person to limbo.",
                                option_type=OptionType.STRING,
                                required=True),
                         Option(name='duration',
                                description="The duration of the limbo.",
                                option_type=OptionType.STRING,
                                required=False),
                     ],
                     guild_ids=[ATLAS])
    async def limbo(self, ctx: SlashContext, member: discord.Member, reason: str, duration: str = None):
        if not self.has_any_role(ctx.author, MOD):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(member, int):
            _original = member
            member = ctx.guild.get_member(member)
            if member is None:
                embed = Embed(description=f"A user with ID {_original} is not in the server.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if ctx.author.top_role.position <= member.top_role.position:
            embed = Embed(description=f"You cannot preform this action on {member.mention} because of role heirarchy.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if self.bot.limbo_role not in member._roles:
            embed = Embed(description=f"{member.mention} is not verified.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if duration is not None:
            _duration = 0
            try:
                for s in duration.split(' '):
                    _duration += Utils.convertTime(s)
            except ValueError:
                embed = Embed(description="Invalid duration.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            if _duration <= 0:
                embed = Embed(description="Duration cannot be negative.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            duration = _duration
        await ctx.defer(hidden=True)
        await self.bot.db.mod.createAction(member.id, ctx.author.id, reason, 4, duration)
        await member.remove_roles(discord.Object(self.bot.limbo_role), reason=f"{ctx.author} ({ctx.author.id}): {reason} ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})")
        m = f"{member.mention} has been put into limbo {'for ' +Utils.humanTimeDuration(duration) if duration else 'indefinitly'}: {reason}"
        to_send = f"You were {'permanently ' if duration else ''}sent to limbo {'for ' +Utils.humanTimeDuration(duration) if duration else ''} in `{ctx.author.guild.name}`.\nReason: {reason}"
        notified = True
        try:
            embed = Embed(description=to_send, color=discord.Color.gold())
            await member.send(embed=embed)
        except discord.HTTPException:
            notified = False
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)

    @slash.cog_slash(name='unlimbo',
                     description="Takes a member out of limbo.",
                     options=[
                         Option(name='member',
                                description="The member to un-limbo.",
                                option_type=OptionType.USER,
                                required=True)
                     ],
                     guild_ids=[ATLAS])
    async def unlimbo(self, ctx: SlashContext, member: discord.Member):
        if not self.has_any_role(ctx.author, MOD):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if isinstance(member, int):
            _original = member
            member = ctx.guild.get_member(member)
            if member is None:
                embed = Embed(description=f"A user with ID {_original} is not in the server.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if self.bot.limbo_role in member._roles:
            embed = Embed(description=f"{member.mention} is not in limbo.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        await member.add_roles(discord.Object(self.bot.limbo_role), reason=f"{ctx.author} ({ctx.author.id}) - UNLIMBO")
        actions = await self.bot.db.mod.getActionsOfType(member.id, 4)
        for action in actions:
            if not action.expired and (action.expires is None or (action.expires is None or action.expires <= time.time())):
                try:
                    await self.bot.db.mod.expireAction(action.id)
                except AtlasException:
                    pass
        m = f"{member.mention} has been taken out of limbo."
        to_send = f"You were removed from limbo in `{ctx.author.guild.name}`."
        notified = True
        try:
            embed = Embed(description=to_send)
            await member.send(embed=embed)
        except discord.HTTPException:
            notified = False
        embed = Embed(description=m + ("\nThey have not been notified." if not notified else ''))
        await ctx.send(embed=embed, hidden=True)
        log_channel = self.bot.get_channel(self.bot.db.mod.log_channel)
        embed = Embed(title='Unlimbo', description=f"Member: {member.mention}\nModerator: {ctx.author.mention}", color=discord.Color.green())
        if log_channel is not None:
            await log_channel.send(embed=embed)
    
    @slash.cog_slash(name='actions',
                     description="Shows a list of moderation actions taken against a member.",
                     options=[
                         Option(name='member',
                                description="The member to show actions for.",
                                option_type=OptionType.USER,
                                required=True),
                         Option(name='action_type',
                                description="The type of action to show.",
                                option_type=OptionType.INTEGER,
                                choices=[
                                    Choice(name='Warning', value=0),
                                    Choice(name='Mute', value=1),
                                    Choice(name='Kick', value=2),
                                    Choice(name='Ban', value=3),
                                    Choice(name='Limbo', value=4),
                                ],
                                required=False)
                     ],
                     guild_ids=[ATLAS])
    async def actions(self, ctx: SlashContext, member: discord.Member, action_type: int = None):
        await ctx.defer()
        if isinstance(member, int):
            member = await self.bot.get_or_fetch_user(member)
            if member is None:
                embed = Embed(description="Invalid user.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        if member.id != ctx.author.id:
            if not self.has_any_role(ctx.author, HELPER):
                embed = Embed(description="You do not have permission to view the moderation history of other members.", color=discord.Color.red())
                return await ctx.send(embed=embed)
        _mod = True
        if not self.has_any_role(ctx.author, HELPER):
            _mod = False
        if action_type is None:
            actions = await self.bot.db.mod.getActions(member.id)
        else:
            actions = await self.bot.db.mod.getActionsOfType(member.id, action_type)
        if not actions:
            embed = Embed(description=f"{member.mention} has no moderation history.", color=discord.Color.red())
            return await ctx.send(embed=embed)
        embeds = []
        embed = Embed(description=f"{len(actions)} actions taken against {member.mention}")
        i = 0
        for a in actions:
            i += 1
            if i > 9:
                embeds.append(embed)
                embed = Embed(description=f"{len(actions)} actions taken against {member.mention}")
                i = 1
            modmsg = ''
            if _mod:
                modmsg = f"Moderator: <@!{a.mod}>\n"
            exp = f"Expire{'d' if a.expired else 's'} <t:{a.expires}:R>" if a.expires is not None else ('Removed by a moderator.' if a.expired else 'Does not expire.')
            embed.add_field(name=f"#{a.id} - {self.action_types[a.action_type]}", 
                            value=modmsg + f"Reason: {a.reason}\n"
                                  f"Time: <t:{a.time}>\n" + exp)
        embeds.append(embed)
        return await EmbedPaginator(ctx, embeds).run()

    @slash.cog_slash(name='action',
                     description="Shows information on a specific moderation action.",
                     options=[
                         Option(name='action',
                                description="The ID of the action to show.",
                                option_type=OptionType.INTEGER,
                                required=True)
                     ],
                     guild_ids=[ATLAS])
    async def action(self, ctx: SlashContext, action: int):
        await ctx.defer()
        try:
            action: ModAction = await self.bot.db.mod.getAction(action)
        except AtlasException as e:
            embed = Embed(description=str(e), color=discord.Color.red())
            return await ctx.send(embed=embed)
        if action.user != ctx.author.id:
            if not self.has_any_role(ctx.author, HELPER):
                embed = Embed(description="You do not have permission to view the moderation history of other members.", color=discord.Color.red())
                return await ctx.send(embed=embed)
        _mod = True
        if not self.has_any_role(ctx.author, HELPER):
            _mod = False
        exp = f"Expire{'d' if action.expired else 's'} <t:{action.expires}:R>" if action.expires is not None else 'Does not expire.'
        modmsg = ''
        if _mod:
            modmsg = f"Moderator: <@!{action.mod}>\n"
        embed = Embed(title=f"Moderation Action #{action.id}",
                      description=f"User: <@!{action.user}>\n"
                                  f"{modmsg}"
                                  f"Reason: {action.reason}\n"
                                  f"Time: <t:{action.time}>\n" + exp,
                      color=discord.Color.green())
        return await ctx.send(embed=embed)

    @slash.cog_slash(name='remove-action',
                     description="Removes an action from a member's moderation history.",
                     options=[
                         Option(name='action',
                                description="The ID of the action to remove.",
                                option_type=OptionType.INTEGER,
                                required=True)
                     ],
                     guild_ids=[ATLAS])
    async def remove_action(self, ctx: SlashContext, action: int):
        if not self.has_any_role(ctx.author, ADMIN):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await ctx.defer(hidden=True)
        try:
            action: ModAction = await self.bot.db.mod.deleteAction(action)
        except AtlasException as e:
            embed = Embed(description=str(e), color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        embed = Embed(description=f"Removed action #{action.id} from <@!{action.user}>",
                      color=discord.Color.green())
        await ctx.send(embed=embed, hidden=True)
        log_channel = self.bot.get_channel(self.bot.db.mod.log_channel)
        embed = Embed(title='Action Removed', description=f"Member: <@!{action.user}>\nModerator: {ctx.author.mention}\nAction ID: {action.id}\nAction Reason: {action.reason}", color=discord.Color.green())
        if log_channel is not None:
            await log_channel.send(embed=embed)

    @slash.cog_subcommand(base="report",
                          base_desc="Report a user for breaking the rules.",
                          name='discord',
                          description="Report someone for breaking rules on the Discord.",
                          options=[
                              Option(name='user',
                                     description="The user you want to report.",
                                     option_type=OptionType.USER,
                                     required=True),
                              Option(name='reason',
                                     description="The reason you are reporting them.",
                                     option_type=OptionType.STRING,
                                     required=True),
                              Option(name='proof',
                                     description="Evidence of them breaking the rules. Leave this blank to provide things such as image uploads.",
                                     option_type=OptionType.STRING,
                                     required=False),
                          ],
                          guild_ids=[ATLAS])
    async def report_dc(self, ctx: SlashContext, user: discord.Member, reason: str, proof: str = None):
        if isinstance(user, int):
            _original = user
            member = ctx.guild.get_member(user)
            if member is None:
                embed = Embed(description="That user doesn't appear to be in the server.", color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
        report_channel = self.bot.get_channel(self.report_channel)
        if report_channel is None:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `NOTFOUND`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        _dmed = False
        if proof is None:
            _dmed = True
            try:
                _m = await ctx.author.send("Please reply to this message with evidence for your report.")
            except discord.HTTPException:
                embed = Embed(description="I cannot DM you.", color=discord.Color.red())
                return await ctx.send(embed=embed)
            await ctx.reply(content="Check your DMs!", hidden=True)
            try:
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.guild is None, timeout=60)
            except asyncio.TimeoutError:
                embed = Embed(description="You took too long to respond.", color=discord.Color.red())
                return await _m.reply(embed=embed)
            proof = msg.content or ''
            if msg.attachments:
                proof += '\n'
                proof += '\n'.join([a.url for a in msg.attachments])
        embed = Embed(title="Discord Report",
                      description=f"Reported by: {ctx.author} (`{ctx.author.id}`)\nSuspect: {user} (`{user.id}`)",
                      color=discord.Color.gold())
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Evidence", value=proof)
        try:
            await report_channel.send(embed=embed)
        except discord.HTTPException:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `SENDFAIL`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if _dmed:
            embed = Embed(description="Thanks for your report! It will be reviewed and appropriate action will be taken.")
            return await msg.reply(embed=embed)
        embed = Embed(description="Thanks for your report! It will be reviewed and appropriate action will be taken.")
        return await ctx.send(embed=embed, hidden=True)

    @slash.cog_subcommand(base="report",
                          base_desc="Report a user for breaking the rules.",
                          name='minecraft',
                          description="Report someone for breaking rules on the Minecraft Server.",
                          options=[
                              Option(name='player',
                                     description="The player you want to report.",
                                     option_type=OptionType.STRING,
                                     required=True),
                              Option(name='reason',
                                     description="The reason you are reporting them.",
                                     option_type=OptionType.STRING,
                                     required=True),
                              Option(name='proof',
                                     description="Evidence of them breaking the rules. Leave this blank to provide things such as image uploads.",
                                     option_type=OptionType.STRING,
                                     required=False),
                          ],
                          guild_ids=[ATLAS])
    async def report_mc(self, ctx: SlashContext, player: str, reason: str, proof: str = None):
        uuid = await Utils.getuuid(player)
        player = await Utils.getname(uuid)
        report_channel = self.bot.get_channel(self.report_channel)
        if report_channel is None:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `NOTFOUND`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        _dmed = False
        if proof is None:
            _dmed = True
            try:
                _m = await ctx.author.send("Please reply to this message with evidence for your report.")
            except discord.HTTPException:
                embed = Embed(description="I cannot DM you.", color=discord.Color.red())
                return await ctx.send(embed=embed)
            await ctx.reply(content="Check your DMs!", hidden=True)
            try:
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.guild is None, timeout=60)
            except asyncio.TimeoutError:
                embed = Embed(description="You took too long to respond.", color=discord.Color.red())
                return await _m.reply(embed=embed)
            proof = msg.content or ''
            if msg.attachments:
                proof += '\n'
                proof += '\n'.join([a.url for a in msg.attachments])
        embed = Embed(title="Minecraft Report",
                      description=f"Reported by: {ctx.author} (`{ctx.author.id}`)\nSuspect: {player}\nSuspect UUID: `{uuid}`",
                      color=discord.Color.gold())
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Evidence", value=proof)
        try:
            await report_channel.send(embed=embed)
        except discord.HTTPException:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `SENDFAIL`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if _dmed:
            embed = Embed(description="Thanks for your report! It will be reviewed and appropriate action will be taken.")
            return await msg.reply(embed=embed)
        embed = Embed(description="Thanks for your report! It will be reviewed and appropriate action will be taken.")
        return await ctx.send(embed=embed, hidden=True)

    @slash.cog_context_menu(name="Report",
                            target=MenuType.MESSAGE,
                            guild_ids=[ATLAS])
    async def report_menu(self, ctx: MenuContext):
        report_channel = self.bot.get_channel(self.report_channel)
        if report_channel is None:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `NOTFOUND`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if ctx.target_message is None:
            embed = Embed(description="The message you tried to report couldn't be found.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        try:
            _m = await ctx.author.send("Please reply to this message with your report reason.")
        except discord.HTTPException:
            embed = Embed(description="I cannot DM you.", color=discord.Color.red())
            return await ctx.send(embed=embed)
        await ctx.reply(content="Check your DMs!", hidden=True)
        try:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.guild is None, timeout=60)
        except asyncio.TimeoutError:
            embed = Embed(description="You took too long to respond.", color=discord.Color.red())
            return await _m.reply(embed=embed)
        reason = msg.content
        if not reason:
            embed = Embed(description="You didn't provide a reason for your report. Report cancelled.", color=discord.Color.red())
            return await msg.reply(embed=embed)
        embed = Embed(title="Discord Report",
                      description=f"Reported by: {ctx.author} (`{ctx.author.id}`)\nSuspect: {ctx.target_message.author} (`{ctx.target_message.author.id}`)",
                      color=discord.Color.gold())
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Message Content", value=ctx.target_message.content + "\n\n[Jump to Message](" + ctx.target_message.jump_url + ")")
        if msg.attachments:
            embed.add_field(name="Attachments", value='\n'.join([a.url for a in msg.attachments]))
        try:
            await report_channel.send(embed=embed)
        except discord.HTTPException:
            embed = Embed(description="Something went wrong. Please contact an administrator.\nError Code: `SENDFAIL`", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        embed = Embed(description="Thanks for your report! It will be reviewed and appropriate action will be taken.")
        return await msg.reply(embed=embed)

    @slash.cog_subcommand(base="lock",
                          base_desc="Lock a channel or the server",
                          name='server',
                          description="Locks the server.",
                          options=[
                              Option(name='locked', description="Whether the server should be locked or not.", option_type=OptionType.BOOLEAN, required=True),
                              Option(name='reason', description="The reason for locking the server. Not required for unlocking.", option_type=OptionType.STRING, required=False),
                          ],
                          guild_ids=[ATLAS])
    async def lock_server(self, ctx: SlashContext, locked: bool, reason: str = None):
        if not self.has_any_role(ctx.author, ADMIN):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if not locked:
            locked = None
        else:
            locked = False
        if reason is None and locked:
            return await ctx.send('Must provide a reason for locking.', hidden=True)
        await ctx.defer(hidden=True)
        embed = Embed(
            title="🔒 Channel Locked", 
            description=f"The server has been locked by {ctx.author} (`{ctx.author.id}`).\n\nReason:\n{reason}", 
            color=discord.Color.gold()
        )
        to_lock_categories = [849720015321825332, 856499927990927390]
        to_lock_channels = [906341979321929748, 877975691197546576, 875500769892253796]
        role = ctx.guild.default_role
        _locked = 0
        for category in to_lock_categories:
            category: discord.CategoryChannel = self.bot.get_channel(category)
            for channel in category.text_channels:
                perms = channel.overwrites_for(role)
                perms.update(send_messages=locked)
                await channel.set_permissions(role, overwrite=perms)
                if locked is not None:
                    await channel.send(embed=embed)
                _locked += 1
            for channel in category.voice_channels:
                perms = channel.overwrites_for(role)
                perms.update(speak=locked)
                await channel.set_permissions(role, overwrite=perms)
                _locked += 1
        for channel in to_lock_channels:
            channel = self.bot.get_channel(channel)
            if channel.type == discord.ChannelType.text:
                perms = channel.overwrites_for(role)
                perms.update(send_messages=locked)
                if locked is not None:
                    await channel.send(embed=embed)
            elif channel.type in (discord.ChannelType.voice, discord.ChannelType.stage_voice):
                perms = channel.overwrites_for(role)
                perms.update(speak=locked)
            _locked += 1
            await channel.set_permissions(role, overwrite=perms)
        await ctx.send(f"{'Locked' if locked is not None else 'Unlocked'} {_locked} channels.", hidden=True)
        
    @slash.cog_subcommand(base="lock",
                          base_desc="Lock a channel or the server",
                          name='channel',
                          description="Locks a channel.",
                          options=[
                              Option(name='channel', description="The channel to lock. If a category, will lock all channels in the category.", option_type=OptionType.CHANNEL, required=True),
                              Option(name='locked', description="Whether the channel should be locked or not.", option_type=OptionType.BOOLEAN, required=True),
                              Option(name='reason', description="The reason for locking the channel. Not required for unlocking.", option_type=OptionType.STRING, required=False),
                          ],
                          guild_ids=[ATLAS])
    async def lock_server(self, ctx: SlashContext, channel, locked: bool, reason: str = None):
        if not self.has_any_role(ctx.author, ADMIN):
            embed = Embed(description="You do not have permission to run this command.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        if not locked:
            locked = None
        else:
            locked = False
        if reason is None and locked:
            return await ctx.send('Must provide a reason for locking.', hidden=True)
        await ctx.defer(hidden=True)
        embed = Embed(
            title="🔒 Channel Locked", 
            description=f"This channel has been locked by {ctx.author} (`{ctx.author.id}`).\n\nReason:\n{reason}", 
            color=discord.Color.gold()
        )
        role = ctx.guild.default_role
        if channel.type == discord.ChannelType.category:
            channel: discord.CategoryChannel
            for c in channel.text_channels:
                perms = c.overwrites_for(role)
                perms.update(send_messages=locked)
                await c.set_permissions(role, overwrite=perms)
                if locked is not None:
                    await c.send(embed=embed)
            for c in channel.voice_channels:
                perms = c.overwrites_for(role)
                perms.update(speak=locked)
                await c.set_permissions(role, overwrite=perms)
            for c in channel.stage_channels:
                perms = c.overwrites_for(role)
                perms.update(speak=locked)
                await c.set_permissions(role, overwrite=perms)
        elif channel.type == discord.ChannelType.text:
            perms = channel.overwrites_for(role)
            perms.update(send_messages=locked)
            await channel.set_permissions(role, overwrite=perms)
            if locked is not None:
                await channel.send(embed=embed)
        elif channel.type in (discord.ChannelType.voice, discord.ChannelType.stage_voice):
            perms = channel.overwrites_for(role)
            perms.update(speak=locked)
            await channel.set_permissions(role, overwrite=perms)
        else:
            return await ctx.send('Invalid channel type.', hidden=True)
        await ctx.send(f"{'Locked' if locked is not None else 'Unlocked'} {channel.mention}.", hidden=True)
                

def setup(bot):
    bot.add_cog(Moderation(bot))
