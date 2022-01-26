import asyncio
from typing import List, Tuple
from utils.dpy import Embed

import discord
import aiosqlite
import os
from time import time
from discord.ext import tasks
import datetime
import random

from utils.objects import ModAction, Suggestion, AtlasException, LevelUser, Ticket, BirthdayUser
from utils.utils import Utils

from discord_slash.utils.manage_components import create_select as Select
from discord_slash.utils.manage_components import create_select_option as SelectOption

class Mod_Actions:
    table = 'ACTIONS'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "USERID INT NOT NULL," \
                 "MODERATOR INT NOT NULL," \
                 "REASON TEXT NOT NULL," \
                 "ID INT NOT NULL," \
                 "TIME INT NOT NULL, " \
                 "EXPIRES INT, " \
                 "ACTION INT NOT NULL," \
                 "EXPIRED BOOLEAN NOT NULL DEFAULT FALSE" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        self.log_channel = bot.config['moderation']['logs']
        bot.loop.create_task(self.init())
        self.undoActions.start()

    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))

    async def close(self):
        self.undoActions.cancel()

    @tasks.loop(minutes=1)
    async def undoActions(self):
        guild = self.bot.get_guild(self.bot.guild_id)
        actions = await self.getAllActions()
        rows: List[ModAction] = [a for a in actions if not a.expired and a.expires is not None and a.expires < int(time())]
        log_channel = self.bot.get_channel(self.log_channel)
        for row in rows:
            if row.action_type == 0:
                pass
            elif row.action_type == 1:
                member = guild.get_member(row.user)
                if member is not None:
                    if self.bot.mute_role in member._roles:
                        await member.remove_roles(guild.get_role(self.bot.mute_role))
                        try:
                            embed = Embed(description=f'Your mute in {guild.name} has expired.', color=discord.Color.green())
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            pass
                        embed = Embed(title="Unmute", description=f"Member: {member.mention}\nModerator: {self.bot.user.mention}", color=discord.Color.green())
                        if log_channel is not None:
                            await log_channel.send(embed=embed)
            elif row.action_type == 2:
                pass
            elif row.action_type == 3:
                try:
                    await guild.unban(discord.Object(row.user))
                except discord.NotFound:
                    pass
                else:
                    member = await self.bot.get_or_fetch_user(row.user)
                    if member is not None:
                        try:
                            embed = Embed(description=f'Your ban in {guild.name} has expired. You can rejoin at https://discord.the-atlas.net/.', color=discord.Color.green())
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            pass
                        embed = Embed(title="Unban", description=f"Member: {member.mention}\nModerator: {self.bot.user.mention}", color=discord.Color.green())
                        if log_channel is not None:
                            await log_channel.send(embed=embed)
            elif row.action_type == 4:
                member = guild.get_member(row.user)
                if member is not None:
                    if self.bot.limbo_role not in member._roles:
                        await member.add_roles(guild.get_role(self.bot.limbo_role))
                        try:
                            embed = Embed(description=f'Your limbo in {guild.name} has expired.', color=discord.Color.green())
                            await member.send(embed=embed)
                        except discord.HTTPException:
                            pass
                        embed = Embed(title="Unlimbo", description=f"Member: {member.mention}\nModerator: {self.bot.user.mention}", color=discord.Color.green())
                        if log_channel is not None:
                            await log_channel.send(embed=embed)
            await self.pool.execute(f"UPDATE {self.table} SET EXPIRED = TRUE WHERE ID = ?;", (row.id,))
            await self.pool.commit()

    @undoActions.before_loop
    async def wait(self):
        await self.bot.wait_until_ready()
        
    async def getNewID(self):
        _id = -1
        async with self.pool.execute(f"SELECT * from {self.table};") as cursor:
            async for row in cursor:
                _id = max(row[3], _id)
        return _id + 1

    async def getAllActions(self):
        ret = []
        async with self.pool.execute(f"SELECT * FROM {self.table};") as cursor:
            async for row in cursor:
                ret.append(ModAction(row))
        return ret

    async def createAction(self, user, moderator, reason, action, duration=None):
        """
        Action Types:
        0 - Warn
        1 - Mute
        2 - Kick
        3 - Ban
        4 - Limbo
        """
        now = int(time())
        if duration is None:
            exp = None
        else:
            exp = now + duration
        if action == 0:
            duration = None
        _id = await self.getNewID()
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?,?,?,?,?,?);", (user, moderator, reason, _id, now, exp, action, False))
        await self.pool.commit()
        log_channel = self.bot.get_channel(self.log_channel)
        dur = Utils.humanTimeDuration(duration) if duration else 'Indefinite'
        _type = 'Warn' if action == 0 else ('Mute' if action == 1 else ('Kick' if action == 2 else ('Ban' if action == 3 else ('Limbo' if action == 4 else 'Unknown'))))
        embed = Embed(title=_type, description=f"Member: <@!{user}>\nModerator: <@!{moderator}>\nReason: {reason}\nDuration: {dur}", color=discord.Color.green())
        if log_channel is not None:
            await log_channel.send(embed=embed)

    async def getActions(self, user):
        ret = []
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USERID = ?;", (user,)) as cursor:
            async for row in cursor:
                ret.append(ModAction(row))
        return ret
    
    async def getActionsOfType(self, user, _type):
        ret = []
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USERID = ? AND ACTION = ?;", (user, _type)) as cursor:
            async for row in cursor:
                ret.append(ModAction(row))
        return ret

    async def getAction(self, _id):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE ID = ?;", (_id,)) as cursor:
            async for row in cursor:
                return ModAction(row)
        raise AtlasException(f'Action with id {_id} does not exist.')

    async def deleteAction(self, _id):
        action = await self.getAction(_id)
        await self.pool.execute(f"DELETE FROM {self.table} WHERE ID = ?;", (_id,))
        await self.pool.commit()
        return action

    async def expireAction(self, _id):
        await self.getAction(_id)
        await self.pool.execute(f"UPDATE {self.table} SET EXPIRED = TRUE WHERE ID = ?;", (_id,))
        await self.pool.commit()

    async def setReason(self, _id, reason):
        await self.getAction(_id)
        await self.pool.execute(f"UPDATE {self.table} SET REASON = ? WHERE ID = ?;", (reason, _id))
        await self.pool.commit()

class Suggestions:
    table = 'SUGGESTIONS'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "USERID INT NOT NULL," \
                 "MESSAGEID INT NOT NULL," \
                 "SUGGESTION TEXT NOT NULL," \
                 "ID INT NOT NULL," \
                 "STATUS BOOLEAN NOT NULL DEFAULT FALSE" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        bot.loop.create_task(self.init())

    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))
        await self.pool.commit()

    async def close(self):
        pass

    async def getNewID(self):
        _id = -1
        async with self.pool.execute(f"SELECT * from {self.table};") as cursor:
            async for row in cursor:
                _id = max(row[3], _id)
        return _id + 1

    async def get(self, _id):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE ID = ?;", (_id,)) as cursor:
            async for row in cursor:
                if bool(row[4]):
                    raise AtlasException(f'Suggestion with ID {_id} has already been resolved.')
                return Suggestion(row)
        raise AtlasException(f'Suggestion with ID {_id} does not exist.')

    async def create(self, user, suggestion):
        _id = await self.getNewID()
        embed = Embed(title=f"Suggestion #{_id}", description=suggestion, color=discord.Color.gold())
        embed.set_author(name=f"{user} ({user.id})", icon_url=user.avatar_url)
        channel = self.bot.get_channel(self.bot.suggestion_channel)
        message = await channel.send(embed=embed)
        await message.add_reaction('⬆')
        await message.add_reaction('⬇')
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?,?,?);", (user.id, message.id, suggestion, _id, False))
        await self.pool.commit()
        return message

    async def deny(self, _id, mod, reason):
        guild = self.bot.get_guild(self.bot.guild_id)
        suggestion = await self.get(_id)
        await self.pool.execute(f"UPDATE {self.table} SET STATUS = TRUE WHERE ID = ?;", (_id,))
        await self.pool.commit()
        member = guild.get_member(suggestion.user)
        if member is not None:
            embed = Embed(description=f'Your suggestion in {guild.name} has been denied by `{mod} ({mod.id})`.\n\nReason:\n{reason}', color=discord.Color.red())
            try:
                await member.send(embed=embed)
            except discord.HTTPException:
                pass
        channel = self.bot.get_channel(self.bot.suggestion_channel)
        try:
            message = await channel.fetch_message(suggestion.message)
        except discord.HTTPException:
            pass
        else:
            embed = message.embeds[0]
            embed.add_field(name=f'Denied by {mod}', value=reason)
            embed.color = discord.Color.red()
            await message.edit(embed=embed)
        embed = Embed(description=f'Suggestion #{_id} denied by `{mod} ({mod.id})`', color=discord.Color.red())
        embed.add_field(name='Suggestion', value=suggestion.suggestion, inline=True)
        embed.add_field(name='Reason', value=reason, inline=True)
        deny_channel = self.bot.get_channel(self.bot.sugg_deny_channel)
        if deny_channel is not None:
            await deny_channel.send(embed=embed)

    async def accept(self, _id, mod, reason):
        guild = self.bot.get_guild(self.bot.guild_id)
        suggestion = await self.get(_id)
        await self.pool.execute(f"UPDATE {self.table} SET STATUS = TRUE WHERE ID = ?;", (_id,))
        await self.pool.commit()
        member = guild.get_member(suggestion.user)
        if member is not None:
            embed = Embed(description=f'Your suggestion in {guild.name} has been accepted by `{mod} ({mod.id})`.\n\nReason:\n{reason}', color=discord.Color.green())
            try:
                await member.send(embed=embed)
            except discord.HTTPException:
                pass
        channel = self.bot.get_channel(self.bot.suggestion_channel)
        try:
            message = await channel.fetch_message(suggestion.message)
        except discord.HTTPException:
            pass
        else:
            embed = message.embeds[0]
            embed.add_field(name=f'Accepted by {mod}', value=reason)
            embed.color = discord.Color.green()
            await message.edit(embed=embed)
        embed = Embed(description=f'Suggestion #{_id} accepted by `{mod} ({mod.id})`', color=discord.Color.green())
        embed.add_field(name='Suggestion', value=suggestion.suggestion, inline=True)
        embed.add_field(name='Reason', value=reason, inline=True)
        deny_channel = self.bot.get_channel(self.bot.sugg_accept_channel)
        if deny_channel is not None:
            await deny_channel.send(embed=embed)

class Leveling:
    table = 'LEVELS'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "USERID INT NOT NULL," \
                 "MESSAGES INT NOT NULL," \
                 "XP INT NOT NULL" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        bot.loop.create_task(self.init())

    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))
        await self.pool.commit()

    async def close(self):
        pass

    async def get(self, user):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USERID = ?;", (user,)) as cursor:
            async for row in cursor:
                return LevelUser(row)
        return None

    async def update(self, user, xp):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USERID = ?;", (user,)) as cursor:
            async for _ in cursor:
                await self.pool.execute(f"UPDATE {self.table} SET XP = XP + ?, MESSAGES = MESSAGES WHERE USERID = ?;", (xp, user))
                await self.pool.commit()
                return
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?);", (user, 1, xp))
        await self.pool.commit()

    async def addMessage(self, user):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USERID = ?;", (user,)) as cursor:
            async for _ in cursor:
                await self.pool.execute(f"UPDATE {self.table} SET MESSAGES = MESSAGES + 1 WHERE USERID = ?;", (user,))
                await self.pool.commit()
                return
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?);", (user, 1, 0))
        await self.pool.commit()

    async def getAll(self):
        users = []
        async with self.pool.execute(f"SELECT * FROM {self.table};") as cursor:
            async for row in cursor:
                users.append(LevelUser(row))
        return users

class Roles:
    table = 'ROLES'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "ROLEID INT NOT NULL," \
                 "NAME TEXT NOT NULL," \
                 "DESCRIPTION TEXT NOT NULL" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        self.channel = self.bot._config['roles']['channel']
        with open('data/message.txt', 'r') as f:
            self.message = int(f.read())
        bot.loop.create_task(self.init())

    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))
        await self.pool.commit()

    async def close(self):
        pass

    async def add(self, role, name, description):
        try:
            await self.get(role)
        except AtlasException:
            pass
        else:
            raise AtlasException('Role already exists.')
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?);", (role, name, description))
        await self.pool.commit()
        return await self.getAll()

    async def get(self, role):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE ROLEID = ?;", (role,)) as cursor:
            async for row in cursor:
                return row
        raise AtlasException("That reaction role doesn't exist.")

    async def getAll(self):
        options = []
        embed = Embed(
            title="Roles",
        )
        embed.timestamp = Embed.Empty
        embed.set_footer(text="Select a role to toggle below.")
        async with self.pool.execute(f"SELECT * FROM {self.table};") as cursor:
            async for row in cursor:
                role = self.bot.get_guild(self.bot.guild_id).get_role(row[0])
                if role is None:
                    continue
                embed.add_field(name=row[1], value=row[2])
                _o = SelectOption(
                    label=row[1], 
                    value=str(role.id),
                    description=f"Role ID: {role.id}"
                )
                options.append(_o)
        if options:
            select = Select(options=options, custom_id=f"select-role", placeholder="Select a role to toggle.", min_values=1, max_values=1)
        else:
            select = None
        return select, embed

    async def remove(self, role):
        await self.get(role)
        await self.pool.execute(f"DELETE FROM {self.table} WHERE ROLEID = ?;", (role,))
        await self.pool.commit()
        return await self.getAll()
    
class Tickets:
    table = 'TICKETS'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "ID INT NOT NULL," \
                 "USERID INT NOT NULL," \
                 "CHANNELID INT NOT NULL," \
                 "STATUS INT NOT NULL," \
                 "CREATED INT NOT NULL" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        bot.loop.create_task(self.init())

    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))
        await self.pool.commit()

    async def close(self):
        pass

    async def getNewID(self):
        _id = -1
        async with self.pool.execute(f"SELECT * from {self.table};") as cursor:
            async for row in cursor:
                _id = max(row[0], _id)
        return _id + 1

    async def get(self, id):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE ID = ?;", (id,)) as cursor:
            async for row in cursor:
                return Ticket(row)
        raise AtlasException("That ticket doesn't exist.")

    async def getAll(self):
        ret = []
        async with self.pool.execute(f"SELECT * FROM {self.table};") as cursor:
            async for row in cursor:
                ret.append(Ticket(row))
        return ret

    async def getChannel(self, channel):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE CHANNELID = ?;", (channel,)) as cursor:
            async for row in cursor:
                return Ticket(row)
        raise AtlasException("That ticket doesn't exist.")

    async def add(self, user, channel):
        _id = await self.getNewID()
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?,?,?);", (_id, user, channel, 0, time()))
        await self.pool.commit()

    async def remove(self, id):
        await self.get(id)
        await self.pool.execute(f"DELETE FROM {self.table} WHERE ID = ?;", (id,))
        await self.pool.commit()

    async def updateState(self, id, state):
        await self.get(id)
        await self.pool.execute(f"UPDATE {self.table} SET STATUS = ? WHERE ID = ?;", (state, id))
        await self.pool.commit()

class Other:
    table = 'OTHER'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "USER1 INT NOT NULL," \
                 "USER2 INT NOT NULL," \
                 "VALUE INT NOT NULL," \
                 "TYPE INT NOT NULL" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        bot.loop.create_task(self.init())

    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))
        await self.pool.commit()

    async def close(self):
        pass

    async def add(self, user1, user2, value, _type):
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?,?);", (user1, user2, value, _type))
        await self.pool.commit()

    async def get(self, user1, user2, _type) -> Tuple[int, int, int, int]:
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USER1 = ? AND USER2 = ? AND TYPE = ?;", (user1, user2, _type)) as cursor:
            async for row in cursor:
                return row
        raise AtlasException("Those users aren't in the database.")

    async def remove(self, user1, user2, _type):
        await self.get(user1, user2, _type)
        await self.pool.execute(f"DELETE FROM {self.table} WHERE USER1 = ? AND USER2 = ? AND TYPE = ?;", (user1, user2, _type))
        await self.pool.commit()

class Birthday:
    table = 'BIRTHDAYS'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "USERID INT NOT NULL," \
                 "MONTH INT NOT NULL," \
                 "DAY INT NOT NULL" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        bot.loop.create_task(self.init())

    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))
        await self.pool.commit()

    async def close(self):
        pass

    async def get(self, user):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USERID = ?;", (user,)) as cursor:
            async for row in cursor:
                return BirthdayUser(row)
        return None

    async def set(self, user, month, day):
        async with self.pool.execute(f"SELECT * FROM {self.table} WHERE USERID = ?;", (user,)) as cursor:
            async for _ in cursor:
                await self.pool.execute(f"UPDATE {self.table} SET MONTH = ?, DAY = ? WHERE USERID = ?;", (month, day, user))
                await self.pool.commit()
                return
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?);", (user, month, day))
        await self.pool.commit()

    async def remove(self, user):
        if await self.get(user) is None:
            raise AtlasException("You don't have a birthday set.")
        await self.pool.execute(f"DELETE FROM {self.table} WHERE USERID = ?;", (user,))
        await self.pool.commit()

    async def getAll(self):
        users = []
        async with self.pool.execute(f"SELECT * FROM {self.table};") as cursor:
            async for row in cursor:
                users.append(BirthdayUser(row))
        return users

class Giveaways:
    table = 'GIVEAWAYS'
    init_query = "CREATE TABLE IF NOT EXISTS {} (" \
                 "CHANNELID INT NOT NULL," \
                 "MESSAGEID INT NOT NULL," \
                 "WINNERS INT NOT NULL," \
                 "ENDS INT NOT NULL," \
                 "ENDED BOOLEAN NOT NULL DEFAULT FALSE" \
                 ");"

    def __init__(self, bot, pool):
        self.bot = bot
        self.pool: aiosqlite.Connection = pool
        bot.loop.create_task(self.init())
    
    async def init(self):
        await self.pool.execute(self.init_query.format(self.table))
        await self.pool.commit()

    async def close(self):
        pass

    async def create(self, channel, prize, duration, winners, maker):
        now = datetime.datetime.utcnow()
        end = now + datetime.timedelta(seconds=duration)
        embed = Embed(title=prize, description=f"React with :tada: to enter the giveaway!\n"
                                               f"**{winners}** winner{'s' if winners > 1 else ''} will be chosen.\n"
                                               f"This giveaway will end <t:{int(end.timestamp())}:R>", 
                      color=discord.Color.blurple())
        message = await channel.send(f"Giveaway created by {maker.mention}.", embed=embed)
        await message.add_reaction("🎉")
        await self.pool.execute(f"INSERT INTO {self.table} VALUES (?,?,?,?,?);", (channel.id, message.id, winners, end.timestamp(), False))
        await self.pool.commit()
        return message

    async def check(self):
        now = datetime.datetime.utcnow()
        async with self.pool.execute(f"SELECT * FROM {self.table}") as cursor:
            async for row in cursor:
                if (row[3] + 86400) < now.timestamp() and bool(row[4]):
                    await self.pool.execute(f"DELETE FROM {self.table} WHERE CHANNELID = ? AND MESSAGEID = ?;", (row[0], row[1]))
                    await self.pool.commit()
                elif row[3] < now.timestamp() and not bool(row[4]):
                    await self.pool.execute(f"UPDATE {self.table} SET ENDED = TRUE WHERE CHANNELID = ? AND MESSAGEID = ?;", (row[0], row[1]))
                    await self.pool.commit()
                    channel = self.bot.get_channel(row[0])
                    try:
                        message = await channel.fetch_message(row[1])
                    except discord.NotFound:
                        await self.pool.execute(f"DELETE FROM {self.table} WHERE CHANNELID = ? AND MESSAGEID = ?;", (row[0], row[1]))
                        await self.pool.commit()
                        continue
                    prize = message.embeds[0].title
                    winners = row[2]
                    reacted = []
                    for reaction in message.reactions:
                        if reaction.emoji == "🎉":
                            async for user in reaction.users():
                                if not user.bot:
                                    reacted.append(user)
                    if len(reacted) != 0:
                        if len(reacted) >= winners:
                            winners = random.sample(reacted, winners)
                            await message.reply(f"Congratulations {', '.join([winner.mention for winner in winners])}, you won **{prize}**! :tada:")
                        else:
                            winners = reacted
                            await message.reply(f"Congratulations {', '.join([winner.mention for winner in winners])}, you won **{prize}**! :tada:")
                        embed = message.embeds[0]
                        embed.description = f"This giveaway ended <t:{int(now.timestamp())}:R>." \
                                            f"\nWinners: {', '.join([winner.mention for winner in winners])}"
                        await message.edit(embed=embed)
                    else:
                        embed = message.embeds[0]
                        embed.description = f"This giveaway ended <t:{int(now.timestamp())}:R>." \
                                            f"\nWinners: Nobody :slight_frown:"
                        await message.edit(embed=embed)
                        await message.reply(f"Nobody won. :slight_frown:")
                    

class Database:
    def __init__(self, bot):
        self.bot = bot
        self.init.start()

    @tasks.loop(count=1)
    async def init(self):
        self.pool: aiosqlite.Connection = await aiosqlite.connect('data/database.db')
        self.mod = Mod_Actions(self.bot, self.pool)
        self.suggest = Suggestions(self.bot, self.pool)
        self.level = Leveling(self.bot, self.pool)
        self.roles = Roles(self.bot, self.pool)
        self.tickets = Tickets(self.bot, self.pool)
        self.other = Other(self.bot, self.pool)
        self.birthday = Birthday(self.bot, self.pool)
        self.giveaway = Giveaways(self.bot, self.pool)

    async def close(self):
        await self.pool.commit()
        await asyncio.wait_for(self.pool.close(), timeout=5)
        await self.mod.close()
        await self.suggest.close()
        await self.level.close()
        await self.roles.close()
        await self.tickets.close()
        await self.other.close()
        await self.birthday.close()
        await self.giveaway.close()
