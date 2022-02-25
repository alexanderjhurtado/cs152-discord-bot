# bot.py
import discord
from discord.ext import commands
from discord.ui import View
import os
import json
import logging
import re
import requests
from report import Report
from manual_review import ManualReview
from message_processor import MessageProcessor
from uni2ascii import uni2ascii

INDIVIDUAL_SCORE_THRESHOLD = 0.625

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_key = tokens['perspective']


class ModBot(discord.Client):
    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.manual_reviews = {} # Map from user IDs to a manual review corresponding to their
        self.perspective_key = key
        self.message_processor = MessageProcessor()

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It\'s in these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')
        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")
        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs).
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel.
        '''
        # Ignore messages from us
        if message.author.id == self.user.id:
            return
        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def on_message_edit(self, message_before, message_after):
        await self.handle_channel_message(message_after)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report and manual review process.\n"
            await message.channel.send(reply)
            return
        author_id = message.author.id
        responses = []
        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return
        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self, message.author)
        # Let the report class handle this message; forward all the messages it returns to us
        current_report = self.reports[author_id]
        responses = await current_report.handle_message(message)
        for r in responses:
            await message.channel.send(r)
        # If the report is ready for review, create a new manual report
        if current_report.report_sent():
            report_info = current_report.gather_report_information()
            if author_id not in self.manual_reviews:
                self.manual_reviews[author_id] = ManualReview(self, report_info, message.channel)
                await self.manual_reviews[author_id].initial_message()
        # If the report is complete or cancelled, remove it from report and manual review maps
        if current_report.report_complete():
            self.reports.pop(author_id)
            if author_id in self.manual_reviews:
                self.manual_reviews.pop(author_id)

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return
        mod_channel = self.mod_channels[message.guild.id]
        # ASCII-fy then extract Perspective score and entity mentions from message
        message_content = uni2ascii(message.content)
        scores = self.message_processor.eval_text(message_content)
        # Additional work for messages that are harassment-like
        if any(score >= INDIVIDUAL_SCORE_THRESHOLD for score in scores.values()):
            # Forward warning to mod channel about harassing messages
            await mod_channel.send(embed=AbuseWarningEmbed(message), view=AbuseWarningView(message))
            # TODO: Identify any entities that are being targeted and forward warning to mod channel

    async def terminate_report(self, author_id, message, channel):
        await channel.send(message)
        await self.remove_report(author_id)

    async def remove_report(self, author_id):
        if author_id in self.reports:
            self.reports.pop(author_id)
        if author_id in self.manual_reviews:
            self.manual_reviews.pop(author_id)



class AbuseWarningView(View):
    def __init__(self, message):
        super().__init__()
        self.message = message

    @discord.ui.button(label='Delete message', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        button.label = 'Message deleted'
        button.disabled = True
        await self.message.delete()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Kick user', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        button.label = 'User kicked'
        button.disabled = True
        await self.message.channel.send(f'{self.message.author.name} has been kicked.') # simulate user being kicked
        await interaction.response.edit_message(view=self)

class AbuseWarningEmbed(discord.Embed):
    def __init__(self, message):
        title = 'Potentially abusive message detected'
        description = f'<@{message.author.id}> said:\n"{self.truncate_string(message.content)}" [[link]({message.jump_url})]'
        super().__init__(title=title, description=description, color=0xED1500)

    def truncate_string(self, string):
        '''
        Truncate string to a certain length and add ellipsis if appropriate
        '''
        TRUNCATION_LENGTH = 325
        return string[:TRUNCATION_LENGTH] + ("..." if len(string) > TRUNCATION_LENGTH else "")

# class CampaignWarningEmbed(discord.Embed):
#     def __init__(self, targeted_entities):
#         title = '‼️ Possible harassment campaign detected ‼️'
#         description = self.code_format(json.dumps({'targeted_entities': targeted_entities }, indent=2))
#         super().__init__(title=title, description=description, color=0xED1500)

#     def code_format(self, text):
#         return "```" + text + "```"


client = ModBot(perspective_key)
client.run(discord_token)
