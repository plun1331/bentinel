import discord
from discord.ext import commands, tasks
from bot import Bot

class MemberCount(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: Bot = bot
        self.check.start()

    @tasks.loop(seconds=5)
    async def check(self):
        await self.bot.db.giveaway.check()

    @check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(MemberCount(bot))