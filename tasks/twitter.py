import discord
from discord.ext import commands, tasks
from bot import Bot
from utils.utils import Utils
from datetime import datetime
import os

class Twitter(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: Bot = bot
        self.channel = 849728579897786418
        self.token = os.getenv('TWITTER_BEARER_TOKEN')
        self.last_checked = datetime.utcnow()
        self.twitter.start()
        
    # allows easier access to bot owner for the future when following multiple accounts
    # and updating via command
    @property
    def twitter_allowed_accounts(self) -> int:
        return self.bot.owner_id
    
    @twitter_allowed_accounts.setter
    def twitter_allowed_accounts(self, value):
        self.bot.owner_id = value

    @tasks.loop(seconds=60)
    async def twitter(self):
        channel = self.bot.get_channel(self.channel)
        if channel is None:
            return
        tweets = []
        user_info = (await Utils.getTwitterUser("AtlasMCOfficial", self.token))['data'][0]
        user_id = user_info['id']
        posts = await Utils.getTwitterPosts(user_id, self.token)
        for post in posts['data']:
            created_at = post['created_at']
            if created_at.endswith('Z'):
                created_at = created_at[:-1]
            created_at = datetime.fromisoformat(created_at)
            if created_at > self.last_checked:
                tweets.append(f"https://twitter.com/AtlasMCOfficial/status/{post['id']}")
        if tweets:
            await channel.send(f"New tweet{'s' if len(tweets) > 1 else ''} from @AtlasMCOfficial:\n" + '\n'.join(tweets))
        self.last_checked = datetime.utcnow()
        

    @twitter.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(Twitter(bot))
