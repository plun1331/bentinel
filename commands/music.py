from typing import Dict
import discord
from discord.ext import commands

import asyncio
import itertools
import sys
import traceback
from async_timeout import timeout
from utils.ytdl import YTDLSource, InvalidVoiceChannel, VoiceConnectionError
from utils.player import MusicPlayer

from discord_slash import SlashContext
from discord_slash import cog_ext as slash
from discord_slash.utils.manage_commands import create_option as Option
from discord_slash.utils.manage_commands import create_choice as Choice
from discord_slash.utils.manage_components import create_button as Button
from discord_slash.utils.manage_components import create_select as Select
from discord_slash.utils.manage_components import create_select_option as SelectOption
from discord_slash.utils.manage_components import create_actionrow as ActionRow
from discord_slash.model import ButtonStyle, SlashCommandOptionType as OptionType
from utils.paginator import TextPageSource
from async_timeout import timeout
from bot import Bot, GUILDS


class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot: Bot = bot
        self.players: Dict[int, MusicPlayer] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, _, after):
        if member != self.bot.user:
            return
        if after is None:
            await self.cleanup(member.guild)
        if not after.deaf:
            try:
                await member.edit(deafen=True)
            except discord.HTTPException:
                pass
        if after.mute:
            try:
                await member.edit(mute=False)
            except discord.HTTPException:
                pass
            
        
    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    async def cog_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.reply('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            return await ctx.reply("You're not in a voice channel.")
        elif isinstance(error, VoiceConnectionError):
            return await ctx.reply('Failed to connect. Please make sure I have the proper permissions.')

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx, self)
            self.players[ctx.guild.id] = player

        return player

    async def has_permissions(self, ctx):
        if ctx.guild.me.voice is None:
            return True
        if (len([m for m in ctx.guild.me.voice.channel.members if not m.bot]) <= 1):
            return True
        if ctx.author.guild_permissions.manage_channels:
            return True
        if await self.bot.is_owner(ctx.author):
            return True
        

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='connect', 
        description="Summons the bot to a voice channel.",
        guild_ids=GUILDS
    )
    async def connect_(self, ctx):
        vc = ctx.voice_client
        state = ctx.guild.me.voice
        if ctx.author.voice is None:
            raise InvalidVoiceChannel
        
        if vc:
            if state is None:
                return await ctx.reply("I'm being used in a different channel right now.")
            elif state.channel == ctx.author.voice.channel:
                return await ctx.reply("I'm already in your voice channel!")
            elif [m for m in state.channel.members if not m.bot]:
                if not await self.has_permissions(ctx):
                    return await ctx.reply("I'm being used in a different channel right now.")

        channel = ctx.author.voice.channel
        await ctx.defer()
        if vc:
            try:
                async with timeout(10):
                    await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError
        else:
            try:
                async with timeout(10):
                    await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError

        await ctx.send(f'Connected to {channel.mention}.')

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='play', 
        description="Searches for a song and adds it to the queue.",
        options=[
            Option(
                name='query',
                option_type=OptionType.STRING,
                description="The song to search for.",
                required=True
            )
        ],
        guild_ids=GUILDS
    )
    async def play_(self, ctx, *, query: str):
        vc = ctx.voice_client
        state = ctx.guild.me.voice
        if not vc or not state:
            await ctx.invoke(self.connect_)
            if ctx.guild.get_member(self.bot.user.id).voice is None:
                return
        else:
            if not ctx.guild.me.voice.channel == ctx.author.voice.channel:
                return await ctx.reply("You must be in the same voice channel as me to do that.")
            await ctx.defer()

        player = self.get_player(ctx)
        try:
            source = await YTDLSource.create_source(ctx, ctx.author, query, loop=self.bot.loop)
        except Exception as e:
            return await ctx.reply(f'An error occurred while processing this request: {e}')
        if isinstance(source, list):
            for src in source:
                await player.queue.put(src)
            await ctx.reply(f'{len(source)} videos have been added to the queue.')
        else:
            await player.queue.put(source)
            await ctx.reply(f'**{source.get("title")}** has been added to the queue.')

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='pause',
        description="Pauses the player.",
        guild_ids=GUILDS
    )
    async def pause_(self, ctx):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_playing() or not state:
            return await ctx.reply('I am not currently playing anything!')
        elif not ctx.guild.me.voice.channel == ctx.author.voice.channel:
            return await ctx.reply("You must be in the same voice channel as me to do that.")
        elif vc.is_paused():
            return await ctx.reply(f'The player is already paused. Use `resume` to unpause it.')

        if not await self.has_permissions(ctx):
            return await ctx.reply('You do not have permission to do this.')

        vc.pause()
        await ctx.reply(f'**`{ctx.author}`**: Paused the player.')

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='resume',
        description="Resumes music playback.",
        guild_ids=GUILDS
    )
    async def resume_(self, ctx):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently playing anything!')
        elif not ctx.guild.me.voice.channel == ctx.author.voice.channel:
            return await ctx.reply("You must be in the same voice channel as me to do that.")
        elif not vc.is_paused():
            return await ctx.reply(f'The player is not paused.')

        vc.resume()
        await ctx.reply(f'**`{ctx.author}`**: Unpaused the player.')

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='skip',
        description="Skips the current song.",
        guild_ids=GUILDS
    )
    async def skip_(self, ctx):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently connected to voice!')

        if not ctx.guild.me.voice.channel == ctx.author.voice.channel:
            return await ctx.reply("You must be in the same voice channel as me to do that.")

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return await ctx.reply('I am not currently playing anything!')



        player = self.get_player(ctx)
        if ctx.author.id == getattr(player.current, 'requester', player.current['requester']).id:
            player._skip = True
            vc.stop()
            await ctx.reply(f'**`{ctx.author}`**: Skipped the song.')
        elif await self.has_permissions(ctx):
            player._skip = True
            vc.stop()
            await ctx.reply(f'**`{ctx.author}`**: Skipped the song.')
        else:
            if ctx.author.id in player.voted:
                return await ctx.reply('You have already voted to skip this song.')
            player.voted.append(ctx.author.id)
            total_votes = len(player.voted)
            vc_members = len([m for m in ctx.author.voice.channel.members if not m.bot])
            needed = vc_members // 2
            if total_votes >= needed:
                player._skip = True
                vc.stop()
                await ctx.reply(f'**`{ctx.author}`**: Voted to skip (**{total_votes}/{needed}**)\nSkipped the song.')
            else:
                await ctx.reply(f'**`{ctx.author}`**: Voted to skip (**{total_votes}/{needed}**)')

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='queue',
        description="Displays the currently queued songs.",
        options=[
            Option(
                name='page',
                option_type=OptionType.INTEGER,
                description="The page of the queue to display.",
                required=False
            )
        ],
        guild_ids=GUILDS
    )
    async def queue_info(self, ctx, *, page: int = 1):
        if page < 1:
            page = 1
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently connected to voice!')

        player = self.get_player(ctx)
        if player.queue.empty():
            fmt = ['Empty queue.']
        else:
            fmt = []
            for index, song in enumerate(player.queue._queue):
                fmt.append(f"#{index + 1}: [`{song['title']}`]({song['webpage_url']})")

        fmt = '\n'.join(fmt)
        embeds = []
        for _page in TextPageSource(fmt, prefix='', suffix='', max_size=1024).pages:
            embed = discord.Embed(title='Queue',
                                  description=f'Now Playing: {f"[`{player.current.title}`]({player.current.web_url})" if player.current else "Nothing!"}',
                                  color=discord.Color.blurple())
            embed.add_field(name='​', value=_page)
            embeds.append(embed)
        try:
            embed = embeds[page - 1]
        except IndexError:
            embed = embeds[-1]
        embed.set_footer(text=f'Page {page if page <= len(embeds) else len(embeds)}/{len(embeds)}')
        await ctx.reply(embed=embed)

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='remove',
        description="Removes a song from the queue by queue position.",
        options=[
            Option(
                name='index',
                option_type=OptionType.INTEGER,
                description="The index of the song to remove.",
                required=True
            )
        ],
        guild_ids=GUILDS
    )
    async def remove_(self, ctx, index: str):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently connected to voice!')

        player = self.get_player(ctx)

        if not ctx.guild.me.voice.channel == ctx.author.voice.channel:
            return await ctx.reply("You must be in the same voice channel as me to do that.")

        if player.queue.empty():
            await ctx.reply('Queue is empty!')
        else:
            try:
                res = player.queue._queue[index-1]
                if ctx.author.id != getattr(res, 'requester', res['requester']).id:
                    if not await self.has_permissions(ctx):
                        return await ctx.reply(f'You do not have permission to do this.')
            except IndexError:
                return await ctx.reply(f"Please provide a number between 1 and {len(player.queue._queue)}")
            del player.queue._queue[index-1]
            if res is None:
                await ctx.reply("There isn't that many songs in the queue.")
            else:
                await ctx.reply(f'**`{ctx.author}`**: Removed **`{res.get("title")}`** from the queue.')

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='nowplaying',
        description="Displays the currently playing song.",
        guild_ids=GUILDS
    )
    async def now_playing_(self, ctx):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently connected to voice!')

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.reply('I am not currently playing anything!')

        await ctx.reply(embed=player.current.create_embed())

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='loop',
        description="Toggles looping.",
        options=[
            Option(
                name='loop',
                option_type=OptionType.INTEGER,
                description="The type of loop to switch to.",
                required=True,
                choices=[
                    Choice(
                        value=0,
                        name="Disable"
                    ),
                    Choice(
                        value=1,
                        name="Current"
                    ),
                    Choice(
                        value=2,
                        name="Queue"
                    )
                ]
            )
        ],
        guild_ids=GUILDS
    )
    async def loop_(self, ctx, loop: int):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently connected to voice!')

        if not ctx.guild.me.voice.channel == ctx.author.voice.channel:
            return await ctx.reply("You must be in the same voice channel as me to do that.")

        if not await self.has_permissions(ctx):
            return await ctx.reply(f'You do not have permission to do this.')

        player = self.get_player(ctx)

        ltype = loop

        if ltype == 2:
            player.loop = False
            player.loop_queue = True
            return await ctx.reply(f"Now looping the queue.")
        elif ltype == 0:
            player.loop_queue = False
            return await ctx.reply(f"No longer looping anything.")
        else:
            player.loop = True
            return await ctx.reply(f"Now looping the current song.")

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='clear',
        description="Clears the queue.",
        guild_ids=GUILDS
    )
    async def clear_(self, ctx):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently connected to voice!')

        if not ctx.guild.me.voice.channel == ctx.author.voice.channel:
            return await ctx.reply("You must be in the same voice channel as me to do that.")

        if not await self.has_permissions(ctx):
            return await ctx.reply(f'You do not have permission to do this.')

        player = self.get_player(ctx)

        if not player.queue.empty():
            player.queue._queue.clear()
        player._clear = True
        vc.stop()
        await ctx.reply(f"Cleared the queue.")

    @slash.cog_subcommand(
        base='music',
        base_desc="Music commands.",
        name='stop',
        description="Stops the player and disconnects the bot.",
        guild_ids=GUILDS
    )
    async def stop_(self, ctx):
        vc = ctx.voice_client
        state = ctx.guild.me.voice

        if not vc or not vc.is_connected() or not state:
            return await ctx.reply('I am not currently playing anything!')

        if not ctx.guild.me.voice.channel == ctx.author.voice.channel:
            return await ctx.reply("You must be in the same voice channel as me to do that.")

        if not await self.has_permissions(ctx):
            return await ctx.reply(f'You do not have permission to do this.')

        await self.cleanup(ctx.guild)
        await ctx.reply('Goodbye!')

def setup(bot):
    bot.add_cog(Music(bot))
