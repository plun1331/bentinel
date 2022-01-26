import datetime
import discord
import json
import io

def embed_to_json(embed: discord.Embed):
    embed_json = {}
    embed_json['title'] = embed.title or None
    embed_json['description'] = embed.description or None
    embed_json['url'] = embed.url or None
    if embed.color is not Embed.Empty:
        color = getattr(embed.color, 'value', embed.color)
        embed_json['color'] = str(hex(color)).replace('0x', '#')
    if embed.timestamp is not Embed.Empty:
        embed_json['timestamp'] = embed.timestamp.isoformat()
    if embed.footer is not Embed.Empty:
        _footer_json = {}
        if embed.footer.text is not Embed.Empty:
            _footer_json['text'] = embed.footer.text
        if embed.footer.icon_url is not Embed.Empty:
            _footer_json['icon_url'] = embed.footer.icon_url
        if any(list(_footer_json.values())):
            embed_json['footer'] = _footer_json
    if embed.author is not Embed.Empty:
        _author_json = {}
        if embed.author.name is not Embed.Empty:
            _author_json['name'] = embed.author.name if embed.author.name is not Embed.Empty else None
        if embed.author.url is not Embed.Empty:
            _author_json['url'] = embed.author.url if embed.author.url is not Embed.Empty else None
        if embed.author.icon_url is not Embed.Empty:
            _author_json['icon_url'] = embed.author.icon_url if embed.author.icon_url is not Embed.Empty else None
        if any(list(_author_json.values())):
            embed_json['author'] = _author_json
    embed_json['fields'] = []
    for field in embed.fields:
        _field_json = {}
        _field_json['name'] = field.name
        _field_json['value'] = field.value
        _field_json['inline'] = field.inline
        embed_json['fields'].append(_field_json)
    if embed.thumbnail is not Embed.Empty and embed.thumbnail.url is not Embed.Empty:
        embed_json['thumbnail'] = {'url': embed.thumbnail.url}
    if embed.image is not Embed.Empty and embed.image.url is not Embed.Empty:
        embed_json['image'] = {'url': embed.image.url}
    return {k: v for k, v in embed_json.items() if v is not None}

def attachment_to_json(attachment: discord.Attachment):
    attachment_json = {}
    attachment_json["url"] = attachment.url
    attachment_json["name"] = attachment.filename
    attachment_json["size"] = attachment.size
    attachment_json["height"] = attachment.height
    attachment_json["width"] = attachment.width
    return attachment_json

def message_to_json(message: discord.Message):
    message_json = {}
    discordData = {}
    for mention in message.channel_mentions:
        discordData[str(mention.id)] = {"name": mention.name}
    for mention in message.role_mentions:
        discordData[str(mention.id)] = {"name": mention.name}
    for mention in message.mentions:
        discordData[str(mention.id)] = {
            "name": mention.name,
            "tag": mention.discriminator,
            "nick": mention.display_name,
            "avatar": str(mention.avatar_url).split('/')[-1].split('?')[0].split('.')[0]
        }
    message_json["discordData"] = discordData
    message_json["id"] = message.id
    if message.reference is not None:
        ref = {}
        ref["message"] = message.reference.message_id
        ref["channel"] = message.reference.channel_id
        ref["server"] = message.reference.guild_id
        message_json["reference"] = ref
    message_json["embeds"] = [embed_to_json(embed) for embed in message.embeds]
    message_json["content"] = message.system_content
    message_json["user_id"] = str(message.author.id)
    message_json["bot"] = message.author.bot
    message_json["username"] = message.author.name
    message_json["tag"] = message.author.discriminator
    message_json["nick"] = message.author.display_name
    message_json["avatar"] = str(message.author.avatar_url).split('/')[-1].split('?')[0].split('.')[0]
    message_json["created"] = message.created_at.isoformat()
    message_json["edited"] = message.edited_at.isoformat() if message.edited_at is not None else None
    message_json["attachments"] = [attachment_to_json(attachment) for attachment in message.attachments]
    return message_json

async def save_channel(channel: discord.TextChannel):
    guild: discord.Guild = channel.guild
    _messages = []
    _user_info = {} # {"text": # of messages}
    async with channel.typing():
        async for message in channel.history(limit=None, oldest_first=True):
            message: discord.Message
            _messages.append(message_to_json(message))
            if f"{message.author} ({message.author.id})" in _user_info:
                _user_info[f"{message.author} ({message.author.id})"] += 1
            else:
                _user_info[f"{message.author} ({message.author.id})"] = 1
    user_info = ""
    for key, value in _user_info.items():
        user_info += f"    {value} - {key}\n"
    _channel = {
        "name": channel.name,
        "id": str(channel.id),
    }
    _guild = {
        "name": guild.name,
        "id": str(guild.id),
        "icon": str(guild.icon_url).split('/')[-1].split('?')[0].split('.')[0],
    }
    html = f"<Server-Info>\n" \
            f"    Server: {guild.name} ({guild.id})\n" \
            f"    Channel: {channel.name} ({channel.id})\n" \
            f"    Messages: {len(_messages)}\n" \
            f"\n" \
            f"<User-Info>\n" \
            f"{user_info}" \
            f"\n" \
            f"<Base-Transcript>\n" \
            f"    <script src=\"https://tickettool.xyz/transcript/transcript.bundle.min.obv.js\">\n" \
            f"    </script>\n" \
            f"    <script type=\"text/javascript\">\n" \
            f"        let channel = {json.dumps(_channel)};\n" \
            f"        let guild = {json.dumps(_guild)};\n" \
            f"        let messages = {json.dumps(_messages)};\n" \
            f"        window.Convert(messages, channel, guild);\n" \
            f"    </script>"
    return html

class Embed(discord.Embed):
    def __init__(self, **kwargs):
        kwargs['color'] = kwargs.pop("color", None) or 0x7289da
        super().__init__(**kwargs)
        self.set_footer(text='Atlas Sentinel')
        self.timestamp = datetime.datetime.utcnow()

    def add_field(self, name, value, inline=False):
        return super().add_field(name=name, value=value, inline=inline)

    def set_footer(self, *, text, icon_url = None):
        return super().set_footer(
            text=text, 
            icon_url="https://media.discordapp.net/attachments/869021131435294730/886115047548518410/sentinel.png" if icon_url is None else icon_url
        )