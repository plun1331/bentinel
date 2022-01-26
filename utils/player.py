import asyncio
from async_timeout import timeout
import discord
from utils.ytdl import YTDLSource




class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_ctx', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'loop', 'loop_queue', '_skip', '_clear', 'voted', '_passed_songs')

    def __init__(self, ctx, cog):
        self._ctx = ctx
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = self.bot.get_channel(ctx.channel_id)
        self._cog = ctx.cog or cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = 1
        self.current = None
        self.loop = False
        self.loop_queue = False
        self._skip = False
        self._clear = False
        self.voted = []
        self._passed_songs = 0

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()
        
        try:
            while not self.bot.is_closed():
                self.next.clear()
                self.voted = []

                if not self.loop or self.current is None or self._skip or self._clear:
                    try:
                        # Wait for the next song. If we timeout cancel the player and disconnect...
                        async with timeout(300):  # 5 minutes...
                            source = await self.queue.get()
                    except asyncio.TimeoutError:
                        return self.destroy(self._guild)
                else:
                    source = self.current
                    source = await YTDLSource.create_source(self._ctx, source.author, source.web_url, loop=self.bot.loop)

                self._skip = False
                self._clear = False

                if not isinstance(source, YTDLSource):
                    # Source was probably a stream (not downloaded)
                    # So we should regather to prevent stream expiration
                    try:
                        source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                    except Exception as e:
                        await self._channel.send(f'There was an error processing your song.\n'
                                                f'```css\n[{e}]\n```')
                        self._skip = True
                        continue

                source.volume = self.volume
                self.current = source

                try:
                    self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
                except AttributeError:
                    return self.destroy(self._guild)
                try:
                    self.np = await self._channel.send(embed=self.current.create_embed())
                except discord.HTTPException:
                    pass
                await self.next.wait()

                try:
                    channel = self._guild.me.voice.channel
                    if len([m for m in channel.members if not m.bot]) == 0:
                        self._passed_songs += 1
                    else:
                        self._passed_songs = 0
                except AttributeError:
                    return self.destroy(self._guild)

                if self._passed_songs >= 5:
                    return self.destroy(self._guild)

                # Make sure the FFmpeg process is cleaned up.
                source.cleanup()
                if not self._clear:
                    if not self.loop or self._skip:
                        self.current = None

                    if self.loop_queue:
                        source = await YTDLSource.create_source(self._ctx, source.requester, source.web_url, loop=self.bot.loop)
                        self.queue.put_nowait(source)    
                else:
                    self.current = None

                try:
                    # We are no longer playing this song...
                    await self.np.delete()
                except (discord.HTTPException, AttributeError):
                    pass
        except:
            pass
        self.destroy(self._guild)

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))
