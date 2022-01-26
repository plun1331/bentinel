""" Paginator """
import asyncio
from datetime import datetime
from typing import List

import discord
from discord.ext import commands
from discord_slash.model import ButtonStyle
from discord_slash.utils.manage_components import create_button as Button, create_actionrow as ActionRow
from discord_slash import ComponentContext, SlashContext

from utils.dpy import Embed

TimeoutButton = Button(label="Menu timed out.", style=ButtonStyle.red, disabled=True)
ClosedButton = Button(label="Menu closed.", style=ButtonStyle.red, disabled=True)

class EmbedPaginator:
    def __init__(self, ctx: SlashContext, embeds: List[Embed], *, footer: str = ''):
        self.page = 0
        self.embeds = embeds
        self.ctx = ctx
        self.bot = None
        self.ran = None
        self.footer = footer + ' ' if footer != '' else ''
        self.buttons = [
            ActionRow(
                Button(custom_id='first', style=ButtonStyle.blue, disabled=False, emoji='⏪'),
                Button(custom_id='back', style=ButtonStyle.blue, disabled=False, emoji='◀'),
                Button(custom_id='stop', style=ButtonStyle.blue, disabled=False, emoji='⏹'),
                Button(custom_id='next', style=ButtonStyle.blue, disabled=False, emoji='▶'),
                Button(custom_id='last', style=ButtonStyle.blue, disabled=False, emoji='⏩'),
            ),
            ActionRow(
                Button(custom_id='selPage', style=ButtonStyle.blue, disabled=False, emoji='🔢')
            )
        ]
        self.no_left = [
            ActionRow(
                Button(custom_id='first', style=ButtonStyle.blue, disabled=True, emoji='⏪'),
                Button(custom_id='back', style=ButtonStyle.blue, disabled=True, emoji='◀'),
                Button(custom_id='stop', style=ButtonStyle.blue, disabled=False, emoji='⏹'),
                Button(custom_id='next', style=ButtonStyle.blue, disabled=False, emoji='▶'),
                Button(custom_id='last', style=ButtonStyle.blue, disabled=False, emoji='⏩'),
            ),
            ActionRow(
                Button(custom_id='selPage', style=ButtonStyle.blue, disabled=False, emoji='🔢')
            )
        ]
        self.no_right = [
            ActionRow(
                Button(custom_id='first', style=ButtonStyle.blue, disabled=False, emoji='⏪'),
                Button(custom_id='back', style=ButtonStyle.blue, disabled=False, emoji='◀'),
                Button(custom_id='stop', style=ButtonStyle.blue, disabled=False, emoji='⏹'),
                Button(custom_id='next', style=ButtonStyle.blue, disabled=True, emoji='▶'),
                Button(custom_id='last', style=ButtonStyle.blue, disabled=True, emoji='⏩'),
            ),
            ActionRow(
                Button(custom_id='selPage', style=ButtonStyle.blue, disabled=False, emoji='🔢')
            )
        ]
        self.disabled_buttons = [
            ActionRow(
                Button(custom_id='first', style=ButtonStyle.blue, disabled=True, emoji='⏪'),
                Button(custom_id='back', style=ButtonStyle.blue, disabled=True, emoji='◀'),
                Button(custom_id='stop', style=ButtonStyle.blue, disabled=True, emoji='⏹'),
                Button(custom_id='next', style=ButtonStyle.blue, disabled=True, emoji='▶'),
                Button(custom_id='last', style=ButtonStyle.blue, disabled=True, emoji='⏩'),
            ),
            ActionRow(
                Button(custom_id='selPage', style=ButtonStyle.blue, disabled=True, emoji='🔢')
            )
        ]
        self.running = False
        self.message = None
        self.in_help = False

    async def listen(self):
        while self.running:
            try:
                res = await self.bot.wait_for("component", check=self.check, timeout=60)
            except asyncio.TimeoutError:
                if self.running:
                    self.running = False
                    await self.message.edit(components=[ActionRow(TimeoutButton)])
                return
            asyncio.create_task(self.update(res))
    
    async def update(self, res: ComponentContext):
        if res.author.id != self.ctx.author.id:
            return await res.send(content="This isn't your paginator!", hidden=True)
        try:
            if not self.in_help:
                if res.custom_id == 'first':
                    self.page = 0
                elif res.custom_id == 'back':
                    self.page -= 1
                    if self.page < 0:
                        self.page = 0
                elif res.custom_id == 'stop':
                    self.running = False
                    await res.edit_origin(components=[ActionRow(ClosedButton)])
                    return
                elif res.custom_id == 'next':
                    self.page += 1
                    if self.page > len(self.embeds)-1:
                        self.page = len(self.embeds)-1
                elif res.custom_id == 'last':
                    self.page = len(self.embeds)-1
                elif res.custom_id == 'selPage':
                    await res.edit_origin(components=self.disabled_buttons)
                    msg = await self.ctx.send(f"{self.ctx.author.mention}, What page would you like to go to?")
                    try:
                        _in = await self.bot.wait_for('message', check=lambda m: m.author.id == self.ctx.author.id and m.channel.id == self.ctx.channel.id, timeout=60)
                    except asyncio.TimeoutError:
                        await self.message.edit(components=self.buttons)
                        return await msg.delete(delay=0.1)
                    await msg.delete(delay=0.1)
                    try:
                        page = int(_in.content)
                    except ValueError:
                        await self.message.edit(components=self.buttons)
                        return await _in.delete(delay=0.1)
                    if page > len(self.embeds):
                        page = len(self.embeds)
                    if page < 1:
                        page = 1
                    self.page = page - 1
                    await _in.delete(delay=0.1)
                    self.embeds[self.page].set_footer(text=f"{self.footer}Page "
                                                        f"{self.page + 1}/{len(self.embeds)}")
                    self.embeds[self.page].timestamp = self.ran
                    await self.message.edit(embed=self.embeds[self.page], components=self.buttons)
                    return
                else:
                    return
            self.in_help = False
            self.embeds[self.page].set_footer(text=f"{self.footer}Page "
                                                        f"{self.page + 1}/{len(self.embeds)}")
            self.embeds[self.page].timestamp = self.ran
            if self.page >= len(self.embeds)-1:
                await res.edit_origin(embed=self.embeds[self.page], components=self.no_right)
            elif self.page <= 0:
                await res.edit_origin(embed=self.embeds[self.page], components=self.no_left)
            else:
                await res.edit_origin(embed=self.embeds[self.page], components=self.buttons)
        except discord.NotFound:
            try:
                self.running = False
                await self.message.edit(components=[])
            except discord.HTTPException:
                pass

    def check(self, res: ComponentContext):
        return res.origin_message_id == self.message.id and res.custom_id in ('last', 'back', 'stop', 'next', 'first', 'selPage') and res.channel.id == self.message.channel.id

    async def send_initial(self):
        self.embeds[self.page].set_footer(text=f"{self.footer}Page {self.page + 1}/{len(self.embeds)}")
        self.embeds[self.page].timestamp = self.ran
        self.message = await self.ctx.send(embed=self.embeds[self.page], components=self.no_left)

    async def run(self):
        self.ran = datetime.utcnow()
        if len(self.embeds) == 1:
            self.embeds[self.page].set_footer(text=f"{self.footer}Page {self.page + 1}/{len(self.embeds)}")
            self.embeds[self.page].timestamp = self.ran
            await self.ctx.send(embed=self.embeds[0])
            return
        self.running = True
        self.bot = self.ctx.bot
        await self.send_initial()
        await self.listen()
        self.running = False


class TextPageSource:
    """ Get pages for text paginator """

    def __init__(self, text, *, prefix='```', suffix='```', max_size=2000):
        pages = commands.Paginator(prefix=prefix, suffix=suffix, max_size=max_size - 200)
        for line in text.split('\n'):
            pages.add_line(line)
        self._pages = pages

    @property
    def pages(self):
        return self._pages.pages
