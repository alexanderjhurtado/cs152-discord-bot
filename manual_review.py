from enum import Enum, auto
import discord
from discord.ext import commands
from discord.ui import Button, View
import re



class ManualReview:
    ABUSE_DEFINITIONS = {
        "Bullying": "Intent to harm, intimidate, or coerce (someone perceived as vulnerable).",
        "Hate Speech": "Abusive or threatening speech or writing that expresses prejudice against a particular group, especially on the basis of race, religion, or sexual orientation.",
        "Sexual Harrassment": "Content that depicts sexually explicit activities",
        "Revealing Personal Information": "Content that exposes a user's personal, sensitive information without consent",
        "Advocating Violence": "Depiction of especially vivid, brutal and realistic acts of violence",
        "Other": "General category that includes all malicious content that is may be considered in violation of our guidelines",
    }

    NOT_ABUSE_MESSAGE = "Sorry, we did not find the reported content to be in violation of our community guidelines: "

    def __init__(self, case_id, client, report_info, reporting_channel):
        self.case_id = case_id
        self.report_imminent_danger = report_info["report_imminent_danger"]
        self.author = report_info["author"]
        self.message = report_info["message"]
        self.abuse_type = report_info["abuse_type"]
        self.mod_channel = client.mod_channels[report_info["message"].guild.id]
        self.client = client
        self.reporting_channel = reporting_channel

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
                    "value": f'<@{self.message.author.id}> said:\n"{truncate_string(self.message.content)}" [[link]({self.message.jump_url})]',
                    "inline": False,
                },
            ]
        }
        view = InitialMessageView(self.message, self.author, self.begin_review)
        if self.report_imminent_danger:
            view = InitialMessageViewDanger(self.message, self.mod_channel, self.author, self.begin_review)
            embed["description"] = "User is in imminent danger and wants the following info reported to the authorities."
            embed["color"] = 0xED1500
        await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)

    async def begin_review(self):
        description = f"This content was identified as `{self.abuse_type}` material. Is this content in violation of our guidelines?\n\n"
        description += "For your reference, here is our definition of this abuse type:"
        embed = {
            "title": "Evaluate Content",
            "description": description,
            "fields": [
                {
                    "name": f"{self.abuse_type}",
                    "value": self.ABUSE_DEFINITIONS[self.abuse_type],
                    "inline": False,
                },
                {
                    "name": "Message",
                    "value": f'<@{self.message.author.id}> said:\n"{truncate_string(self.message.content)}" [[link]({self.message.jump_url})]',
                    "inline": False,
                },
            ]
        }
        view = EvaluateAbuseView(self.return_to_user, self.take_action_on_message)
        await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)

    async def return_to_user(self):
        message_to_user = self.NOT_ABUSE_MESSAGE + f"[`{self.message.author} said: \"{truncate_string(self.message.content)}\"`]"
        embed = {
            "title": "Return To User",
            "description": "The content was not found to be abusive. Send the following message to the user?",
            "fields": [
                {
                    "name": "Reply to User",
                    "value": message_to_user,
                    "inline": False,
                },
            ]
        }
        view = ReturnUserView(self.end_case, message_to_user)
        await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)

    async def take_action_on_message(self):
        embed = {
            "title": "Take Action",
            "description": "How would you like to take action?",
        }
        view = TakeActionView(self.message, self.mod_channel, self.end_case)
        await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)

    async def end_case(self, message=None):
        await self.client.terminate_case(
            author_id=self.author.id,
            manual_review_case_id=self.case_id,
            message=message,
            channel=self.reporting_channel
        )

def truncate_string(string):
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
    def __init__(self, message, mod_channel, author, begin_review):
        super().__init__()
        self.message = message
        self.mod_channel = mod_channel
        self.author = author
        self.begin_review = begin_review

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
        message += f'<@{self.message.author.id}> said:\n"{truncate_string(self.message.content)}"\n'
        message += f'Link to message: {self.message.jump_url}'
        await self.mod_channel.send(message)
        await interaction.response.edit_message(view=self)


class EvaluateAbuseView(View):
    def __init__(self, return_to_user, take_action_on_message):
        super().__init__()
        self.return_to_user = return_to_user
        self.take_action_on_message = take_action_on_message

    @discord.ui.button(label='No', style=discord.ButtonStyle.red)
    async def no_callback(self, button, interaction):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await self.return_to_user()

    @discord.ui.button(label='Yes', style=discord.ButtonStyle.green)
    async def yes_callback(self, button, interaction):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await self.take_action_on_message()


class ReturnUserView(View):
    def __init__(self, end_case, message):
        super().__init__()
        self.end_case = end_case
        self.message = message

    @discord.ui.button(label="Don't send", style=discord.ButtonStyle.red)
    async def cancel_callback(self, button, interaction):
        button.label = "Not sent"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await self.end_case()

    @discord.ui.button(label='Send', style=discord.ButtonStyle.green)
    async def send_callback(self, button, interaction):
        button.label = 'Sent'
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await self.end_case(self.message)


class TakeActionView(View):
    def __init__(self, message, mod_channel, end_case):
        super().__init__()
        self.message = message
        self.mod_channel = mod_channel
        self.end_case = end_case

    @discord.ui.button(label='Delete message', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        button.label = 'Message deleted'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        try:
            await self.message.delete()
            await self.end_case(f"The message you reported was deleted [`{self.message.author} said: \"{truncate_string(self.message.content)}\"`].")
        except:
            await self.mod_channel.send("Looks like that message was already deleted.")
            await self.end_case()


    @discord.ui.button(label='Kick user', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        button.label = 'User kicked'
        button.disabled = True
        await self.message.channel.send(f'{self.message.author.name} has been kicked.') # simulate user being kicked
        await interaction.response.edit_message(view=self)
        await self.end_case(f"The user you reported [`{self.message.author}`] was kicked.")
