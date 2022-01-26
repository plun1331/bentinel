import json
import asyncio
import re
import discord
from discord.ext import commands
import discord_slash
from discord_slash import SlashContext, ComponentContext
from discord_slash import cog_ext as slash
from discord_slash.utils.manage_commands import create_option as Option
from discord_slash.utils.manage_commands import create_choice as Choice
from discord_slash.utils.manage_components import create_button as Button
from discord_slash.utils.manage_components import create_select as Select
from discord_slash.utils.manage_components import create_select_option as SelectOption
from discord_slash.utils.manage_components import create_actionrow as ActionRow
from discord_slash.model import ButtonStyle, SlashCommandOptionType as OptionType

from utils.dpy import Embed
from utils.utils import Utils
from utils.paginator import EmbedPaginator, TextPageSource
from utils.objects import AtlasException
from bot import Bot, ATLAS

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.verified_role = 877602252209139735

    @commands.Cog.listener()
    async def on_component(self, ctx: ComponentContext):
        if ctx.custom_id == 'select-role':
            await ctx.defer(hidden=True)
            role = ctx.selected_options[0]
            role = ctx.guild.get_role(int(role))
            if role is None:
                return await ctx.send("That role doesn't seem to exist. Please notify an administrator.", hidden=True)
            select, _ = await self.bot.db.roles.getAll()
            await ctx.origin_message.edit(components=[ActionRow(select)]) # just resets the select menu
            try:
                if role.id in ctx.author._roles:
                    await ctx.author.remove_roles(role)
                    await ctx.send(f"The {role.mention} has been removed from you.", hidden=True)
                else:
                    await ctx.author.add_roles(role)
                    await ctx.send(f"You have been given the role {role.mention}.", hidden=True)
            except discord.Forbidden:
                await ctx.send("I couldn't edit your roles because of permission issues. Please notify an administrator.", hidden=True)
        elif ctx.custom_id == 'verify':
            await ctx.defer(hidden=True)
            if self.verified_role in ctx.author._roles:
                await ctx.send("You are already verified!", hidden=True)
            else:
                role = ctx.guild.get_role(self.verified_role)
                if role is None:
                    return await ctx.send("That role doesn't seem to exist. Please notify an administrator.", hidden=True)
                try:
                    await ctx.author.add_roles(role)
                except discord.Forbidden:
                    await ctx.send("I couldn't edit your roles because of permission issues. Please notify an administrator.", hidden=True)
                else:
                    await ctx.send("You have been verified!", hidden=True)


    @slash.cog_subcommand(
        base="roles",
        base_desc="Manage toggleable roles.",
        name="add",
        description="Adds a toggleable role.",
        options=[
            Option(
                name="role",
                option_type=OptionType.ROLE,
                required=True,
                description="The role to add.",
            ),
            Option(
                name="name",
                option_type=OptionType.STRING,
                required=True,
                description="The name to give the role in the embed.",
            ),
            Option(
                name="description",
                option_type=OptionType.STRING,
                required=False,
                description="The description to show on the role menu. Leave blank to input something else later.",
            )
        ],
        guild_ids=[ATLAS]
    )
    async def add(self, ctx: SlashContext, role: discord.Role, name: str, description: str = None):
        if not ctx.author.guild_permissions.administrator and ctx.author.id != self.bot.owner_id:
            return await ctx.send("Insufficient permissions.")
        if description is None:
            await ctx.send("Please enter a description for the role.")
            try:
                description = await ctx.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                description = description.content
            except asyncio.TimeoutError:
                return await ctx.send("Timed out.")
        try:
            select, embed = await self.bot.db.roles.add(role.id, name, description)
        except AtlasException as e:
            return await ctx.send(str(e))
        channel = self.bot.get_channel(self.bot.db.roles.channel)
        if channel is None:
            return await ctx.send("The role channel does not exist.")
        msg = channel.get_partial_message(self.bot.db.roles.message)
        try:
            await msg.edit(embed=embed, components=[ActionRow(select)])
        except discord.NotFound:
            msg = await channel.send(embed=embed, components=[ActionRow(select)])
            with open('data/message.txt', 'w') as f:
                f.write(str(msg.id))
            self.bot.db.roles.message = msg.id
        await ctx.send('Role added.')

    @slash.cog_subcommand(
        base="roles",
        base_desc="Manage toggleable roles.",
        name="remove",
        description="Removes a toggleable role.",
        options=[
            Option(
                name="role",
                option_type=OptionType.ROLE,
                required=True,
                description="The role to remove.",
            )
        ],
        guild_ids=[ATLAS]
    )
    async def remove(self, ctx: SlashContext, role: discord.Role):
        if not ctx.author.guild_permissions.administrator and ctx.author.id != self.bot.owner_id:
            return await ctx.send("Insufficient permissions.")
        try:
            select, embed = await self.bot.db.roles.remove(role.id)
        except AtlasException as e:
            return await ctx.send(str(e))
        channel = self.bot.get_channel(self.bot.db.roles.channel)
        if channel is None:
            return await ctx.send("The role channel does not exist.", hidden=True)
        msg = channel.get_partial_message(self.bot.db.roles.message)
        try:
            if select is not None:
                await msg.edit(embed=embed, components=[ActionRow(select)])
            else:
                await msg.edit(embed=embed, components=[])
        except discord.NotFound:
            if select is not None:
                msg = await channel.sendt(embed=embed, components=[ActionRow(select)])
            else:
                msg = await channel.send(embed=embed, components=[])
            with open('data/message.txt', 'w') as f:
                f.write(str(msg.id))
            self.bot.db.roles.message = msg.id
        await ctx.send('Role removed.')

    @slash.cog_subcommand(
        base="roles",
        base_desc="Manage toggleable roles.",
        name="create",
        description="Recreates the role message.",
        guild_ids=[ATLAS]
    )
    async def create(self, ctx: SlashContext):
        if not ctx.author.guild_permissions.administrator and ctx.author.id != self.bot.owner_id:
            return await ctx.send("Insufficient permissions.")
        channel = self.bot.get_channel(self.bot.db.roles.channel)
        if channel is None:
            await ctx.send("The role channel does not exist.", hidden=True)
            return
        select, embed = await self.bot.db.roles.getAll()
        if select:
            msg = await channel.send(embed=embed, components=[ActionRow(select)])
        else:
            return await ctx.send("No roles to display.")
        with open('data/message.txt', 'w') as f:
            f.write(str(msg.id))
        self.bot.db.roles.message = msg.id
        await ctx.send("The role message has been recreated.", hidden=True)
        
    @slash.cog_subcommand(
        base="roles",
        base_desc="Manage toggleable roles.",
        name="rules",
        description="Sends the rules message in the server's rules channel.",
        guild_ids=[ATLAS]
    )  
    async def rules(self, ctx:SlashContext):
        if not ctx.author.guild_permissions.administrator and ctx.author.id != self.bot.owner_id:
            return await ctx.send("Insufficient permissions.", hidden=True)
        channel = ctx.guild.rules_channel
        if channel is None:
            return await ctx.send("The rules channel does not exist.", hidden=True)
        await ctx.defer(hidden=True)
        embeds = []
        embed = discord.Embed(title="General Information",
                      description="For more support, check out the following:",
                      color=discord.Color.blurple())
        embed.add_field(name="Appeals", value="If you wish to discuss appeals, please head to our [Ban Appeals](https://discord.gg/jrU5aUEBYe) server. (https://discord.gg/jrU5aUEBYe)", inline=False)
        embed.add_field(name="Support Inquiries & Store Issues", value="For Support related issues, such as purchases, ranks, and connections, please contact support by visiting <#856952204270239835> and opening a ticket.", inline=False)
        embed.add_field(name="Reporting Rule Breakers", value="If you want to report a rule breaker, please use the `/report` command in-game.", inline=False)
        embed.add_field(name="Server IP Address", value="IP: `mc.the-atlas.net`\nSupported Versions: `1.8 - 1.17`", inline=False)
        embeds.append(embed)
        embed = discord.Embed(title="Safety Tips",
                      description="To ensure you enjoy your time on our Discord Server, we would like to offer you some safety tips to help you out! We recommend the following:\n\n"
                                  ":one: Discord Settings > Privacy and Safety.\n\n"
                                  ":two: Turn your Safe Direct Messaging to 'Keep me safe' or 'My friends are nice'. This will allow Discord to scan messages from certain people to ensure they are safe to view.\n\n"
                                  ":three: Turning off 'Allow direct messages from server members'. This will allow only messages from people that are your Friend in Discord.\n\n"
                                  ":four: Checking your 'Who can add you as a friend' to make sure you are happy with the settings. You can allow everyone, friends of friends, server members, or no one to add you as a friend.\n\n"
                                  ":five: Do not accept friend requests from users you do not know.",
                      color=discord.Color.blurple())
        embeds.append(embed)
        embed = discord.Embed(title="Discord Rules",
                      description="In addition to the Atlas Server Rules, which can be found [here](https://www.the-atlas.net/rules), we have some Discord specific rules:",
                      color=discord.Color.blurple())
        embed.add_field(name="Moderation Injustice", 
                        value="In terms of punishments, whatever is said by the moderation team is final.\n"
                              "However, if you have concrete proof of moderation abuse/power frenzies, then you may bring this up to the attention of an administrator or community manager.\n\n"
                              "Discord bans can be appealed on our other server (just in case!)\n"
                              "Which can be found here: https://discord.gg/jrU5aUEBYe\n\n"
                              "All members have the opportunity to appeal their ban if they believe that they are innocent. "
                              "If you were muted, kicked or warned, your punishment is non-appealable unless a mistake has occurred. "
                              "If you witness a staff breaking our rules in the server and no staff members are responding to the situation, you can get staff member attention by pinging an online staff member once. "
                              "Abuse of ping (ex: spamming or wasting staff time) will result in action being taken against your offense.", inline=False)
        embed.add_field(name="Advertising",
                        value="All forms of advertisement aside from discord servers/websites that are affiliated, partnered, official Hypixel/Atlas media, "
                              "or with the approval of an administrator will be taken upon action.\n\n"
                              "This case is non-appealable as we know that our members have somewhat of a brain and thought that advertising their 30 member discord was a good idea.", inline=False)
        embed.add_field(name="Player Respect",
                        value="Our community must be respectful.\n"
                              "Even if it is not a staff member, please treat everyone with respect at all times.\n\n"
                              "Excessive homophobia, racism, any forms of hate speech, bullying, and suicide encouragement is not tolerated and non-appealable.", inline=False)
        embed.add_field(name="User Safety",
                        value="We value our members' safety at all times.\n"
                              "That means, any Doxxing attempts will & can be reported to a moderator.\n\n"
                              "Please make sure not to share any personal information!\n"
                              "Any addresses or personal information will be instantly deleted by moderators to protect the community's privacy and the perpetrator will receive a permanent ban.", inline=False)
        embed.add_field(name="Server Espionage",
                        value="Should you be found responsible, affiliated, or related to an attack to the server or it's player-base, you will be banned no matter how small you contributed.\n\n"
                              "This topic is not taken lightly.", inline=False)
        embed.add_field(name="Suicide Encouragement",
                        value="You may not promote or encourage suicide or self-harm.\n\n"
                              "At Atlas, we recognize that suicide and self-harm are significant social & public health challenges that require collaboration between all stakeholders – public, private, and civil society – and that we have a role and responsibility to help people access and receive support when they need it. "
                              "We have recognized the need to protect people from the potential harm caused by exposure to content that could promote or encourage self-harm – intentionally or inadvertently. "
                              "That’s why our rules prohibit content that promotes or encourages self-harming behaviors and provides support to those undergoing experiences with self-harm or suicidal thoughts.\n\n"
                              "NOTE: people can share their personal experiences, but should avoid sharing detailed information about specific strategies or methods related to self-harm, as this could inadvertently encourage this behavior.", inline=False)
        embed.add_field(name="Unnecessary Pings",
                        value="Please refrain from pinging any staff member above moderator or any of the Sandbox Developers as they are actively working on updates.\n"
                              "Should this happen you will be either permanently muted or banned.", inline=False)
        embed.add_field(name="Follow Discord TOS & Community Guidelines",
                        value="We will ban anyone who does not follow the Discord Community Guidelines & TOS.\n"
                              "The minimum age to own a Discord Account is 13. Anyone found to be younger will be banned.\n"
                              "*Underage bans are appealable when the user is of age.*\n\n"
                              "Links:\n"
                              "https://discord.com/guidelines\n"
                              "https://discord.com/terms", inline=False)
        embeds.append(embed)
        embed = discord.Embed(title="Public Resources",
                             description="__Help Is Available__\n"
                                         "If you or someone you know is going through a hard time, try to console them and direct them to a professional that can help the person in need."
                                         "Life is precious, please do not hesitate to contact any of these hotlines.\n\n"
                                         "**National Suicide Prevention Lifeline**: `1-800-273-8255` (24/7)\n"
                                         "**The Crisis Text Line**: Text \"HOME\" to `741741`\n"
                                         "**Trevor Project (LGBTQIA+)**: `1-866-488-7386` (24/7)\n\n"
                                         "`BRIGHTER DAYS WILL COME, STAY STRONG.`",
                             color=discord.Color.blurple())
        embeds.append(embed)
        await channel.send("Thank you for joining the Atlas, we are excited to have you here! We have channels ready and waiting for you and your friends to join.", embed=embeds[0])
        for embed in embeds[1:]:
            await channel.send(embed=embed)
        msg = "> Other Servers \n" \
            "**Official Servers** \n" \
               "• Main Server \n" \
               "https://discord.gg/atlasmc \n" \
               "• Backup Server \n" \
               "https://discord.gg/YPgnMkdNPb \n" \
               "• Development Server\n" \
               "https://discord.gg/uZesc3E6NC \n" \
               "• Ban Appeals \n" \
               "https://discord.gg/sggYbMV3uk \n" \
               "• Alpha Server \n" \
               "https://discord.gg/QAUmYjM6Av"
        await channel.send(msg)
        msg = "```\nYour presence in this server implies accepting these rules, including all further changes. These changes might be done at any time without notice, it is your responsibility to check for them.\n```"
        embed = discord.Embed(title="2 Step Verification",
                      description="Click the button below to gain access to all of our channels!",
                      color=discord.Color.blurple())
        button = Button(style=ButtonStyle.green, label='Verify', emoji=self.bot.get_emoji(831435958380658719), custom_id='verify')
        await channel.send(msg, embed=embed, components=[ActionRow(button)])
        await ctx.send(f'Rulebook has been sent to {channel.mention}!')

def setup(bot):
    bot.add_cog(Roles(bot))
