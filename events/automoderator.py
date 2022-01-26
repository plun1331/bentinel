from typing import List
import discord
from discord.ext import commands
from utils.objects import ModAction
import time
from utils.dpy import Embed
from utils.utils import ExpiringCache, Utils
from bot import Bot

class Automoderator(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        with open('data/banned-words.txt', 'r') as f:
            self.banned_words: List[str] = [w.strip() for w in f.read().splitlines()]
        with open('data/illegal-words.txt', 'r') as f:
            self.illegal_words: List[str] = [w.strip() for w in f.read().splitlines()]
        self.warning_threshold = {
            3: (1, 3600),
            6: (1, 172800),
            9: (3, 2592000),
        }
        self.action_types = {
            4: "LIMBO",
            3: "BAN",
            2: "KICK",
            1: "MUTE",
            0: "WARNING"
        }
        self.cons = ExpiringCache(seconds=600)
        self.replace = {
            '0': 'o',
            '!': 'i',
            '$': 's',
            '@': 'a',
            '|': 'l',
            'ö': 'o',
        }

    async def warn(self, member: discord.Member):
        reason = "Use of a blacklisted word."
        await self.bot.db.mod.createAction(member.id, self.bot.user.id, reason, 0)
        warnings = len(await self.bot.db.mod.getActionsOfType(member.id, 0))
        to_send = f'{self.bot.user.mention} has given you a warning in `{member.guild.name}`.\nReason: {reason}\nThis is your {Utils.ord(warnings)} warning.'
        oto_send = f'{self.bot.user.mention} has given you a warning in `{member.guild.name}`.\nReason: {reason}\nThis is your {Utils.ord(warnings)} warning.'
        for warns, act in sorted(self.warning_threshold.items(), reverse=True, key=lambda i: i[0]):
            action, duration = act
            if warnings == warns:
                await self.bot.db.mod.createAction(member.id, self.bot.user.id, f"Reached the warning threshold. {warnings}", action, duration)
                if action == 3:
                    dur = f"temporarily banned for {Utils.humanTimeDuration(duration)}." if duration is not None else 'permanently banned.'
                    to_send += f"\nBecause you have recieved {warnings} warnings, you have been " + dur
                    try:
                        embed = Embed(description=to_send, color=discord.Color.gold())
                        msg = await member.send(embed=embed)
                    except discord.HTTPException:
                        pass
                    try:
                        await member.ban(reason=f"Automatic ban for reaching the warning threshold. ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})")
                    except discord.HTTPException:
                        await msg.delete(delay=0.1)
                        try:
                            embed = Embed(description=oto_send, color=discord.Color.gold())
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            pass
                    return
                elif action == 1:
                    to_send += f"\nBecause you have recieved {warnings} warnings, you have been temporarily muted for {Utils.humanTimeDuration(duration)}."
                    try:
                        embed = Embed(description=to_send, color=discord.Color.gold())
                        msg = await member.send(embed=embed)
                    except discord.HTTPException:
                        pass
                    try:
                        await member.add_roles(discord.Object(self.bot.mute_role), reason=f"[AUTOMOD]: {reason} ({Utils.humanTimeDuration(duration) if duration is not None else 'PERMANENT'})")
                    except discord.HTTPException:
                        await msg.delete(delay=0.1)
                        try:
                            embed = Embed(description=oto_send, color=discord.Color.gold())
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            pass
                    return
                else:
                    pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != self.bot.guild_id:
            return
        if member.bot:
            return
        actions: List[ModAction] = await self.bot.db.mod.getActions(member.id)
        for action in actions:
            if not action.expired and (action.expires is None or action.expires <= time.time()) and action.action_type in (1, 4):
                if action.action_type == 1:
                    await member.add_roles(member.guild.get_role(self.bot.mute_role))
                elif action.action_type == 4:
                    await member.add_roles(member.guild.get_role(self.bot.limbo_role))

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return
        await self.on_message(message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return  # Ignore DMs
        if message.guild.id != self.bot.guild_id:
            return  # Not in the right guild
        if message.author.bot:
            return  # Ignore bots
        if message.author.id == self.bot.owner_id or (message.author.guild_permissions.administrator and message.author.id != 554456262994165773):
            return  # Don't check for specific messages
        content = ' ' + message.content + ' '
        for k, v in self.replace.items():
            content = content.replace(k, v)
        try:
            _ill = any([' ' + word + ' ' in ''.join([(e if e.isalnum() else ' ') for e in content.lower()]) for word in self.illegal_words])
            _ill2 = any([' ' + word + ' ' in ''.join([e for e in content.lower() if e.isalnum() or e == ' ']) for word in self.illegal_words])
            _bnn = any([' ' + word + ' ' in ''.join([(e if e.isalnum() else ' ') for e in content.lower()]) for word in self.banned_words])
            _bnn2 = any([' ' + word + ' ' in ''.join([e for e in content.lower() if e.isalnum() or e == ' ']) for word in self.banned_words])
            if _ill or _ill2:
                await message.delete()
                await message.author.add_roles(message.guild.get_role(self.bot.limbo_role))
                await self.bot.db.mod.createAction(message.author.id, self.bot.user.id, "Use of a blacklisted word.", 4, 2592000)
                embed = Embed(description=f'Your message has been deleted because it contains a blacklisted word.\nYou have been sent to limbo for 30 days.', color=discord.Color.red())
                return await message.author.send(embed=embed)
            elif _bnn or _bnn2:
                await message.delete()
                embed = Embed(description=f'Your message has been deleted because it contains a blacklisted word.', color=discord.Color.gold())
                self.cons.append(message.author.id)
                if len([m for m in self.cons.items if message.author.id == m]) >= 5:
                    return await self.warn(message.author)
                return await message.author.send(embed=embed)
            for attach in message.attachments:
                if 'sooty' in attach.filename.lower():
                    await message.delete()
                    return await message.author.send('No more sooty.')
        except discord.HTTPException:
            pass

    
def setup(bot):
    bot.add_cog(Automoderator(bot))
