import logging
import os, sys
import discord
from discord.ext import commands
from dotenv import load_dotenv
import log
from bot import Bot
import configparser

def blurple():
    return discord.Color(0x5865F2)

discord.Color.blurple = blurple

load_dotenv()

bot = Bot()

@bot.command()
async def say(ctx, *, message):
    await ctx.message.delete(delay=0.01)
    if ctx.message.reference:
        return await ctx.channel.send(message, reference=ctx.message.reference)
    await ctx.channel.send(message)

bot.logger.info('Bot class initialized.')

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.WARNING)
formatter = logging.Formatter(f'{log.TextFormat.yellow}[%(levelname)s: %(name)s] {log.TextFormat.white}%(message)s{log.TextFormat.reset}')
handler.setFormatter(formatter)
logger.addHandler(handler)

token = os.getenv('TOKEN')


bot.logger.info('Loading extensions...')
loaded = 0
failed = 0
exts = (
    'commands',
    'events',
    'tasks'
)
for _dir in exts:
    for file in os.listdir(_dir):
        if not file.endswith('.py'):
            continue
        try:
            bot.load_extension(f'{_dir}.{file[:-3]}')
            bot.logger.debug(f'Extension {file[:-3]} loaded.')
            loaded += 1
        except (commands.ExtensionFailed, commands.NoEntryPointError) as e:
            bot.logger.error(f'Failed to load extension {file[:-3]}: {e}')
            failed += 1
try:
    bot.load_extension(f'jishaku')
    bot.logger.debug(f'Extension jishaku loaded.')
    loaded += 1
except (commands.ExtensionFailed, commands.NoEntryPointError) as e:
    bot.logger.error(f'Failed to load extension jishaku: {e}')
    failed += 1
if failed:
    func = bot.logger.warn
else:
    func = bot.logger.success
func(f'{loaded} extensions were loaded. {failed} failed.')

bot.logger.info('Logging in using static token...')
try:
    bot.run(token)
except (discord.LoginFailure, discord.HTTPException) as e:
    bot.logger.emergency(f"Failed to login: {e}")
    sys.exit(1)
