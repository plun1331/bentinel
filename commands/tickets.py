import io
import json
import asyncio
import re
import time
from typing import List
import discord
from discord.ext import commands, tasks
import discord_slash
from discord_slash import SlashContext, ComponentContext
from discord_slash import cog_ext as slash
from discord_slash.utils.manage_commands import create_option as Option
from discord_slash.utils.manage_commands import create_choice as Choice
from discord_slash.utils.manage_components import create_button as Button
from discord_slash.utils.manage_components import create_select as Select
from discord_slash.utils.manage_components import create_select_option as SelectOption
from discord_slash.utils.manage_components import create_actionrow as ActionRow
from discord_slash.model import ButtonStyle, SlashCommandOptionType as OptionType

from utils.dpy import Embed, message_to_json, save_channel
from utils.utils import Utils
from utils.paginator import EmbedPaginator, TextPageSource
from utils.objects import Ticket, AtlasException
from bot import Bot, ATLAS


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.ticket_timeout = 60*10 # 10 minutes
        self._check_tickets.start()
        self.ticket_category = self.bot.config['tickets']['category']
        self.panel = self.bot.config['tickets']['channel']
        self.role = self.bot.config['tickets']['role']
        self.archive = self.bot.config['tickets']['archive']
        self.transcript = self.bot.config['tickets']['transcripts']
        """
        Ticket States:
        0 - Created, no response yet.
        1 - User responded, no admin response yet.
        2 - Admin responded, ticket is opened.
        3 - Ticket is closed.
        """

    def cog_unload(self):
        self._check_tickets.cancel()

    @tasks.loop(seconds=30)
    async def _check_tickets(self):
        guild = self.bot.get_guild(self.bot.guild_id)
        tickets: List[Ticket] = await self.bot.db.tickets.getAll()
        for ticket in tickets:
            if ticket.state == 0:
                if ticket.created_at + self.ticket_timeout < time.time():
                    member = guild.get_member(ticket.user)
                    channel = guild.get_channel(ticket.channel)
                    if channel is None:
                        continue
                    if member:
                        embed = Embed(
                            description=f"Your ticket has been deleted because you failed to respond to it within 10 minutes.",
                            color=discord.Color.red()
                        )
                        try:
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            pass
                    await self.bot.db.tickets.remove(ticket.id)
                    await channel.delete()

    @_check_tickets.before_loop
    async def before_check_tickets(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_component(self, ctx: ComponentContext):
        if ctx.custom_id != 'ticket-open':
            return
        await ctx.defer(hidden=True)
        _id = await self.bot.db.tickets.getNewID()
        channel = await ctx.guild.create_text_channel(
            name=f"ticket-{_id}", 
            overwrites={
                ctx.author: discord.PermissionOverwrite(
                    read_messages=True, 
                    send_messages=True, 
                    read_message_history=True
                ), 
                ctx.guild.default_role: discord.PermissionOverwrite(
                    read_messages=False
                ),
                ctx.guild.get_role(self.role): discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True
                )
            },
            category=self.bot.get_channel(self.ticket_category)
        )
        embed = Embed(
            title="Welcome!",
            description="Thank you for creating a ticket. Please specify why you opened this ticket within 10 minutes, or this ticket will be closed."
        )
        await channel.send(ctx.author.mention, embed=embed)
        await self.bot.db.tickets.add(ctx.author.id, channel.id)
        await ctx.send(f"Your ticket has been created. {channel.mention}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.guild.id != self.bot.guild_id:
            return
        channel: discord.TextChannel = message.channel
        try:
            ticket: Ticket = await self.bot.db.tickets.getChannel(channel.id)
        except AtlasException:
            return
        if ticket.state != 0:
            return
        if ticket.user != message.author.id:
            return
        await self.bot.db.tickets.updateState(ticket.id, 1)
        await channel.set_permissions(message.author, read_messages=True, send_messages=False, read_message_history=True)
        await message.reply(f"<@&{self.role}>", embed=Embed(
            description=f"Thank you for your response. A staff member will be with you shortly."
        ))
        
    @slash.cog_subcommand(
        base="tickets",
        base_desc="Manage tickets.",
        name="accept",
        description="Accept a ticket.",
        guild_ids=[ATLAS]
    )
    async def ticket_accept(self, ctx: SlashContext):
        if not ctx.author.guild_permissions.administrator and not self.role in ctx.author._roles:
            embed = Embed(description="You do not have permission to preform that action.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        guild = ctx.guild
        ticket: Ticket = await self.bot.db.tickets.getChannel(ctx.channel_id)
        if ticket.state != 1:
            embed = Embed(description="This ticket either has already been accepted, or the user hasn't responded to it yet.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        channel = guild.get_channel(ticket.channel)
        if channel is None:
            await self.bot.db.tickets.remove(ticket.id)
            embed = Embed(description="This ticket has been deleted.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await self.bot.db.tickets.updateState(ticket.id, 2)
        member = guild.get_member(ticket.user)
        if member is None:
            embed = Embed(description="The user who created this ticket left the server. Deleting in 5 seconds...", color=discord.Color.red())
            await ctx.send(embed=embed, hidden=True)
            await asyncio.sleep(5)
            await self.bot.db.tickets.remove(ticket.id)
            return await channel.delete()
        await channel.set_permissions(member, read_messages=True, send_messages=True, read_message_history=True)
        await channel.send(f"{member.mention}", embed=Embed(
            description=f"Your ticket has been accepted by {ctx.author.mention}."
        ))
        await ctx.send(embed=Embed(description=f"Ticket #{ticket.id} has been accepted. {channel.mention}"), hidden=True)

    @slash.cog_subcommand(
        base="tickets",
        base_desc="Manage tickets.",
        name="deny",
        description="Deny a ticket.",
        options=[
            Option(
                name="reason",
                option_type=OptionType.STRING,
                description="The denial reason.",
                required=True
            )
        ],
        guild_ids=[ATLAS]
    )
    async def ticket_deny(self, ctx: SlashContext, reason: str):
        if not ctx.author.guild_permissions.administrator and not self.role in ctx.author._roles:
            embed = Embed(description="You do not have permission to preform that action.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        guild = ctx.guild
        ticket: Ticket = await self.bot.db.tickets.getChannel(ctx.channel_id)
        if ticket.state != 1:
            embed = Embed(description="This ticket either has already been accepted, or the user hasn't responded to it yet.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        channel = guild.get_channel(ticket.channel)
        if channel is None:
            await self.bot.db.tickets.remove(ticket.id)
            embed = Embed(description="This ticket has been deleted.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await self.bot.db.tickets.updateState(ticket.id, 2)
        member = guild.get_member(ticket.user)
        if member is None:
            embed = Embed(description="The user who created this ticket left the server. Deleting in 5 seconds...", color=discord.Color.red())
            await ctx.send(embed=embed, hidden=True)
            await asyncio.sleep(5)
            await self.bot.db.tickets.remove(ticket.id)
            return await channel.delete()
        try:
            await member.send(embed=Embed(
                description=f"Your ticket has been denied by {ctx.author.mention}.\nReason:\n{reason}"
            ))
        except discord.HTTPException:
            pass
        await self.bot.db.tickets.remove(ticket.id)
        await channel.delete()
        await ctx.send(embed=Embed(description=f"Ticket #{ticket.id} denied."), hidden=True)

    @slash.cog_subcommand(
        base="tickets",
        base_desc="Manage tickets.",
        name="close",
        description="Close a ticket.",
        options=[
            Option(
                name="reason",
                option_type=OptionType.STRING,
                description="The reason you are closing it.",
                required=True
            )
        ],
        guild_ids=[ATLAS]
    )
    async def ticket_close(self, ctx: SlashContext, reason: str):
        if not ctx.author.guild_permissions.administrator and not self.role in ctx.author._roles:
            embed = Embed(description="You do not have permission to preform that action.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        guild = ctx.guild
        ticket: Ticket = await self.bot.db.tickets.getChannel(ctx.channel_id)
        if ticket.state != 2:
            embed = Embed(description="This ticket has already been closed, or has not been replied to yet.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        channel = guild.get_channel(ticket.channel)
        if channel is None:
            await self.bot.db.tickets.remove(ticket.id)
            embed = Embed(description="This ticket has been deleted.", color=discord.Color.red())
            return await ctx.send(embed=embed, hidden=True)
        await channel.send(embed=Embed(description=f"Ticket closed by {ctx.author.mention}. A transcript will be saved and the ticket will be deleted shortly."))
        await self.bot.db.tickets.updateState(ticket.id, 3)
        member = guild.get_member(ticket.user)
        if member is not None:
            await channel.set_permissions(member, read_messages=False)
            try:
                await member.send(embed=Embed(
                    description=f"Your ticket has been closed by {ctx.author.mention}.\nReason:\n{reason}"
                ))
            except discord.HTTPException:
                pass
        await ctx.send(embed=Embed(description=f"Ticket #{ticket.id} closed."), hidden=True)
        output = await save_channel(channel)
        _file = io.BytesIO(output.encode('utf-8'))
        _file.seek(0)
        _channel = self.bot.get_channel(self.transcript)
        if _channel is not None:
            _edit_msg = await _channel.send(file=discord.File(_file, f"ticket-{ticket.id}-{channel.id}.html"))
            embed = Embed(
                description=f"Ticket #{ticket.id} (Channel ID: {channel.id}) closed by `{ctx.author} ({ctx.author.id})`: {reason}.\n"
                            f"Opened By: `{member} ({ticket.user})`\n"
                            f"[Download Transcript]({_edit_msg.attachments[0].url})")
            await _edit_msg.edit(embed=embed)
        await asyncio.sleep(5)
        await self.bot.db.tickets.remove(ticket.id)
        await channel.delete()

    @slash.cog_subcommand(
        base="tickets",
        base_desc="Manage tickets.",
        name="create-panel",
        description="Recreate the ticket panel.",
        guild_ids=[ATLAS]
    )
    async def ticket_createpanel(self, ctx: SlashContext):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("Insufficient permissions.")
        channel = self.bot.get_channel(self.panel)
        if channel is None:
            return await ctx.send("The ticket channel does not exist.")
        embed = Embed(title="Tickets", description="Click the button below to open a ticket.")
        embed.add_field(
            name="Bug Reports", 
            value="If you're reporting a bug, please use this format in your ticket reason, it helps us better understand what is happening and it generally makes it a lot easier for us to help you/fix it.\n"
                  "Format:\n"
                  "• IGN,\n"
                  "• The server that this bug occurred in,\n"
                  "• Explaination of the bug."
        )
        await channel.send(embed=embed, 
            components=[
                ActionRow(
                    Button(
                        style=ButtonStyle.blue, 
                        label="Open Ticket", 
                        emoji="📩", 
                        custom_id="ticket-open"
                    )
                )
            ]
        )
        await ctx.send("Ticket panel created.")

def setup(bot):
    bot.add_cog(Tickets(bot))
