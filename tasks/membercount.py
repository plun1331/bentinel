import discord
from discord.ext import commands, tasks
from bot import Bot

class MemberCount(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: Bot = bot
        self.member_count = 888259843130024007
        self.booster_count = 888259895500103741
        self.update.start()

    @tasks.loop(minutes=10)
    async def update(self):
        guild = self.bot.get_guild(self.bot.guild_id)
        if guild is None:
            return
        member_count = self.bot.get_channel(self.member_count)
        booster_count = self.bot.get_channel(self.booster_count)
        if member_count is not None:
            await member_count.edit(name=f"✦ Members: {len(guild.members)}")
        if booster_count is not None:
            await booster_count.edit(name=f"✦ Boosters: {guild.premium_subscription_count}")

    @update.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(MemberCount(bot))