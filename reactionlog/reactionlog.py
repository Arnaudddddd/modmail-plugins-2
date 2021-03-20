import asyncio
import datetime
import re

import discord
from discord import utils
from discord.ext import commands

RE_ID = re.compile(r"\b(\d{15,21})\b")
RE_WEBHOOK_NAME = re.compile(r"webhook name:\s*(.+)\n", re.I)


class ReactionLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.webhook: discord.Webhook = None
        self.channel: discord.TextChannel = None
        self.ignored_list = []
        asyncio.create_task(self.cog_load())

    async def cog_load(self):
        await self.bot.wait_until_ready()
        self.channel = utils.get(self.bot.guild.text_channels, name='reaction-logs')
        if not self.channel:
            self.channel = next((c for c in self.bot.guild.text_channels if 'reaction-logs' in (c.topic or '')), None)

        if not self.channel:
            if not self.bot.guild.me.guild_permissions.manage_channels:
                print("I don't have permissions to manage channels")
                self.bot.remove_cog("ReactionLogger")
                return
            self.channel = await self.bot.guild.create_text_channel(
                "reaction-logs",
                topic="reaction-logs (don't edit this first line)\n"
                      "Webhook name: Reaction Logger\n\n"
                      "Ignored Channels:\n"
                      "- 122055941540671003 (example)\n"
                      "-\n\n"
                      "Ignored Members:\n"
                      "- 062234385923023350 (example)\n"
                      "-\n\n"
                      "Ignored Messages:\n"
                      "- 100698437992827166 (example)\n"
                      "-\n\n",
                overwrites={
                    self.bot.guild.me: discord.PermissionOverwrite(read_messages=True),
                    self.bot.guild.default_role: discord.PermissionOverwrite(read_messages=False)
                },
                reason="Reaction Logger!")

        self.ignored_list = [int(m) for m in RE_ID.findall(self.channel.topic or "")]

        webhook_name = RE_WEBHOOK_NAME.search(self.channel.topic or "")
        if webhook_name:
            webhook_name = webhook_name.group(1).strip()

        if self.channel.guild.id != self.bot.guild.id:
            print("Channel ID not in guild ID")
            self.bot.remove_cog("ReactionLogger")
            return
        if not isinstance(self.channel, discord.TextChannel):
            print("Channel ID is not a text channel")
            self.bot.remove_cog("ReactionLogger")
            return

        if not self.channel.permissions_for(self.channel.guild.me).manage_webhooks:
            print("I don't have permissions to manage webhooks in the channel")
            self.bot.remove_cog("ReactionLogger")
            return

        try:
            if webhook_name:
                self.webhook = utils.get(await self.channel.webhooks(), name=webhook_name)
            if not self.webhook:
                self.webhook = utils.get(await self.channel.webhooks(), name='Reaction Logger')
            if not self.webhook:
                self.webhook = await self.channel.create_webhook(name=webhook_name or 'Reaction Logger',
                                                                 avatar=await self.bot.user.avatar_url.read(),
                                                                 reason='Reaction Logger!')
                print("made webhook")
            if webhook_name and self.webhook.name != webhook_name:
                await self.webhook.edit(name=webhook_name, reason='Reaction Logger (renamed)!')
                print("renamed webhook")
        except Exception as e:
            print("Something went wrong...", e)
            self.bot.remove_cog("ReactionLogger")
            return

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if not self.webhook or \
                not self.channel or \
                after.guild.id != self.bot.guild.id or \
                after.id != self.channel.id or \
                before.topic == after.topic:
            return
        self.ignored_list = [int(m) for m in RE_ID.findall(after.topic or "")]
        webhook_name = RE_WEBHOOK_NAME.search(after.topic or "")
        if webhook_name:
            webhook_name = webhook_name.group(1).strip()

            if self.webhook.name != webhook_name:
                await self.webhook.edit(name=webhook_name, reason='Reaction Logger (renamed)!')
                print("renamed webhook")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not self.webhook or payload.guild_id != self.bot.guild.id:
            return

        user: discord.Member = payload.member
        if user.bot:
            return

        if payload.channel_id in self.ignored_list \
                or payload.message_id in self.ignored_list \
                or payload.user_id in self.ignored_list:
            return

        channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
        message: discord.PartialMessage = channel.get_partial_message(payload.message_id)
        emoji: discord.PartialEmoji = payload.emoji
        if emoji.is_custom_emoji():
            emoji_text = f"`:{emoji.name}:`"
        else:
            emoji_text = str(emoji)

        embed = discord.Embed(
            description=f"**Message:** [Jump!](https://discord.com/channels/{channel.guild.id}/{channel.id}/{message.id}) {channel.mention}\n",
            colour=0xffd1df,
        )
        embed.timestamp = datetime.datetime.utcnow()

        try:
            if emoji.is_custom_emoji():
                embed.set_author(name=f"Reaction added by {user}")
                embed.description += f"**Emoji name:** {emoji_text}\n"
                embed.set_thumbnail(url=str(emoji.url))
            else:
                embed.set_author(name=f"Reaction added by {user}")
                embed.description += f"**Emoji:** {emoji_text}\n"
        except Exception:
            embed.set_author(name=f"Reaction added by {user}")
            embed.description += f"**Emoji name:** {emoji_text} (emoji can't be found)\n"

        embed.set_footer(text=f"User ID: {user.id}\n"
                              f"Channel ID: {channel.id}\n"
                              f"Message ID: {message.id}")
        await self.webhook.send(embed=embed)


def setup(bot):
    bot.add_cog(ReactionLogger(bot))
