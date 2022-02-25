from enum import Enum, auto
import discord
from discord.ext import commands
from discord.ui import Button, View
import re

class ManualReview:
    def __init__(self, client, report_info):
        self.report_imminent_danger = report_info["report_imminent_danger"]
        self.author = report_info["author"]
        self.message = report_info["message"]
        self.abuse_type = report_info["abuse_type"]
        self.mod_channel = client.mod_channels[report_info["message"].guild.id]
        self.client = client

    async def initial_message(self):
        embed = {
            "title": "Manual Report",
            "color": 0x5865F2,
            "fields": [
                {
                    "name": "Reported by",
                    "value": self.author.name,
                    "inline": True,
                },
                {
                    "name": "Abuse Type",
                    "value": self.abuse_type,
                    "inline": True,
                },
                {
                    "name": "Message",
                    "value": f'<@{self.message.author.id}> said:\n"{self.truncate_string(self.message.content)}" [[link]({self.message.jump_url})]',
                    "inline": False,
                },
            ]
        }
        view = InitialMessageView(self.message, self.author, self.begin_review)
        if self.report_imminent_danger:
            view = InitialMessageViewDanger(self.message, self.mod_channel, self.author, self.begin_review, self.truncate_string)
            embed["description"] = "User is in imminent danger and wants the following info reported to the authorities."
            embed["color"] = 0xED1500
        await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)

    async def begin_review(self):
        embed = {
            "title": "Evaluate Content",
            "fields": [
                {
                    "name": "Reported by",
                    "value": self.author.name,
                    "inline": True,
                },
                {
                    "name": "Abuse Type",
                    "value": self.abuse_type,
                    "inline": True,
                },
                {
                    "name": "Message",
                    "value": f'<@{self.message.author.id}> said:\n"{self.truncate_string(self.message.content)}" [[link]({self.message.jump_url})]',
                    "inline": False,
                },
            ]
        }

    def truncate_string(self, string):
        '''
        Truncate string to a certain length and add ellipsis if appropriate
        '''
        TRUNCATION_LENGTH = 325
        return string[:TRUNCATION_LENGTH] + ("..." if len(string) > TRUNCATION_LENGTH else "")


class InitialMessageView(View):
    def __init__(self, message, author, begin_review):
        super().__init__()
        self.message = message
        self.author = author
        self.begin_review = begin_review

    @discord.ui.button(label='Begin Review', style=discord.ButtonStyle.green)
    async def begin_review_callback(self, button, interaction):
        button.label = 'Started Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.begin_review()

class InitialMessageViewDanger(View):
    def __init__(self, message, mod_channel, author, begin_review, truncate_string):
        super().__init__()
        self.message = message
        self.mod_channel = mod_channel
        self.author = author
        self.begin_review = begin_review
        self.truncate_string = truncate_string

    @discord.ui.button(label='Begin Review', style=discord.ButtonStyle.green)
    async def begin_review_callback(self, button, interaction):
        button.label = 'Started Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.begin_review()

    @discord.ui.button(label='Report to Authorities', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        button.label = 'Authorities Alerted'
        button.disabled = True
        message = "The authorities have been sent the following information:\n\n"
        message += f"Reported by: {self.author}\n"
        message += f'<@{self.message.author.id}> said:\n"{self.truncate_string(self.message.content)}" [[link]({self.message.jump_url})]\n'
        await self.mod_channel.send(message)
        await interaction.response.edit_message(view=self)
