from enum import Enum, auto
import discord
from discord.ext import commands
from discord.ui import Button, View
import re



class ManualReview:
    ABUSE_DEFINITIONS = {
        "Bullying": "Intent to harm, intimidate, or coerce (someone perceived as vulnerable).",
        "Hate Speech": "Abusive or threatening speech or writing that expresses prejudice against a particular group, especially on the basis of race, religion, or sexual orientation.",
        "Sexual Harassment": "Content that depicts sexually explicit activities",
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
        self.targeted_harassment = report_info["targeted_harassment"]
        self.targeted_harassment_messages = report_info["targeted_harassment_messages"]
        self.target_twitter_info = report_info["target_twitter_info"]
        self.being_silenced = report_info["being_silenced"]
        self.mod_channel = client.mod_channels[report_info["message"].guild.id]
        self.client = client
        self.kicked_users = set()
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
                {
                    "name": "Targeted Harassment Campaign",
                    "value": "Yes" if self.targeted_harassment else "No",
                    "inline": False,
                },
            ]
        }
        harassment_campaign_messages = ""
        if len(self.targeted_harassment_messages) > 0:
            for message in self.targeted_harassment_messages:
                harassment_campaign_messages += f'<@{message.author.id}> said:\n"{truncate_string(message.content)}" [[link]({message.jump_url})]\n\n'
            embed["fields"].append({
                "name": "Messages in Harassment Campaign",
                "value": harassment_campaign_messages,
                "inline": False,
            })
        if self.target_twitter_info:
            value = f"Handle: @{self.target_twitter_info['handle']}\n"
            value += f"Name: {self.target_twitter_info['name']}\n"
            value += f"Bio: {self.target_twitter_info['bio']}"
            embed["fields"].append({
                "name": "Harrassed Twitter User",
                "value":  value,
                "inline": True,
            })
        if self.targeted_harassment:
            embed["fields"].append({
                "name": "User being Silenced?",
                "value":  "Yes" if self.being_silenced else "No",
                "inline": True,
            })
        view = InitialMessageView(self.begin_review)
        if self.report_imminent_danger and self.targeted_harassment:
            view = InitialMessageViewDangerHarassment(self.message, self.mod_channel, self.author, self.begin_review, self.take_action_on_harassment)
        elif self.report_imminent_danger:
            view = InitialMessageViewDanger(self.message, self.mod_channel, self.author, self.begin_review)
        elif self.targeted_harassment:
            view = InitialMessageViewHarassment(self.begin_review, self.take_action_on_harassment)

        if self.report_imminent_danger:
            embed["description"] = "User is in imminent danger and wants the following info reported to the authorities."
        try:
            await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)
        except:
            if len(self.targeted_harassment_messages) > 0:
                index = -3 if self.target_twitter_info else -2
                embed["fields"][index] = {
                    "name": "Messages in Harassment Campaign (not all displayed here)",
                    "value": truncate_string(harassment_campaign_messages),
                    "inline": False,
                }
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
        view = ReturnUserView(message_to_user, self.reporting_channel)
        await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)

    async def take_action_on_message(self):
        embed = {
            "title": "Take Action",
            "description": "How would you like to take action?",
        }
        view = TakeActionView(self.message, self.mod_channel, self.reporting_channel, self.kicked_users)
        await self.mod_channel.send(embed=discord.Embed.from_dict(embed), view=view)

    async def take_action_on_harassment(self):
        view = None
        if self.target_twitter_info and len(self.targeted_harassment_messages) > 0:
            view = TargetedHarassmentTwitterView(self.targeted_harassment_messages, self.target_twitter_info, self.mod_channel, self.reporting_channel, self.kicked_users)
        elif self.target_twitter_info:
            view = TwitterView(self.target_twitter_info, self.mod_channel)
        elif len(self.targeted_harassment_messages) > 0:
            view = TargetedHarassmentView(self.targeted_harassment_messages, self.reporting_channel, self.kicked_users)
        else:
            await self.mod_channel.send("No actions to take on harassment campaign; no reported messages or Twitter account.")
            return

        primary_embed = {
            "title": "Targeted Harassment Campaign",
            "description": "How would you like to take action on the following user-reported harassment campaign and its associated messages?",
            "fields": [],
        }
        if self.target_twitter_info:
            twitter_value = f"Handle: @{self.target_twitter_info['handle']}\n"
            twitter_value += f"Name: {self.target_twitter_info['name']}\n"
            twitter_value += f"Bio: {self.target_twitter_info['bio']}"
            primary_embed["fields"].append({
                "name": "Harrassed Twitter User",
                "value":  twitter_value,
                "inline": False,
            })
        if len(self.targeted_harassment_messages) == 0:
            await self.mod_channel.send(embed=discord.Embed.from_dict(primary_embed), view=view)
            return

        primary_embed["fields"].append({
            "name": "Targeted Messages",
            "value": "",
            "inline": False,
        })

        message_to_user = ""
        sent_first_message = False
        secondary_embed = {
            "title": "Targeted Harassment Campaign (continued)",
            "fields": [
                {
                    "name": "Targeted Messages",
                    "value": "",
                    "inline": False,
                }
            ]
        }
        for message in self.targeted_harassment_messages:
            if len(message_to_user) > 700:
                if not sent_first_message:
                    primary_embed["fields"][1 if self.target_twitter_info else 0]["value"] = message_to_user
                    sent_first_message = True
                    await self.mod_channel.send(embed=discord.Embed.from_dict(primary_embed))
                    message_to_user = ""
                else:
                    secondary_embed["fields"][0]["value"] = message_to_user
                    await self.mod_channel.send(embed=discord.Embed.from_dict(secondary_embed))
                    message_to_user = ""
            message_to_user += f'<@{message.author.id}> said:\n"{truncate_string(message.content)}" [[link]({message.jump_url})]\n'
        if not sent_first_message:
            primary_embed["fields"][1 if self.target_twitter_info else 0]["value"] = message_to_user
            sent_first_message = True
            await self.mod_channel.send(embed=discord.Embed.from_dict(primary_embed), view=view)
            message_to_user = ""
        else:
            secondary_embed["fields"][0]["value"] = message_to_user
            await self.mod_channel.send(embed=discord.Embed.from_dict(secondary_embed), view=view)
            message_to_user = ""


def truncate_string(string):
    '''
    Truncate string to a certain length and add ellipsis if appropriate
    '''
    TRUNCATION_LENGTH = 325
    return string[:TRUNCATION_LENGTH] + ("..." if len(string) > TRUNCATION_LENGTH else "")


class InitialMessageView(View):
    def __init__(self, begin_review):
        super().__init__()
        self.begin_review = begin_review

    @discord.ui.button(label='Review Reported Message', style=discord.ButtonStyle.green)
    async def begin_review_callback(self, button, interaction):
        button.label = 'Started Message Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.begin_review()


class InitialMessageViewHarassment(View):
    def __init__(self, begin_review, take_action_on_harassment):
        super().__init__()
        self.begin_review = begin_review
        self.take_action_on_harassment = take_action_on_harassment

    @discord.ui.button(label='Review Reported Message', style=discord.ButtonStyle.green)
    async def begin_review_callback(self, button, interaction):
        button.label = 'Started Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.begin_review()

    @discord.ui.button(label='Review Harassment Campaign', style=discord.ButtonStyle.blurple)
    async def review_harassment_callback(self, button, interaction):
        button.label = 'Started Harassment Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.take_action_on_harassment()


class InitialMessageViewDanger(View):
    def __init__(self, message, mod_channel, author, begin_review):
        super().__init__()
        self.message = message
        self.mod_channel = mod_channel
        self.author = author
        self.begin_review = begin_review

    @discord.ui.button(label='Review Reported Message', style=discord.ButtonStyle.green)
    async def begin_review_callback(self, button, interaction):
        button.label = 'Started Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.begin_review()

    @discord.ui.button(label='Report to Authorities', style=discord.ButtonStyle.red)
    async def report_authorities_callback(self, button, interaction):
        button.label = 'Authorities Alerted'
        button.disabled = True
        message = "The authorities have been sent the following information:\n\n"
        message += f"Reported by: {self.author}\n"
        message += f'<@{self.message.author.id}> said:\n"{truncate_string(self.message.content)}"\n'
        message += f'Link to message: {self.message.jump_url}'
        await self.mod_channel.send(message)
        await interaction.response.edit_message(view=self)


class InitialMessageViewDangerHarassment(View):
    def __init__(self, message, mod_channel, author, begin_review, take_action_on_harassment):
        super().__init__()
        self.message = message
        self.mod_channel = mod_channel
        self.author = author
        self.begin_review = begin_review
        self.take_action_on_harassment = take_action_on_harassment

    @discord.ui.button(label='Review Reported Message', style=discord.ButtonStyle.green)
    async def begin_review_callback(self, button, interaction):
        button.label = 'Started Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.begin_review()

    @discord.ui.button(label='Review Harassment Campaign', style=discord.ButtonStyle.blurple)
    async def review_harassment_callback(self, button, interaction):
        button.label = 'Started Harassment Review'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.take_action_on_harassment()

    @discord.ui.button(label='Report to Authorities', style=discord.ButtonStyle.red)
    async def report_authorities_callback(self, button, interaction):
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
    def __init__(self, message, reporting_channel):
        super().__init__()
        self.message = message
        self.reporting_channel = reporting_channel

    @discord.ui.button(label="Don't send", style=discord.ButtonStyle.red)
    async def cancel_callback(self, button, interaction):
        button.label = "Not sent"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Send', style=discord.ButtonStyle.green)
    async def send_callback(self, button, interaction):
        button.label = 'Sent'
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await self.reporting_channel.send(self.message)


class TakeActionView(View):
    def __init__(self, message, mod_channel, reporting_channel, kicked_users):
        super().__init__()
        self.message = message
        self.mod_channel = mod_channel
        self.reporting_channel = reporting_channel
        self.kicked_users = kicked_users

    @discord.ui.button(label='Delete message', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        button.label = 'Message deleted'
        button.disabled = True
        await interaction.response.edit_message(view=self)
        try:
            await self.message.delete()
            await self.reporting_channel.send(f"The message you reported was deleted [`{self.message.author} said: \"{truncate_string(self.message.content)}\"`].")
        except:
            await self.mod_channel.send("Looks like that message was already deleted.")

    @discord.ui.button(label='Kick user', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        button.label = 'User kicked'
        button.disabled = True
        if self.message.author not in self.kicked_users:
            await self.message.channel.send(f'{self.message.author.name} has been kicked.') # simulate user being kicked
            await self.reporting_channel.send(f"The user you reported [`{self.message.author}`] was kicked.")
            self.kicked_users.add(self.message.author)
        await interaction.response.edit_message(view=self)


class TargetedHarassmentView(View):
    def __init__(self, targeted_harassment_messages, reporting_channel, kicked_users):
        super().__init__()
        self.targeted_harassment_messages = targeted_harassment_messages
        self.reporting_channel = reporting_channel
        self.kicked_users = kicked_users

    @discord.ui.button(label='Delete all messages', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Messages deleted'
        button.disabled = True
        for message in self.targeted_harassment_messages:
            try:
                await message.delete()
                await self.reporting_channel.send(f"The message you reported was deleted [`{message.author} said: \"{truncate_string(message.content)}\"`].")
            except discord.errors.NotFound as err:
                pass
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Kick users', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Users kicked'
        button.disabled = True
        for message in self.targeted_harassment_messages:
            if message.author not in self.kicked_users:
                await message.channel.send(f'{message.author} has been kicked.') # simulate user being kicked
                await self.reporting_channel.send(f"The user identified in the targeted harassment campain you reported, [`{message.author}`], was kicked.")
                self.kicked_users.add(message.author)
        await interaction.edit_original_message(view=self)

class TwitterView(View):
    def __init__(self, target_twitter_info, mod_channel):
        super().__init__()
        self.target_twitter_info = target_twitter_info
        self.mod_channel = mod_channel

    @discord.ui.button(label='Share Harassment with Twitter', style=discord.ButtonStyle.blurple)
    async def report_twitter_callback(self, button, interaction):
        button.label = 'Sent to Twitter'
        button.disabled = True
        message = "Twitter has been alerted that the following user may be the victim of a targeted harassment campaign:\n"
        message += f"```Handle: {self.target_twitter_info['handle']}\n"
        message += f"Name: {self.target_twitter_info['name']}\n"
        message += f"Bio: {self.target_twitter_info['bio']}```"
        await self.mod_channel.send(message)
        await interaction.response.edit_message(view=self)



class TargetedHarassmentTwitterView(View):
    def __init__(self, targeted_harassment_messages, target_twitter_info, mod_channel, reporting_channel, kicked_users):
        super().__init__()
        self.targeted_harassment_messages = targeted_harassment_messages
        self.target_twitter_info = target_twitter_info
        self.mod_channel = mod_channel
        self.reporting_channel = reporting_channel
        self.kicked_users = kicked_users

    @discord.ui.button(label='Delete all messages', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Messages deleted'
        button.disabled = True
        for message in self.targeted_harassment_messages:
            try:
                await message.delete()
                await self.reporting_channel.send(f"The message you reported was deleted [`{message.author} said: \"{truncate_string(message.content)}\"`].")
            except discord.errors.NotFound as err:
                pass
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Kick users', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Users kicked'
        button.disabled = True
        for message in self.targeted_harassment_messages:
            if message.author not in self.kicked_users:
                await message.channel.send(f'{message.author} has been kicked.') # simulate user being kicked
                await self.reporting_channel.send(f"The user identified in the targeted harassment campain you reported, [`{message.author}`], was kicked.")
                self.kicked_users.add(message.author)
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Share Harassment with Twitter', style=discord.ButtonStyle.blurple)
    async def report_twitter_callback(self, button, interaction):
        button.label = 'Sent to Twitter'
        button.disabled = True
        message = "Twitter has been alerted that the following user may be the victim of a targeted harassment campaign:\n"
        message += f"```Handle: {self.target_twitter_info['handle']}\n"
        message += f"Name: {self.target_twitter_info['name']}\n"
        message += f"Bio: {self.target_twitter_info['bio']}```"
        await self.mod_channel.send(message)
        await interaction.response.edit_message(view=self)
