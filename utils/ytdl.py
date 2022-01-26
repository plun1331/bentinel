import asyncio
import discord
from discord.ext import commands
from functools import partial
import youtube_dl
from youtube_dl import YoutubeDL
from utils.dpy import Embed

youtube_dl.utils.bug_reports_message = lambda: ''

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostats -loglevel 0',
    'options': '-vn',
}

ytdl = YoutubeDL(YTDL_OPTIONS)


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.web_url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)
        
    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} days'.format(days))
        if hours > 0:
            duration.append('{} hours'.format(hours))
        if minutes > 0:
            duration.append('{} minutes'.format(minutes))
        if seconds > 0:
            duration.append('{} seconds'.format(seconds))

        return ', '.join(duration)

    @classmethod
    async def create_source(cls, ctx, requester, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)
        
        if 'entries' in data and len(data['entries']) > 1:
            _ret = []
            # sort through playlist
            for vid in data['entries']:
                if download:
                    source = ytdl.prepare_filename(vid)
                    _ret.append(cls(discord.FFmpegPCMAudio(source, **FFMPEG_OPTIONS), data=data, requester=requester))
                else:
                    _ret.append({'webpage_url': vid['webpage_url'], 'requester': requester, 'title': vid['title']})
            return _ret
        else:
            if 'entries' in data:
                data = data['entries'][0]
            if download:
                source = ytdl.prepare_filename(data)
            else:
                return {'webpage_url': data['webpage_url'], 'requester': requester, 'title': data['title']}

            return cls(discord.FFmpegPCMAudio(source, **FFMPEG_OPTIONS), data=data, requester=requester)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), data=data, requester=requester)

    def create_embed(self):
        embed = Embed(title='Now playing',
                      description='```css\n{0.title}\n```'.format(self))
        embed.add_field(name='Duration', value=self.duration, inline=True)
        embed.add_field(name='Requested by', value=self.requester.mention, inline=True)
        embed.add_field(name='Uploader', value='[{0.uploader}]({0.uploader_url})'.format(self), inline=True)
        embed.add_field(name='URL', value='[Click]({0.web_url})'.format(self), inline=True)
        embed.set_thumbnail(url=self.thumbnail)

        return embed
