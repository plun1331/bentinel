from utils.database import Database
from discord.ext import commands
import discord
import log
from discord_slash import SlashCommand as SlashClient
import json

with open('config.json', 'r') as f:
    config = json.load(f)

GUILDS = config['commands']['guilds']
ATLAS = config['bot']['guild']

class Context(commands.Context):
    def send(self, *args, **kwargs):
        kwargs['allowed_mentions'] = discord.AllowedMentions(replied_user=False)
        return self.reply(*args, **kwargs)

class Bot(commands.Bot):
    def __init__(self, **options):
        options['intents'] = discord.Intents.default()
        options['intents'].members = True
        options['command_prefix'] = '/'
        options['help_command'] = None
        options['status'] = discord.Status.online
        options['activity'] = discord.Game(name='on mc.the-atlas.net')
        super().__init__(**options)
        self.logger = log.Logger()
        self.database = None
        with open('config.json', 'r') as f:
            config = json.load(f)
        self.config = config
        # config loaded from config.json
        self.limbo_role = config['moderation']['limbo']
        self.mute_role = config['moderation']['mute']
        self.application_channel = config['applications']['channel']
        self.suggestion_channel = config['suggestions']['channel']
        self.sugg_deny_channel = config['suggestions']['deny_channel']
        self.sugg_accept_channel = config['suggestions']['accept_channel']
        self.guild_id = config['bot']['guild']
        self.db = Database(self)
        self.slash = SlashClient(self, delete_from_unused_guilds=True, sync_commands=False)
        self.owner_id = 830344767027675166

    @property
    def _config(self):
        return self.config

    async def get_or_fetch_user(self, user):
        try:
            return self.get_user(user) or await self.fetch_user(user)
        except discord.HTTPException:
            return None
    
    async def sync_all_commands(self) -> None:
        self.logger.info('Syncing commands...')
        await self.slash.sync_all_commands()
        self.logger.success('Commands synced!')

    async def sync_commands(self) -> None:
        await self.sync_all_commands()

    async def on_connect(self):
        self.logger.info('Connected to Discord.')

    async def on_disconnect(self):
        self.logger.warn('Disconnected from Discord.')

    async def on_resumed(self):
        self.logger.info('Connection resumed.')

    async def on_ready(self):
        self.logger.success(f'Bot is ready!')
        self.logger.success(f'Logged in as {self.user} with ID {self.user.id}')

    async def on_message(self, message):
        if not await self.is_owner(message.author):
            return
        await self.process_commands(message)

    async def close(self) -> None:
        self.logger.warn('Closing the bot...')
        for ext in dict(self.extensions).keys():
            self.unload_extension(ext)
        await super().close()

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=cls or Context)
