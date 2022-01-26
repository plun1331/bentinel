import discord
from discord.ext import commands
from discord_slash import ComponentContext
from discord_slash.utils.manage_components import create_button as Button, create_actionrow as ActionRow
from discord_slash.model import ButtonStyle
import traceback

from utils.paginator import TextPageSource
from utils.objects import AtlasException
from utils.utils import ExpiringCache
from bot import Bot

script = """While I'm currently dying of Twitter, my last words to you is today's sponsor, Swofty hosting! 

Swofty hosting is Minecraft Server hosting for the modern generation. They have over 2 terabytes of ram to host your server fast and efficiently. 

With a convient menu to use and useful features such as automatic mod and plugin installation, Swofty Hosting is usable by everyone! 

To get started, go to the Atlas Development Discord (https://discord.gg/En2CMEuvR5) and look in #announcements to get started on making an account! And thank you to Swofty for giving me his money.

*© 2021 Swofty Hosting:tm:*
"""

class Autoreplies(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.cd = ExpiringCache(seconds=60)

    @commands.Cog.listener('on_message')
    async def swofty(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.lower() == 'swofty hosting':
            if message.channel.id in self.cd.items:
                return
            self.cd.append(message.channel.id)
            await message.reply(script)
            
    @commands.Cog.listener('on_message')
    async def sbx(self, message: discord.Message):
        if message.author.bot:
            return
        c = message.content.lower()
        if (any([m in c for m in ('join', 'down', 'closed', 'offline', 'why', 'where')]) and 'server' in c) or (('cant' in c or "can't" in c) and 'join' in c):
            delete_button = Button(emoji="🗑️", style=ButtonStyle.red, disabled=False, custom_id=f"delete-autoresponse.{message.author.id}")
            #await message.reply(f"https://discord.com/channels/830345347867476000/849739331278733332/929811299184046140",
            await message.reply(f"Please check <#930096309589925948> for news on the server's status.",
                                components=[ActionRow(delete_button)])
            
        
    @commands.Cog.listener('on_component')
    async def delete_message(self, ctx: ComponentContext):
        if ctx.custom_id.startswith('delete-autoresponse'):
            if ctx.custom_id.endswith(str(ctx.author.id)) or ctx.author.guild_permissions.manage_messages:
                await ctx.origin_message.delete()

def setup(bot):
    bot.add_cog(Autoreplies(bot))
