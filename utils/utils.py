import time
from typing import Union
import aiohttp
import os
import json


TIME_DURATION_UNITS = (
    ('week', 60 * 60 * 24 * 7),
    ('day', 60 * 60 * 24),
    ('hour', 60 * 60),
    ('minute', 60),
    ('second', 1)
)

class Utils:
    @staticmethod
    def get_percent(x, y):
        return (x / y) * 100

    @staticmethod
    def ord(n):
        n = int(n)
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        return str(n) + suffix

    @staticmethod
    def humanJoin(seq, delim=', ', *, final='or', code=False):
        if code:
            delim = f"`{delim} `"
        size = len(seq)
        if size == 0:
            return ''

        if size == 1:
            if code:
                return f"`{seq[0]}`"
            return seq[0]

        if size == 2:
            if code:
                return f"`{seq[0]}` {final} `{seq[1]}`"
            return f'{seq[0]} {final} {seq[1]}'

        if code:
            return '`' + delim.join(seq[:-1]) + f'` {final} `{seq[-1]}`'
        return delim.join(seq[:-1]) + f' {final} {seq[-1]}'

    @staticmethod
    def humanTimeDuration(seconds):
        if seconds == 0 or not isinstance(seconds, (int, float)):
            return None
        parts = []
        for unit, div in TIME_DURATION_UNITS:
            amount, seconds = divmod(int(seconds), div)
            if amount > 0:
                parts.append(f'{amount} {unit}{"" if amount == 1 else "s"}')
        return Utils.humanJoin(parts, final='and')

    @staticmethod
    def convertTime(time):
        time = time.strip()
        val = time[-1]
        _time = int(time[:-1])
        c = {
            's': 'second',
            'm': 'minute',
            'h': 'hour',
            'd': 'day',
            'w': 'week'
        }
        if val.lower() in c:
            val = c[val.lower()]
        for unit, amnt in TIME_DURATION_UNITS:
            if val.lower() == unit:
                return amnt * _time
        raise ValueError

    @staticmethod
    async def reboot():
        url = "https://hosting.swofty.net/api/client/servers/dea1537e/power"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('SWOFTY')}"
        }

        data = '{"signal": "restart"}'
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as resp:
                return await resp.read()

    @staticmethod
    async def getuuid(name):
        url = f"https://api.mojang.com/users/profiles/minecraft/{name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                try:
                    return (await resp.json()).get('id', None)
                except json.JsonDecodeError:
                    return None

    @staticmethod
    async def getname(uuid):
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                try:
                    return (await resp.json()).get('name', None)
                except json.JsonDecodeError:
                    return None
                
    @staticmethod
    async def getTwitterUser(name, token):
        url = f"https://api.twitter.com/2/users/by?usernames={name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'Authorization': f"Bearer {token}"}) as resp:
                try:
                    return (await resp.json())
                except json.JsonDecodeError:
                    return None
                
    @staticmethod
    async def getTwitterPosts(user_id, token):
        url = f"https://api.twitter.com/2/users/{user_id}/tweets?tweet.fields=created_at&max_results=10&exclude=replies"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'Authorization': f"Bearer {token}"}) as resp:
                try:
                    return (await resp.json())
                except json.JsonDecodeError:
                    return None

    @staticmethod
    async def postTicketTranscript(data):
        url = f"url"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('SWOFTY')}"
        }
        data = {'data': data}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as resp:
                return await resp.read()

    @staticmethod
    def level(xp):
        level = 0
        beforexp = 0
        nxt_lvl_xp = 0
        for lvl in range(1, 1000):
            lvl_xp = 5 / 6 * lvl * (2 * lvl * lvl + 27 * lvl + 91)
            xp_needed = lvl_xp - xp
            level = lvl-1
            if xp_needed >= 0:
                lvl_xp = 5 / 6 * lvl * (2 * lvl * lvl + 27 * lvl + 91)
                exp = 5 / 6 * (lvl-1) * (2 * (lvl-1) * (lvl-1) + 27 * (lvl-1) + 91)
                beforexp = exp+1
                nxt_lvl_xp = lvl_xp+1
                break
        return level, int(beforexp), int(nxt_lvl_xp) # level, xp to next level, xp needed for next level


class ExpiringCache:
    def __init__(self, *, seconds: Union[int, float]):
        self.s = seconds
        self._items = {}

    def append(self, obj):
        self.clr()
        n = time.time()
        if n not in self._items:
            self._items[n] = []
        self._items[n].append(obj)

    def clr(self):
        for k in dict(self._items).keys():
            if k <= time.time() - self.s:
                self._items.pop(k)

    @property
    def items(self):
        self.clr()
        e = []
        [e.extend(i) for i in self._items.values()]
        return e
