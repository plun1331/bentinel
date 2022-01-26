from typing import Union
import discord
from discord.ext import commands
from discord_slash import SlashContext
import traceback

from utils.paginator import TextPageSource
from utils.objects import AtlasException
from utils.utils import ExpiringCache
from utils.dpy import Embed
from bot import Bot
import io

CHANNEL = Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.CategoryChannel]

class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = self.bot.config['logs']['channel']
        self.yes = '<:bit_tick:831435958380658719>'
        self.no = '<:bit_cross:831435958406086666>'

    """
    Messages
    """
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild.id != self.bot.guild_id:
            return
        embed = Embed(description=f'Message deleted in {message.channel.mention} by {message.author.mention} (`{message.author} - {message.author.id}`)', 
                              color=discord.Color.blurple())
        if message.type != discord.MessageType.default:
            embed.description += ' [SYSTEM MESSAGE]'
            content = message.system_content
        else:
            content = message.content
        files = []
        if content:
            if len(content) > 1024:
                output = io.BytesIO()
                output.write(content.encode('utf-8'))
                output.seek(0)
                files = [discord.File(output, 'deleted-message.txt')]
            else:
                embed.add_field(name='Content', value=content)
        if message.attachments:
            v = ', '.join(f"[{a.filename}]({a.proxy_url})" for a in message.attachments)
            if v:
                embed.add_field(name='Attachments', value=v)
        embed.set_footer(text=f'Message ID: {message.id}')
        embed.set_author(name=message.guild.name, icon_url=message.guild.icon_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            if files:
                return await channel.send(embed=embed, files=files)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        content = ''
        for message in payload.cached_messages:
            content += f"[{message.author} ({message.author.id})] {message.content}\n"
        files = []
        if content:
            content = f"Some messages may be missing from this file.\n\n" + content
            output = io.BytesIO()
            output.write(content.encode('utf-8'))
            output.seek(0)
            files = [discord.File(output, 'bulk-delete.txt')]
        embed = Embed(description=f"{len(payload.message_ids)} messages were deleted in <#{payload.channel_id}>")
        guild = self.bot.get_guild(payload.guild_id)
        embed.set_author(name=guild.name, icon_url=guild.icon_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            if files:
                return await channel.send(embed=embed, files=files)
            await channel.send(embed=embed)
        
            
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild.id != self.bot.guild_id:
            return
        if not any([before.system_content != after.system_content, before.attachments != after.attachments]):
            return
        if before.author.id == self.bot.user.id:
            return
        embed = Embed(description=f'Message edited in {after.channel.mention} by {before.author.mention} (`{before.author} - {before.author.id}`)\n'
                                          f'[Jump to Message]({after.jump_url})', 
                              color=discord.Color.blurple())
        files = []
        if before.content != after.content and before.content and after.content:
            if len(before.content) > 1024:
                output = io.BytesIO()
                output.write(before.content.encode('utf-8'))
                output.seek(0)
                files.append(discord.File(output, 'before.txt'))
            if len(after.content) > 1024:
                output = io.BytesIO()
                output.write(after.content.encode('utf-8'))
                output.seek(0)
                files.append(discord.File(output, 'after.txt'))
            embed.add_field(name='Old Content', value=before.content  if len(before.content) <= 1024 else '[Attached as file before.txt]')
            embed.add_field(name='New Content', value=after.content if len(after.content) <= 1024 else '[Attached as file after.txt]')
        if before.attachments != after.attachments and before.attachments:
            embed.add_field(name='Old Attachments', value=', '.join(f"({a.filename})[{a.proxy_url}]" for a in before.attachments))
        embed.set_footer(text=f'Message ID: {before.id}')
        embed.set_author(name=before.guild.name, icon_url=before.guild.icon_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            if files:
                return await channel.send(embed=embed, files=files)
            await channel.send(embed=embed)

    """
    Roles
    """
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        if role.guild.id != self.bot.guild_id:
            return
        embed = Embed(description=f'Role {role.mention} created.', 
                              color=discord.Color.blurple())
        embed.add_field(name='Name', value=role.name)
        embed.add_field(name='Color', value=f"`{role.color}`")
        embed.add_field(name='Hoisted', value=self.yes if role.hoist else self.no)
        embed.add_field(name='Mentionable', value=self.yes if role.mentionable else self.no)
        if role.is_bot_managed() or role.is_integration():
            embed.add_field(name='Managed', value=f"This role is managed by an integration.")
        elif role.is_premium_subscriber():
            embed.add_field(name='Managed', value=f"This role is the guild's boost role.")
        embed.set_footer(text=f'Role ID: {role.id}')
        embed.set_author(name=role.guild.name, icon_url=role.guild.icon_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        if role.guild.id != self.bot.guild_id:
            return
        embed = Embed(description=f'Role @{role.name} deleted.', 
                              color=discord.Color.blurple())
        embed.add_field(name='Name', value=role.name)
        embed.add_field(name='Color', value=f"`{role.color}`")
        embed.add_field(name='Hoisted', value=self.yes if role.hoist else self.no)
        embed.add_field(name='Mentionable', value=self.yes if role.mentionable else self.no)
        embed.set_footer(text=f'Role ID: {role.id}')
        embed.set_author(name=role.guild.name, icon_url=role.guild.icon_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.guild.id != self.bot.guild_id:
            return
        if not any([before.name != after.name, before.color != after.color, before.hoist != after.hoist, before.mentionable != after.mentionable]):
            return
        embed = Embed(description=f'Role {after.mention} updated.', 
                              color=discord.Color.blurple())
        if before.name != after.name:
            embed.add_field(name='Name', value=f"`{before.name}` ➜ `{after.name}`")
        if before.color != after.color:
            embed.add_field(name='Color', value=f"`{before.color}` ➜ `{after.color}`")
        if before.hoist != after.hoist:
            embed.add_field(name='Hoisted', value=f"{self.yes if before.hoist else self.no} ➜ {self.yes if after.hoist else self.no}" )
        if before.mentionable != after.mentionable:
            embed.add_field(name='Mentionable', value=f"{self.yes if before.mentionable else self.no} ➜ {self.yes if after.mentionable else self.no}" )
        embed.set_footer(text=f'Role ID: {before.id}')
        embed.set_author(name=before.guild.name, icon_url=before.guild.icon_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)

    """
    Channels
    """
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: CHANNEL):
        if channel.guild.id != self.bot.guild_id:
            return
        if not isinstance(channel, discord.CategoryChannel):
            embed = Embed(description=f'Channel {channel.mention} created.', 
                                  color=discord.Color.blurple())
            embed.add_field(name='Name', value=channel.name)
            embed.add_field(name='Type', value=str(channel.type))
            embed.add_field(name='Category', value=str(channel.category))
            embed.set_footer(text=f'Channel ID: {channel.id}')
            embed.set_author(name=channel.guild.name, icon_url=channel.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        else:
            embed = Embed(description=f'Category {channel.name} created.', 
                                  color=discord.Color.blurple())
            embed.add_field(name='Name', value=channel.name)
            embed.add_field(name='Type', value="Category")
            embed.set_footer(text=f'Channel ID: {channel.id}')
            embed.set_author(name=channel.guild.name, icon_url=channel.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: CHANNEL):
        if channel.guild.id != self.bot.guild_id:
            return
        if isinstance(channel, discord.TextChannel):
            embed = Embed(description=f'Channel #{channel.name} deleted.',
                                    color=discord.Color.blurple())
            embed.add_field(name='Name', value=channel.name)
            embed.add_field(name='Type', value=str(channel.type))
            embed.add_field(name='Topic', value=channel.topic)
            embed.add_field(name='NSFW', value=self.yes if channel.is_nsfw() else self.no)
            embed.add_field(name='Slowmode', value=f"{channel.slowmode_delay} seconds")
            embed.add_field(name='Category', value=str(channel.category))
            embed.set_footer(text=f'Channel ID: {channel.id}')
            embed.set_author(name=channel.guild.name, icon_url=channel.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        elif isinstance(channel, discord.VoiceChannel):
            embed = Embed(description=f'Channel #{channel.name} deleted.',
                                    color=discord.Color.blurple())
            embed.add_field(name='Name', value=channel.name)
            embed.add_field(name='Type', value="Voice")
            embed.add_field(name='Bitrate', value=channel.bitrate)
            embed.add_field(name='User Limit', value=channel.user_limit)
            embed.add_field(name='Region', value=' '.join([i.capitalize() for i in str(channel.rtc_region).split('_')]) if channel.rtc_region else 'Automatic')
            embed.add_field(name='Category', value=str(channel.category))
            embed.set_footer(text=f'Channel ID: {channel.id}')
            embed.set_author(name=channel.guild.name, icon_url=channel.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        elif isinstance(channel, discord.CategoryChannel):
            embed = Embed(description=f'Category {channel.name} deleted.',
                                    color=discord.Color.blurple())
            embed.add_field(name='Name', value=channel.name)
            embed.add_field(name='Type', value="Category")
            embed.set_footer(text=f'Channel ID: {channel.id}')
            embed.set_author(name=channel.guild.name, icon_url=channel.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        elif isinstance(channel, discord.StageChannel):
            embed = Embed(description=f'Channel #{channel.name} deleted.',
                                    color=discord.Color.blurple())
            embed.add_field(name='Name', value=channel.name)
            embed.add_field(name='Type', value="Stage")
            embed.add_field(name='Bitrate', value=channel.bitrate)
            embed.add_field(name='User Limit', value=channel.user_limit)
            embed.add_field(name='Region', value=' '.join([i.capitalize() for i in str(channel.rtc_region).split('_')]) if channel.rtc_region else 'Automatic')
            embed.add_field(name='Category', value=str(channel.category))
            embed.set_footer(text=f'Channel ID: {channel.id}')
            embed.set_author(name=channel.guild.name, icon_url=channel.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: CHANNEL, after: CHANNEL):
        if before.guild.id != self.bot.guild_id:
            return
        if isinstance(after, discord.TextChannel):
            if not any([before.name != after.name, before.topic != after.topic, before.is_nsfw() != after.is_nsfw(), before.slowmode_delay != after.slowmode_delay]):
                return
            embed = Embed(description=f'Channel {after.mention} updated.',
                                    color=discord.Color.blurple())
            if before.name != after.name:
                embed.add_field(name='Name', value=f'{before.name} ➜ {after.name}')
            if before.type != after.type:
                embed.add_field(name='Type', value=f'{before.type} ➜ {after.type}')
            if before.topic != after.topic:
                embed.add_field(name='Topic', value=f'{before.topic} ➜ {after.topic}')
            if before.is_nsfw() != after.is_nsfw():
                embed.add_field(name='NSFW', value=f'{self.yes if before.is_nsfw() else self.no} ➜ {self.yes if after.is_nsfw() else self.no}')
            if before.slowmode_delay != after.slowmode_delay:
                embed.add_field(name='Slowmode', value=f"{before.slowmode_delay} seconds ➜ {after.slowmode_delay} seconds")
            embed.set_footer(text=f'Channel ID: {after.id}')
            embed.set_author(name=after.guild.name, icon_url=after.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        elif isinstance(after, discord.VoiceChannel):
            if not any([before.name != after.name, before.bitrate != after.bitrate, before.user_limit != after.user_limit, before.rtc_region != after.rtc_region]):
                return
            embed = Embed(description=f'Channel {after.mention} updated.',
                                    color=discord.Color.blurple())
            if before.name != after.name:
                embed.add_field(name='Name', value=f'{before.name} ➜ {after.name}')
            embed.add_field(name='Type', value=f"Voice")
            if before.bitrate != after.bitrate:
                embed.add_field(name='Bitrate', value=f'{before.bitrate} ➜ {after.bitrate}')
            if before.user_limit != after.user_limit:
                embed.add_field(name='User Limit', value=f'{before.user_limit} ➜ {after.user_limit}')
            if before.rtc_region != after.rtc_region:
                embed.add_field(name='Region', value=f'{str(before.rtc_region)} ➜ {str(after.rtc_region)}')
            embed.set_footer(text=f'Channel ID: {after.id}')
            embed.set_author(name=after.guild.name, icon_url=after.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        elif isinstance(after, discord.CategoryChannel):
            if before.name == after.name:
                return
            embed = Embed(description=f'Category {after.mention} updated.',
                                    color=discord.Color.blurple())
            embed.add_field(name='Name', value=f'{before.name} ➜ {after.name}')
            embed.add_field(name='Type', value=f"Category")
            embed.set_footer(text=f'Channel ID: {after.id}')
            embed.set_author(name=after.guild.name, icon_url=after.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)
        elif isinstance(after, discord.StageChannel):
            if not any([before.name != after.name, before.bitrate != after.bitrate, before.user_limit != after.user_limit, before.rtc_region != after.rtc_region, before.category != after.category]):
                return
            embed = Embed(description=f'Channel {after.mention} updated.',
                                    color=discord.Color.blurple())
            if before.name != after.name:
                embed.add_field(name='Name', value=f'{before.name} ➜ {after.name}')
            embed.add_field(name='Type', value=f"Stage")
            if before.bitrate != after.bitrate:
                embed.add_field(name='Bitrate', value=f'{before.bitrate} ➜ {after.bitrate}')
            if before.user_limit != after.user_limit:
                embed.add_field(name='User Limit', value=f'{before.user_limit} ➜ {after.user_limit}')
            if before.rtc_region != after.rtc_region:
                embed.add_field(name='Region', value=f'{str(before.rtc_region)} ➜ {str(after.rtc_region)}')
            if before.category != after.category:
                embed.add_field(name='Category', value=f'{before.category} ➜ {after.category}')
            embed.set_footer(text=f'Channel ID: {after.id}')
            embed.set_author(name=after.guild.name, icon_url=after.guild.icon_url)
            channel = self.bot.get_channel(self.channel)
            if channel is not None:
                await channel.send(embed=embed)

    """
    Users
    """
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != self.bot.guild_id:
            return
        embed = Embed(description=f'{member.mention} joined the server. (`{member} - {member.id}`)',
                                color=discord.Color.blurple())
        embed.set_footer(text=f'User ID: {member.id}')
        embed.set_author(name=member.guild.name, icon_url=member.guild.icon_url)
        embed.set_thumbnail(url=member.avatar_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)
        
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id != self.bot.guild_id:
            return
        embed = Embed(description=f'{member.mention} left the server. (`{member} - {member.id}`)',
                                color=discord.Color.blurple())
        embed.set_author(name=member.guild.name, icon_url=member.guild.icon_url)
        embed.set_thumbnail(url=member.avatar_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild.id != self.bot.guild_id:
            return
        if not any([before.name != after.name, before.nick != after.nick, before.discriminator != after.discriminator, before.roles != after.roles]):
            return
        embed = Embed(description=f'{after.mention} updated. (`{after} - {after.id}`)',
                                color=discord.Color.blurple())
        if before.name != after.name:
            embed.add_field(name='Name', value=f'{before.name} ➜ {after.name}')
        if before.nick != after.nick:
            embed.add_field(name='Nick', value=f'{before.nick} ➜ {after.nick}')
        if before.discriminator != after.discriminator:
            embed.add_field(name='Discriminator', value=f'{before.discriminator} ➜ {after.discriminator}')
        if before.roles != after.roles:
            removed = [role for role in before.roles if role not in after.roles]
            added = [role for role in after.roles if role not in before.roles]
            if removed:
                embed.add_field(name='Removed Roles', value=', '.join([role.name for role in removed]))
            if added:
                embed.add_field(name='Added Roles', value=', '.join([role.name for role in added]))
        embed.set_footer(text=f'User ID: {after.id}')
        embed.set_author(name=after.guild.name, icon_url=after.guild.icon_url)
        embed.set_thumbnail(url=after.avatar_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if guild.id != self.bot.guild_id:
            return
        embed = Embed(description=f'{user.mention} was banned. (`{user} - {user.id}`)',
                                color=discord.Color.blurple())
        embed.set_author(name=guild.name, icon_url=guild.icon_url)
        embed.set_thumbnail(url=user.avatar_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        if guild.id != self.bot.guild_id:
            return
        embed = Embed(description=f'{user.mention} was unbanned. (`{user} - {user.id}`)',
                                color=discord.Color.blurple())
        embed.set_author(name=guild.name, icon_url=guild.icon_url)
        embed.set_thumbnail(url=user.avatar_url)
        channel = self.bot.get_channel(self.channel)
        if channel is not None:
            await channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Logs(bot))
