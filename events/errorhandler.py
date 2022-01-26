import discord
from discord.ext import commands
from discord_slash import SlashContext
import traceback

from utils.paginator import TextPageSource
from utils.objects import AtlasException
from bot import Bot

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.channel: int = self.bot.config['bot']['exceptions']

    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx: SlashContext, error):
        try:
            if isinstance(error, AtlasException):
                embed = discord.Embed(description=str(error), 
                                      color=discord.Color.red())
                return await ctx.send(embed=embed, hidden=True)
            embed = discord.Embed(description=f"An unhandled exception has occurred. Please notify an administrator.\n"
                                              f"Error Code: `{error.__class__.__name__.upper()}`", 
                                  color=discord.Color.red())
            await ctx.send(embed=embed, hidden=True)
        except discord.NotFound:
            pass
        tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        pages = TextPageSource(tb, prefix='```py', suffix='```', max_size=1000).pages
        msg = f"Command: `{ctx.command}`\nInvoker: `{ctx.author} ({ctx.author.id})`\nArguments: {ctx.args}\n{pages[0]}"
        await self.bot.get_channel(self.channel).send(msg)
        for page in pages[1:]:
            await self.bot.get_channel(self.channel).send(page)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return
        tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        pages = TextPageSource(tb, prefix='```py', suffix='```', max_size=1000).pages
        msg = f"Command: `{ctx.command}`\nInvoker: `{ctx.author} ({ctx.author.id})`\nArguments: {ctx.args}\n{pages[0]}"
        await self.bot.get_channel(self.channel).send(msg)
        for page in pages[1:]:
            await self.bot.get_channel(self.channel).send(page)

def setup(bot):
    bot.add_cog(ErrorHandler(bot))
